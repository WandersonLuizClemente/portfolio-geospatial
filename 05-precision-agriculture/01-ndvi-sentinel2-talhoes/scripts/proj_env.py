"""Isola o PROJ/GDAL do Python de instalacoes externas.

No Windows, programas como PostgreSQL/PostGIS e QGIS definem variaveis de ambiente
(PROJ_DATA, PROJ_LIB, GDAL_DATA) apontando para o banco de projecoes DELES. Se a versao for
diferente da usada pelo rasterio, ocorre o erro:
    "proj.db contains DATABASE.LAYOUT.VERSION.MINOR = x whereas a number >= 6 is expected"

Esta funcao remove, so para o processo atual, as variaveis que apontam para fora do ambiente
Python. Deve ser chamada ANTES de importar rasterio, geopandas ou pyogrio.
"""
import os
import sys
from pathlib import Path

VARIAVEIS = ("PROJ_DATA", "PROJ_LIB", "GDAL_DATA")


def isolar_proj_gdal() -> list:
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
        print("Aviso: variaveis externas ignoradas neste processo: " + "; ".join(removidas), file=sys.stderr)
    return removidas
