"""Pipeline de NDVI por talhão com Sentinel-2 L2A (Earth Search / AWS, dados abertos).

Para cada cena do período: lê só a janela de cada talhão (COG, sem baixar a cena inteira),
aplica a máscara de nuvem/sombra (banda SCL), calcula o NDVI e grava estatísticas por talhão.

Uso:
    python scripts/ndvi_pipeline.py \
        --talhoes data/private/talhoes.gpkg \
        --inicio 2025-10-01 --fim 2026-09-30

Saída: outputs/tables/ndvi_por_talhao.csv
"""
from __future__ import annotations

import argparse
import os
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

from proj_env import isolar_proj_gdal

isolar_proj_gdal()  # antes de importar geopandas/rasterio

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import rasterio  # noqa: E402
from rasterio import features  # noqa: E402
from rasterio.enums import Resampling  # noqa: E402
from rasterio.windows import Window, from_bounds  # noqa: E402
from shapely.geometry import box  # noqa: E402

STAC_URL = "https://earth-search.aws.element84.com/v1"
COLECAO = "sentinel-2-l2a"
# Classes SCL aceitas: 4 = vegetação, 5 = solo nu. Todo o resto (nuvem, sombra, água,
# neve, defeito) é descartado.
SCL_VALIDAS = (4, 5)
COLUNAS_OBRIGATORIAS = ("id", "cultura")


@dataclass
class Cena:
    id: str
    data: str
    red: str
    nir: str
    scl: str
    escala: float = 0.0001  # DN -> reflectância
    offset: float = 0.0     # baseline >= 04.00 usa offset de -0,1


def buscar_cenas(bbox, inicio: str, fim: str, max_nuvem: float) -> list[Cena]:
    """Consulta o catálogo STAC e devolve as cenas com bandas red (B04), nir (B08) e scl."""
    from pystac_client import Client

    os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")

    cliente = Client.open(STAC_URL)
    busca = cliente.search(
        collections=[COLECAO],
        bbox=list(bbox),
        datetime=f"{inicio}/{fim}",
        query={"eo:cloud_cover": {"lt": max_nuvem}},
    )
    cenas = []
    for item in busca.items():
        ativos = item.assets
        if not all(k in ativos for k in ("red", "nir", "scl")):
            continue
        bandas = ativos["red"].extra_fields.get("raster:bands", [{}])
        escala = bandas[0].get("scale", 0.0001)
        offset = bandas[0].get("offset", 0.0)
        cenas.append(
            Cena(
                id=item.id,
                data=item.datetime.date().isoformat(),
                red=ativos["red"].href,
                nir=ativos["nir"].href,
                scl=ativos["scl"].href,
                escala=escala,
                offset=offset,
            )
        )
    cenas.sort(key=lambda c: c.data)
    return cenas


def _janela_inteira(janela: Window) -> Window:
    """Arredonda uma janela fracionária para fora, cobrindo todos os pixels tocados."""
    col0 = int(np.floor(janela.col_off))
    row0 = int(np.floor(janela.row_off))
    col1 = int(np.ceil(janela.col_off + janela.width))
    row1 = int(np.ceil(janela.row_off + janela.height))
    return Window(col0, row0, col1 - col0, row1 - row0)


def calcular_ndvi(red_dn, nir_dn, escala: float, offset: float):
    """NDVI a partir dos números digitais. Pixels sem dado (DN = 0) viram NaN."""
    red = red_dn.astype("float32") * escala + offset
    nir = nir_dn.astype("float32") * escala + offset
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir - red) / (nir + red)
    ndvi[(red_dn == 0) | (nir_dn == 0)] = np.nan
    return np.clip(ndvi, -1.0, 1.0)


