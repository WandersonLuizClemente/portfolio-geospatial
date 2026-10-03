"""Executa antes dos testes: isola o PROJ/GDAL de instalações externas (ex.: PostGIS no Windows)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from proj_env import isolar_proj_gdal  # noqa: E402

isolar_proj_gdal()
