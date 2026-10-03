"""Testa a lógica de NDVI com rasters sintéticos (sem internet).

Rodar:  python -m pytest 05-precision-agriculture/01-ndvi-sentinel2-talhoes/tests -q
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
sys.modules["ndvi_pipeline"] = pipe  # necessário para @dataclass com annotations adiadas
spec.loader.exec_module(pipe)

CRS = "EPSG:32724"  # UTM 24S (WGS 84), como as cenas Sentinel-2 da região
X0, Y0 = 400000.0, 7850000.0


def _tif(path, dados, res):
    t = from_origin(X0, Y0, res, res)
    with rasterio.open(path, "w", driver="GTiff", height=dados.shape[0], width=dados.shape[1],
                       count=1, dtype=dados.dtype, crs=CRS, transform=t) as dst:
        dst.write(dados, 1)


def _cena(tmp_path, red_dn, nir_dn, scl, escala=0.0001, offset=0.0):
    _tif(tmp_path / "red.tif", red_dn, 10)
    _tif(tmp_path / "nir.tif", nir_dn, 10)
    _tif(tmp_path / "scl.tif", scl, 20)
    return pipe.Cena("teste", "2026-01-01", str(tmp_path / "red.tif"), str(tmp_path / "nir.tif"),
                     str(tmp_path / "scl.tif"), escala, offset)


def _talhoes():
    # polígono de 400 x 400 m (40 x 40 pixels), em UTM 24S SIRGAS 2000 (EPSG:31984)
    geom = box(X0 + 200, Y0 - 600, X0 + 600, Y0 - 200)
    g = gpd.GeoDataFrame({"id": ["T01"], "cultura": ["cafe"], "area_ha": [16.0]},
                         geometry=[geom], crs=CRS).to_crs(31984)
    return g


def test_calcular_ndvi_valor_conhecido():
    red = np.full((3, 3), 1000, dtype="uint16")
    nir = np.full((3, 3), 5000, dtype="uint16")
    ndvi = pipe.calcular_ndvi(red, nir, 0.0001, 0.0)
    assert np.allclose(ndvi, (0.5 - 0.1) / (0.5 + 0.1), atol=1e-5)


def test_calcular_ndvi_offset_baseline_nova():
    # DN 2000/6000 com offset -0,1 => refletância 0,1 / 0,5 => mesmo NDVI de 0,667
    red = np.full((2, 2), 2000, dtype="uint16")
    nir = np.full((2, 2), 6000, dtype="uint16")
    ndvi = pipe.calcular_ndvi(red, nir, 0.0001, -0.1)
    assert np.allclose(ndvi, 0.4 / 0.6, atol=1e-5)


def test_sem_dado_vira_nan():
    red = np.zeros((2, 2), dtype="uint16")
    nir = np.full((2, 2), 5000, dtype="uint16")
    assert np.isnan(pipe.calcular_ndvi(red, nir, 0.0001, 0.0)).all()


def test_estatistica_do_talhao_ceu_limpo(tmp_path):
    red = np.full((100, 100), 1000, dtype="uint16")
    nir = np.full((100, 100), 5000, dtype="uint16")
    scl = np.full((50, 50), 4, dtype="uint8")  # vegetação em todo lugar
    r = pipe.ndvi_por_talhao(_cena(tmp_path, red, nir, scl), _talhoes())
    assert len(r) == 1
    assert r[0]["aprovado"] and r[0]["pct_validos"] == 1.0
    assert r[0]["ndvi_medio"] == pytest.approx(0.6667, abs=1e-3)
    assert r[0]["pixels_total"] in range(1500, 1700)  # ~1600 pixels de 10 m


def test_nuvem_e_mascarada(tmp_path):
    red = np.full((100, 100), 1000, dtype="uint16")
    nir = np.full((100, 100), 5000, dtype="uint16")
    nir[:, 40:] = 1000          # onde há "nuvem", o NDVI seria 0 se não fosse mascarado
    scl = np.full((50, 50), 4, dtype="uint8")
    scl[:, 20:] = 9             # nuvem (alta probabilidade) em metade direita, na grade de 20 m
    r = pipe.ndvi_por_talhao(_cena(tmp_path, red, nir, scl), _talhoes(), min_validos=0.3)[0]
    assert 0.3 < r["pct_validos"] < 0.7
    assert r["ndvi_medio"] == pytest.approx(0.6667, abs=1e-3)  # só pixels limpos entram na média


def test_talhao_muito_nublado_nao_e_aprovado(tmp_path):
    red = np.full((100, 100), 1000, dtype="uint16")
    nir = np.full((100, 100), 5000, dtype="uint16")
    scl = np.full((50, 50), 9, dtype="uint8")  # tudo nuvem
    r = pipe.ndvi_por_talhao(_cena(tmp_path, red, nir, scl), _talhoes())[0]
    assert r["aprovado"] is False and "ndvi_medio" not in r


def test_talhao_fora_da_cena_e_ignorado(tmp_path):
    red = np.full((10, 10), 1000, dtype="uint16")   # cena pequena: não contém o talhão
    nir = np.full((10, 10), 5000, dtype="uint16")
    scl = np.full((5, 5), 4, dtype="uint8")
    assert pipe.ndvi_por_talhao(_cena(tmp_path, red, nir, scl), _talhoes()) == []
