"""Isola o PROJ/GDAL do Python de instalações externas.

No Windows, programas como PostgreSQL/PostGIS e QGIS definem variáveis de ambiente
(PROJ_DATA, PROJ_LIB, GDAL_DATA) apontando para o banco de dados de projeções DELES.
Se a versão for diferente da usada pelo rasterio, ocorre o erro:
    "proj.db contains DATABASE.LAYOUT.VERSION.MINOR = x whereas a number >= 6 is expected"

Esta função remove, só para o processo atual, as variáveis que apontam para fora do
ambiente Python. Cada biblioteca passa a usar os dados que vêm empacotados com ela.
Deve ser chamada ANTES de importar rasterio, geopandas ou pyogrio.
"""
import os
import sys
from pathlib import Path

VARIAVEIS = ("PROJ_DATA", "PROJ_LIB", "GDAL_DATA")


def isolar_proj_gdal() -> list[str]:
    prefixos = {Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve()}
    removidas = []
    for var in VARIAVEIS:
        valor = os.environ.get(var)
        if not valor:
            continue
        caminho = Path(valor).resolve()
        dentro = any(p == caminho or p in caminho.parents for p in prefixos)
        if not dentro:
            os.environ.pop(var)
            removidas.append(f"{var}={valor}")
    if removidas:
        print("Aviso: variáveis externas ignoradas neste processo: " + "; ".join(removidas),
              file=sys.stderr)
    return removidas
