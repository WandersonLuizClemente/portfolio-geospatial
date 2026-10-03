"""Verifica se as bibliotecas do portfolio estao instaladas e mostra as versoes.

Uso (da raiz do repositorio):  python scripts\check_env.py
"""
import importlib

PACOTES = ["numpy", "pandas", "geopandas", "shapely", "pyproj", "pyogrio",
           "rasterio", "matplotlib", "pystac_client", "pytest"]


def main() -> None:
    faltando = []
    for nome in PACOTES:
        try:
            modulo = importlib.import_module(nome)
            print(f"[OK]    {nome:<14} {getattr(modulo, '__version__', '-')}")
        except ImportError:
            print(f"[FALTA] {nome}")
            faltando.append(nome)
    if faltando:
        print("\nInstale o que falta com:  pip install -r requirements.txt")
    else:
        print("\nAmbiente pronto.")


if __name__ == "__main__":
    main()
