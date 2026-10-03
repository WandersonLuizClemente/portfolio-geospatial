"""Testes da logica de NDVI e da checagem de calibracao, com rasters sinteticos (sem internet).

Rodar (da raiz do repositorio):  python projeto1.py testar
"""
import importlib.util
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ndvi_pipeline.py"
spec = importlib.util.spec_from_file_location("ndvi_pipeline", SCRIPT)
pipe = importlib.util.module_from_spec(spec)
sys.modules["ndvi_pipeline"] = pipe  # necessario para @dataclass com annotations adiadas
spec.loader.exec_module(pipe)

CRS = "EPSG:32724"  # UTM 24S (WGS 84), como as cenas Sentinel-2 da regiao
X0, Y0 = 400000.0, 7850000.0
NDVI_ESPERADO = (0.35 - 0.04) / (0.35 + 0.04)   # refletancia red 0.04, nir 0.35 => 0.7949


def _tif(path, dados, res):
    t = from_origin(X0, Y0, res, res)
    with rasterio.open(path, "w", driver="GTiff", height=dados.shape[0], width=dados.shape[1],
                       count=1, dtype=dados.dtype, crs=CRS, transform=t) as dst:
        dst.write(dados, 1)


def _cena(tmp_path, red_dn, nir_dn, scl, offset_stac=-0.1, baseline="05.11"):
    _tif(tmp_path / "red.tif", red_dn, 10)
    _tif(tmp_path / "nir.tif", nir_dn, 10)
    _tif(tmp_path / "scl.tif", scl, 20)
    return pipe.Cena("teste", "2026-01-01", str(tmp_path / "red.tif"), str(tmp_path / "nir.tif"),
                     str(tmp_path / "scl.tif"), 0.0001, offset_stac, baseline)


def _talhoes():
    # poligono de 400 x 400 m (40 x 40 pixels) em SIRGAS 2000 / UTM 24S
    geom = box(X0 + 200, Y0 - 600, X0 + 600, Y0 - 200)
    return gpd.GeoDataFrame({"id": ["T01"], "cultura": ["cafe"], "area_ha": [16.0]},
                            geometry=[geom], crs=CRS).to_crs(31984)


def _dn(valor, n=100):
    return np.full((n, n), valor, dtype="uint16")


def _scl(valor, n=50):
    return np.full((n, n), valor, dtype="uint8")


# DN COM o +1000 embutido (padrao ESA, baseline >= 04.00): red 1400 / nir 4500
RED_EMB, NIR_EMB = 1400, 4500
# DN SEM o +1000 embutido: red 400 / nir 3500
RED_SEM, NIR_SEM = 400, 3500


# ----------------------------------------------------------------------------- formula
def test_ndvi_bruto_valor_conhecido():
    ndvi = pipe.ndvi_bruto(_dn(RED_EMB, 3), _dn(NIR_EMB, 3), 0.0001, -0.1)
    assert np.allclose(ndvi, NDVI_ESPERADO, atol=1e-4)


def test_ndvi_bruto_nao_recorta_valores_impossiveis():
    # red -0.05 e nir 0.20 => NDVI 1.67: deve continuar 1.67 (nao 1.0), para o pipeline poder descarta-lo
    ndvi = pipe.ndvi_bruto(_dn(500, 2), _dn(3000, 2), 0.0001, -0.1)
    assert np.allclose(ndvi, 0.25 / 0.15, atol=1e-3) and (ndvi > 1).all()


def test_sem_dado_e_soma_nao_positiva_viram_nan():
    assert np.isnan(pipe.ndvi_bruto(_dn(0, 2), _dn(5000, 2), 0.0001, 0.0)).all()
    assert np.isnan(pipe.ndvi_bruto(_dn(500, 2), _dn(600, 2), 0.0001, -0.1)).all()  # soma negativa


# ----------------------------------------------------------------------------- calibracao
def test_offset_do_catalogo_aceito_quando_dn_traz_o_1000(tmp_path):
    r = pipe.ndvi_por_talhao(_cena(tmp_path, _dn(RED_EMB), _dn(NIR_EMB), _scl(4)), _talhoes())[0]
    assert r["aprovado"] and r["calibracao"] == "ok" and r["offset_usado"] == -0.1
    assert r["ndvi_medio"] == pytest.approx(NDVI_ESPERADO, abs=1e-3)
    assert r["pixels_total"] in range(1500, 1700)  # ~1600 pixels de 10 m