def ndvi_por_talhao(cena: Cena, talhoes: gpd.GeoDataFrame, min_validos: float = 0.5) -> list[dict]:
    """Estatísticas de NDVI de cada talhão em uma cena."""
    linhas = []
    with rasterio.open(cena.red) as r, rasterio.open(cena.nir) as n, rasterio.open(cena.scl) as s:
        geoms = talhoes.to_crs(r.crs).geometry
        limites = box(*r.bounds)
        for (_, talhao), geom in zip(talhoes.iterrows(), geoms):
            if not limites.contains(geom):
                continue  # talhão fora desta cena (limite de tile)

            janela = _janela_inteira(from_bounds(*geom.bounds, transform=r.transform))
            transf = r.window_transform(janela)
            red_dn = r.read(1, window=janela)
            nir_dn = n.read(1, window=janela)
            # SCL tem 20 m: lê a mesma área e reamostra (vizinho mais próximo) para a grade de 10 m
            jan_scl = from_bounds(*r.window_bounds(janela), transform=s.transform)
            scl = s.read(1, window=jan_scl, out_shape=red_dn.shape, resampling=Resampling.nearest)

            dentro = features.geometry_mask(
                [geom], out_shape=red_dn.shape, transform=transf, invert=True, all_touched=False
            )
            n_total = int(dentro.sum())
            if n_total == 0:
                continue

            ndvi = calcular_ndvi(red_dn, nir_dn, cena.escala, cena.offset)
            validos = dentro & np.isin(scl, SCL_VALIDAS) & np.isfinite(ndvi)
            n_validos = int(validos.sum())
            pct = n_validos / n_total
            aprovado = pct >= min_validos

            reg = {
                "data": cena.data,
                "cena": cena.id,
                "id": talhao["id"],
                "cultura": talhao["cultura"],
                "area_ha": talhao.get("area_ha", np.nan),
                "pixels_total": n_total,
                "pixels_validos": n_validos,
                "pct_validos": round(pct, 3),
                "aprovado": aprovado,
            }
            if aprovado:
                v = ndvi[validos]
                reg.update(
                    ndvi_medio=float(v.mean()),
                    ndvi_mediana=float(np.median(v)),
                    ndvi_desvio=float(v.std()),
                    ndvi_p10=float(np.percentile(v, 10)),
                    ndvi_p90=float(np.percentile(v, 90)),
                )
            linhas.append(reg)
    return linhas


def carregar_talhoes(caminho: str) -> gpd.GeoDataFrame:
    g = gpd.read_file(caminho)
    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in g.columns]
    if faltando:
        sys.exit(f"Colunas ausentes no arquivo de talhões: {faltando}")
    if g.crs is None:
        sys.exit("O arquivo de talhões não tem sistema de referência definido.")
    return g


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--talhoes", required=True, help="GeoPackage com colunas id e cultura")
    ap.add_argument("--inicio", required=True, help="AAAA-MM-DD")
    ap.add_argument("--fim", required=True, help="AAAA-MM-DD")
    ap.add_argument("--max-nuvem", type=float, default=70.0, help="cobertura máxima de nuvem da cena (%%)")
    ap.add_argument("--min-validos", type=float, default=0.5, help="fração mínima de pixels válidos por talhão")
    ap.add_argument("--saida", default="outputs/tables/ndvi_por_talhao.csv")
    a = ap.parse_args()

    talhoes = carregar_talhoes(a.talhoes)
    bbox = talhoes.to_crs(4326).total_bounds
    print(f"{len(talhoes)} talhões. Buscando cenas de {a.inicio} a {a.fim}...")
    cenas = buscar_cenas(bbox, a.inicio, a.fim, a.max_nuvem)
    if not cenas:
        sys.exit("Nenhuma cena encontrada. Aumente --max-nuvem ou amplie o período.")
    print(f"{len(cenas)} cenas encontradas.")

    registros = []
    for i, cena in enumerate(cenas, 1):
        try:
            registros += ndvi_por_talhao(cena, talhoes, a.min_validos)
            print(f"[{i}/{len(cenas)}] {cena.data} {cena.id}")
        except Exception as e:  # uma cena com falha não derruba o processamento
            warnings.warn(f"Cena {cena.id} ignorada: {e}")

    if not registros:
        sys.exit("Nenhum talhão processado.")
    df = pd.DataFrame(registros).sort_values(["id", "data"])
    Path(a.saida).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.saida, index=False)
    ok = int(df["aprovado"].sum())
    print(f"\nGravado: {a.saida} ({len(df)} linhas; {ok} com cobertura válida suficiente)")


if __name__ == "__main__":
    main()
