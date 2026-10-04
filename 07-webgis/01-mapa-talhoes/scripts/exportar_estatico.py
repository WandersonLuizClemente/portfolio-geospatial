"""Exporta talhoes e NDVI do banco para arquivos estaticos em docs/data/.

Com esses arquivos, o mapa funciona sem servidor e sem banco (por exemplo, no GitHub Pages).
Uso (raiz do repositorio):  python projeto3.py exportar
"""
import json
import sys
from datetime import date
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ))


def exportar(repo, destino: Path, hoje=None) -> dict:
    destino.mkdir(parents=True, exist_ok=True)
    talhoes = repo.talhoes()
    ndvi = repo.ndvi()
    meta = {
        "gerado_em": (hoje or date.today()).isoformat(),
        "talhoes": len(talhoes["features"]),
        "observacoes_aprovadas": len(ndvi),
        "datas": sorted({o["data"] for o in ndvi}),
    }
    (destino / "talhoes.geojson").write_text(json.dumps(talhoes, ensure_ascii=False), encoding="utf-8")
    (destino / "ndvi.json").write_text(json.dumps(ndvi, ensure_ascii=False), encoding="utf-8")
    (destino / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def main() -> int:
    from api.repo import RepositorioPostgis

    meta = exportar(RepositorioPostgis(), PROJ / "docs" / "data")
    print(f"Exportado: {meta['talhoes']} talhoes, {meta['observacoes_aprovadas']} observacoes aprovadas, "
          f"{len(meta['datas'])} datas -> docs/data/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