def test_offset_do_catalogo_rejeitado_quando_dn_nao_traz_o_1000(tmp_path):
    # Este e o cenario que saturava o NDVI em 1.0: subtrair 0.1 de numeros que nao tinham +1000.
    r = pipe.ndvi_por_talhao(_cena(tmp_path, _dn(RED_SEM), _dn(NIR_SEM), _scl(4)), _talhoes())[0]
    assert r["aprovado"] and r["calibracao"] == "corrigido_pelos_dados" and r["offset_usado"] == 0.0
    assert r["ndvi_medio"] == pytest.approx(NDVI_ESPERADO, abs=1e-3)
    assert r["ndvi_medio"] < 0.9  # nunca "saturado"


def test_catalogo_sem_offset_usa_a_baseline(tmp_path):
    cena = _cena(tmp_path, _dn(RED_EMB), _dn(NIR_EMB), _scl(4), offset_stac=None, baseline="05.11")
    r = pipe.ndvi_por_talhao(cena, _talhoes())[0]
    assert r["offset_usado"] == -0.1 and r["calibracao"] == "ok"
    assert r["ndvi_medio"] == pytest.approx(NDVI_ESPERADO, abs=1e-3)


def test_pixels_impossiveis_reprovam_o_talhao(tmp_path):
    red, nir = _dn(RED_EMB), _dn(NIR_EMB)
    red[20:24, 20:60] = 500   # 10% do talhao com reflectancia negativa (soma < 0)
    nir[20:24, 20:60] = 600
    r = pipe.ndvi_por_talhao(_cena(tmp_path, red, nir, _scl(4)), _talhoes())[0]
    assert r["aprovado"] is False and r["motivo"] == "calibracao"
    assert r["pct_fora_faixa"] == pytest.approx(0.10, abs=0.02)


# ----------------------------------------------------------------------------- nuvem e geometria
def test_nuvem_e_mascarada(tmp_path):
    red, nir = _dn(RED_EMB), _dn(NIR_EMB)
    nir[:, 40:] = RED_EMB            # onde ha "nuvem", o NDVI seria 0 se nao fosse mascarado
    scl = _scl(4)
    scl[:, 20:] = 9                  # nuvem (alta probabilidade) na metade direita
    r = pipe.ndvi_por_talhao(_cena(tmp_path, red, nir, scl), _talhoes(), min_validos=0.3)[0]
    assert 0.3 < r["pct_validos"] < 0.7
    assert r["ndvi_medio"] == pytest.approx(NDVI_ESPERADO, abs=1e-3)  # so pixels limpos entram


def test_talhao_muito_nublado_nao_e_aprovado(tmp_path):
    r = pipe.ndvi_por_talhao(_cena(tmp_path, _dn(RED_EMB), _dn(NIR_EMB), _scl(9)), _talhoes())[0]
    assert r["aprovado"] is False and r["motivo"] == "cobertura_baixa" and "ndvi_medio" not in r


def test_poucos_pixels_limpos_nao_calibram_nem_aprovam(tmp_path):
    # ~324 pixels limpos (< 500) com DN sem o +1000: nao ha base para decidir o offset
    scl = _scl(9)
    scl[10:19, 10:19] = 4
    r = pipe.ndvi_por_talhao(_cena(tmp_path, _dn(RED_SEM), _dn(NIR_SEM), scl), _talhoes(), min_validos=0.1)[0]
    assert r["calibracao"] == "sem_pixels_validos" and r["motivo"] == "cobertura_baixa"
    assert r["aprovado"] is False and "ndvi_medio" not in r


def test_talhao_fora_da_cena_e_ignorado(tmp_path):
    cena = _cena(tmp_path, _dn(RED_EMB, 10), _dn(NIR_EMB, 10), _scl(4, 5))  # cena pequena
    assert pipe.ndvi_por_talhao(cena, _talhoes()) == []
