"""Testes do Projeto 3. Os da API usam um repositorio falso (sem banco).

O teste de integracao so roda com PG_INTEGRACAO=1 e um PostgreSQL com PostGIS acessivel pelas
variaveis PGHOST, PGPORT, PGUSER e PGPASSWORD.
"""
import importlib.util
import json
import os
import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import criar_app
from api.repo import configuracao

PROJ = Path(__file__).resolve().parents[1]

FEATURES = [
    {"type": "Feature", "properties": {"id": "T01", "cultura": "cafe", "area_ha": 16.0},
     "geometry": {"type": "Polygon", "coordinates": [[[-40.0, -19.4], [-40.0, -19.39], [-39.99, -19.39], [-40.0, -19.4]]]}},
    {"type": "Feature", "properties": {"id": "T02", "cultura": "coco", "area_ha": 10.0},
     "geometry": {"type": "Polygon", "coordinates": [[[-39.9, -19.4], [-39.9, -19.39], [-39.89, -19.39], [-39.9, -19.4]]]}},
]
OBS = [
    {"talhao_id": "T01", "cultura": "cafe", "data": "2026-01-10", "ndvi_medio": 0.70, "ndvi_mediana": 0.71, "pct_validos": 0.95},
    {"talhao_id": "T01", "cultura": "cafe", "data": "2026-03-01", "ndvi_medio": 0.74, "ndvi_mediana": 0.75, "pct_validos": 0.90},
    {"talhao_id": "T02", "cultura": "coco", "data": "2026-01-10", "ndvi_medio": 0.80, "ndvi_mediana": 0.81, "pct_validos": 0.99},
]


class RepoFalso:
    def talhoes(self):
        return {"type": "FeatureCollection", "features": FEATURES}

    def existe_talhao(self, talhao_id):
        return talhao_id in {"T01", "T02"}

    def ndvi(self, talhao_id=None, inicio=None, fim=None):
        r = [o for o in OBS if talhao_id in (None, o["talhao_id"])]
        r = [o for o in r if inicio is None or date.fromisoformat(o["data"]) >= inicio]
        return [o for o in r if fim is None or date.fromisoformat(o["data"]) <= fim]

    def vizinhos(self, talhao_id, km):
        return [{"id": "T02", "cultura": "coco", "distancia_m": 2600.0}] if km >= 3 else []


@pytest.fixture()
def cliente():
    return TestClient(criar_app(RepoFalso()))


# ----------------------------------------------------------------------------- API
def test_saude(cliente):
    assert cliente.get("/saude").json() == {"status": "ok"}


def test_talhoes_devolve_geojson(cliente):
    r = cliente.get("/talhoes")
    assert r.status_code == 200
    j = r.json()
    assert j["type"] == "FeatureCollection" and len(j["features"]) == 2
    assert j["features"][0]["properties"]["id"] == "T01"


def test_ndvi_sem_filtro_e_com_filtros(cliente):
    assert len(cliente.get("/ndvi").json()) == 3
    assert [o["data"] for o in cliente.get("/ndvi", params={"talhao": "T01"}).json()] == ["2026-01-10", "2026-03-01"]
    r = cliente.get("/ndvi", params={"inicio": "2026-02-01"}).json()
    assert [o["talhao_id"] for o in r] == ["T01"]


def test_ndvi_recusa_datas_invertidas_e_invalidas(cliente):
    assert cliente.get("/ndvi", params={"inicio": "2026-05-01", "fim": "2026-01-01"}).status_code == 422
    assert cliente.get("/ndvi", params={"inicio": "ontem"}).status_code == 422


def test_ndvi_texto_malicioso_e_so_um_valor(cliente):
    r = cliente.get("/ndvi", params={"talhao": "T01'; DROP TABLE agro.talhao; --"})
    assert r.status_code == 200 and r.json() == []
    assert cliente.get("/ndvi", params={"talhao": "x" * 100}).status_code == 422


def test_vizinhos(cliente):
    assert cliente.get("/vizinhos/T01", params={"km": 5}).json()[0]["id"] == "T02"
    assert cliente.get("/vizinhos/T01", params={"km": 1}).json() == []
    assert cliente.get("/vizinhos/T99").status_code == 404


@pytest.mark.parametrize("km", ["0", "-3", "101", "abc"])
def test_vizinhos_recusa_distancias_invalidas(cliente, km):
    assert cliente.get("/vizinhos/T01", params={"km": km}).status_code == 422


def test_cors_so_leitura(cliente):
    r = cliente.get("/saude", headers={"Origin": "http://exemplo.com"})
    assert r.headers.get("access-control-allow-origin") == "*"
    pre = cliente.options("/saude", headers={"Origin": "http://exemplo.com",
                                             "Access-Control-Request-Method": "POST"})
    assert pre.status_code == 400  # POST nao e permitido


def test_configuracao_padroes_e_ambiente():
    assert configuracao({}) == {"host": "localhost", "port": 5432, "dbname": "portfolio_geo",
                                "user": "postgres", "password": ""}
    assert configuracao({"PGPORT": "5433", "PGPASSWORD": "x"})["port"] == 5433


# ----------------------------------------------------------------------------- exportacao
def _carregar_exportador():
    spec = importlib.util.spec_from_file_location("exportar_estatico", PROJ / "scripts" / "exportar_estatico.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["exportar_estatico"] = m
    spec.loader.exec_module(m)
    return m


def test_exportacao_estatica_gera_arquivos_validos(tmp_path):
    meta = _carregar_exportador().exportar(RepoFalso(), tmp_path / "data", hoje=date(2026, 10, 4))
    assert meta == {"gerado_em": "2026-10-04", "talhoes": 2, "observacoes_aprovadas": 3,
                    "datas": ["2026-01-10", "2026-03-01"]}
    assert json.loads((tmp_path / "data" / "talhoes.geojson").read_text(encoding="utf-8"))["type"] == "FeatureCollection"
    assert len(json.loads((tmp_path / "data" / "ndvi.json").read_text(encoding="utf-8"))) == 3


def test_pagina_nao_usa_innerhtml_com_dados():
    js = (PROJ / "docs" / "app.js").read_text(encoding="utf-8")
    assert "innerHTML" not in js and "outerHTML" not in js and "eval(" not in js


# ----------------------------------------------------------------------------- integracao (opcional)
@pytest.mark.skipif(os.environ.get("PG_INTEGRACAO") != "1", reason="defina PG_INTEGRACAO=1 e tenha um PostGIS acessivel")
def test_repositorio_contra_o_banco_real():
    from api.repo import RepositorioPostgis

    cfg = configuracao()
    cfg["dbname"] = os.environ.get("PG_BANCO_TESTE", "portfolio_geo")
    repo = RepositorioPostgis(cfg)
    gj = repo.talhoes()
    assert gj["features"] and gj["features"][0]["geometry"]["type"] in ("MultiPolygon", "Polygon")
    lon, lat = gj["features"][0]["geometry"]["coordinates"][0][0][0][:2]
    assert -180 <= lon <= 180 and -90 <= lat <= 90  # esta em WGS 84, nao em UTM
    obs = repo.ndvi()
    assert obs and all(0 <= o["ndvi_medio"] <= 1 for o in obs) and obs == sorted(obs, key=lambda o: (o["data"], o["talhao_id"]))
    t = gj["features"][0]["properties"]["id"]
    assert repo.existe_talhao(t) and not repo.existe_talhao("nao-existe")
    assert repo.ndvi(t, fim=date(2000, 1, 1)) == []
    assert all(v["id"] != t for v in repo.vizinhos(t, 100))
    assert repo.vizinhos(t, 0.001) == []
