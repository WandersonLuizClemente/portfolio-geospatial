"""Verifica se as bibliotecas do portfólio estão instaladas e mostra as versões.

Uso:
    python scripts/check_env.py
"""
import importlib

PACOTES = [
    "numpy",
    "pandas",
    "geopandas",
    "shapely",
    "pyproj",
    "rasterio",
    "matplotlib",
    "pystac_client",
]


def main() -> None:
    faltando = []
    for nome in PACOTES:
        try:
            modulo = importlib.import_module(nome)
            versao = getattr(modulo, "__version__", "versão não informada")
            print(f"[OK]    {nome:<14} {versao}")
        except ImportError:
            print(f"[FALTA] {nome}")
            faltando.append(nome)

    if faltando:
        print("\nInstale o que falta com:  pip install -r requirements.txt")
    else:
        print("\nAmbiente pronto.")


if __name__ == "__main__":
    main()
