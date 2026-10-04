"""Coloca a pasta do projeto no caminho de importacao (para importar o pacote 'api')."""
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
if str(PROJ) not in sys.path:
    sys.path.insert(0, str(PROJ))
