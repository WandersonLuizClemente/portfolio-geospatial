"""Anonimiza o GeoPackage original dos talhoes e grava data/private/talhoes.gpkg.

- remove o nome da fazenda e as colunas originais;
- cria os campos id (T01, T02, ...), cultura e area_ha;
- mantem o sistema de referencia do arquivo original.

Uso (da raiz do repositorio):
    python projeto1.py preparar "C:\\caminho\\talhoes_originais.gpkg"
    python projeto1.py preparar "C:\\caminho\\talhoes_originais.gpkg" --culturas cafe,coco,cafe,eucalipto,pasto
"""
import argparse
import sys
from pathlib import Path

from proj_env import isolar_proj_gdal

isolar_proj_gdal()

import geopandas as gpd  # noqa: E402

PROJ_DIR = Path(__file__).resolve().parents[1]
CULTURAS_PADRAO = "cafe,coco,cafe,eucalipto,pasto"   # na ordem dos poligonos no arquivo original


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("origem", help="GeoPackage original")
    ap.add_argument("--culturas", default=CULTURAS_PADRAO, help="uma cultura por poligono, separadas por virgula")
    ap.add_argument("--saida", default=str(PROJ_DIR / "data" / "private" / "talhoes.gpkg"))
    a = ap.parse_args()

    g = gpd.read_file(a.origem)
    culturas = [c.strip() for c in a.culturas.split(",") if c.strip()]
    if len(culturas) != len(g):
        sys.exit(f"O arquivo tem {len(g)} poligonos, mas foram informadas {len(culturas)} culturas.")
    if g.crs is None:
        sys.exit("O arquivo original nao tem sistema de referencia definido.")
    area_src = g if g.crs.is_projected else g.to_crs(31984)   # area em metros so em CRS projetado
    if not g.crs.is_projected:
        print("Aviso: CRS geografico; area calculada em EPSG:31984.")
    if not g.is_valid.all():
        print("Aviso: ha geometrias invalidas; corrija no QGIS (Verificar validade) antes de rodar.")

    saida = gpd.GeoDataFrame(
        {"id": [f"T{i:02d}" for i in range(1, len(g) + 1)], "cultura": culturas,
         "area_ha": (area_src.area / 1e4).round(2).values},
        geometry=g.geometry.values, crs=g.crs,
    )
    Path(a.saida).parent.mkdir(parents=True, exist_ok=True)
    if Path(a.saida).exists():
        Path(a.saida).unlink()
    saida.to_file(a.saida, layer="talhoes", driver="GPKG")
    print(f"Gravado: {a.saida}  (CRS {g.crs.to_string()})")
    print(saida.drop(columns="geometry").to_string(index=False))
    print("\nEste arquivo fica em data/private e NAO vai para o GitHub (.gitignore).")


if __name__ == "__main__":
    main()
