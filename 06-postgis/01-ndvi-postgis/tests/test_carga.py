"""Testes do Projeto 2. Os da primeira parte NAO precisam de banco.

O teste de integracao (ultima parte) so roda se a variavel PG_INTEGRACAO=1 estiver definida e
houver um PostgreSQL com PostGIS acessivel pelas variaveis PGHOST/PGPORT/PGUSER/PGPASSWORD.
"""
import importlib.util
import os
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import MultiPolygon, Polygon, box

PROJ = Path(__file__).resolve().parents[1]
SCRIPT = PROJ / "scripts" / "carregar_postgis.py"
spec = importlib.util.spec_from_file_location("carregar_postgis", SCRIPT)
cp = importlib.util.module_from_spec(spec)
sys.modules["carregar_postgis"] = cp
spec.loader.exec_module(cp)


# ----------------------------------------------------------------------------- configuracao
def test_configuracao_padroes_sem_pedir_senha():
    cfg = cp.configuracao(env={}, pedir_senha=False)
    assert cfg["host"] == "localhost" and cfg["port"] == 5432
    assert cfg["dbname"] == "portfolio_geo" and cfg["user"] == "postgres"
    assert cfg["password"] is None


def test_configuracao_usa_variaveis_de_ambiente():
    env = {"PGHOST": "srv", "PGPORT": "5433", "PGDATABASE": "outro", "PGUSER": "ana", "PGPASSWORD": "x"}
    cfg = cp.configuracao(env=env)  # com senha no ambiente, nao pede nada
    assert cfg == {"host": "srv", "port": 5433, "dbname": "outro", "user": "ana", "password": "x"}


# ----------------------------------------------------------------------------- talhoes
def _gpkg(tmp_path, geoms, crs="EPSG:31984", ids=None, cultura="cafe"):
    ids = ids or [f"T{i + 1:02d}" for i in range(len(geoms))]
    g = gpd.GeoDataFrame({"id": ids, "cultura": cultura}, geometry=geoms, crs=crs)
    caminho = tmp_path / "t.gpkg"
    g.to_file(caminho, driver="GPKG", layer="talhoes")
    return caminho


def test_talhoes_viram_multipoligono_em_31984(tmp_path):
    # Poligono em SIRGAS 2000 geografico (EPSG:4674), perto de Linhares-ES
    p = box(-40.06, -19.40, -40.058, -19.398)
    g = cp.ler_talhoes(_gpkg(tmp_path, [p], crs="EPSG:4674"))
    assert g.crs.to_epsg() == 31984
    assert g.geometry.iloc[0].geom_type == "MultiPolygon"
    assert g["area_ha"].iloc[0] > 1  # area calculada quando a coluna nao existe


def test_geometria_invalida_e_corrigida(tmp_path):
    gravata = Polygon([(0, 0), (10, 10), (10, 0), (0, 10), (0, 0)])  # auto-interseccao
    assert not gravata.is_valid
    deslocada = Polygon([(x + 400000, y + 7850000) for x, y in gravata.exterior.coords])
    g = cp.ler_talhoes(_gpkg(tmp_path, [deslocada]))
    assert g.geometry.iloc[0].is_valid and isinstance(g.geometry.iloc[0], MultiPolygon)


def test_talhoes_sem_crs_sao_recusados(tmp_path):
    caminho = tmp_path / "sem_crs.gpkg"
    gdf = gpd.GeoDataFrame({"id": ["T01"], "cultura": ["cafe"]}, geometry=[box(0, 0, 1, 1)])
    gdf.to_file(caminho, driver="GPKG")
    with pytest.raises(ValueError, match="CRS"):
        cp.ler_talhoes(caminho)


def test_ids_duplicados_sao_recusados(tmp_path):
    caminho = _gpkg(tmp_path, [box(400000, 7850000, 400100, 7850100), box(400200, 7850000, 400300, 7850100)],
                    ids=["T01", "T01"])
    with pytest.raises(ValueError, match="duplicados"):
        cp.ler_talhoes(caminho)


# ----------------------------------------------------------------------------- observacoes
CSV = """data,cena,id,cultura,area_ha,pixels_total,pixels_validos,pct_validos,pct_fora_faixa,offset_stac,offset_usado,calibracao,red_dn_p50,nir_dn_p50,aprovado,motivo,ndvi_medio,ndvi_mediana,ndvi_desvio,ndvi_p10,ndvi_p90
2026-01-10,S2_A,T01,cafe,16.0,1600,1500,0.94,0.0,-0.1,0.0,corrigido_pelos_dados,504.0,3500.0,True,ok,0.71,0.72,0.05,0.65,0.78
2026-01-10,S2_A,T02,coco,10.0,1000,100,0.1,0.0,-0.1,0.0,corrigido_pelos_dados,500.0,3400.0,False,cobertura_baixa,,,,,
2026-02-05,S2_B,T01,cafe,16.0,1600,0,0.0,0.0,,,sem_pixels_validos,,,False,cobertura_baixa,,,,,
"""


def test_observacoes_nan_viram_none_e_booleanos_sao_lidos(tmp_path):
    f = tmp_path / "n.csv"
    f.write_text(CSV, encoding="utf-8")
    cenas, obs = cp.ler_observacoes(f)

    assert [c["cena_id"] for c in cenas] == ["S2_A", "S2_B"]          # uma linha por cena
    assert cenas[0]["offset_usado"] == 0.0 and cenas[0]["offset_stac"] == -0.1
    assert cenas[1]["offset_stac"] is None and cenas[1]["offset_usado"] is None
    assert len(obs) == 3
    ok, reprovada, vazia = obs
    assert ok["aprovado"] is True and ok["ndvi_medio"] == pytest.approx(0.71)
    assert reprovada["aprovado"] is False and reprovada["ndvi_medio"] is None
    assert isinstance(ok["pixels_total"], int) and vazia["red_dn_p50"] is None


def test_csv_sem_colunas_obrigatorias_e_recusado(tmp_path):
    f = tmp_path / "n.csv"
    pd.DataFrame({"data": ["2026-01-01"], "cena": ["x"]}).to_csv(f, index=False)
    with pytest.raises(ValueError, match="Colunas ausentes"):
        cp.ler_observacoes(f)


# ----------------------------------------------------------------------------- SQL
def test_arquivo_de_consultas_e_lido_por_inteiro():
    texto = (PROJ / "sql" / "02_consultas.sql").read_text(encoding="utf-8")
    qs = cp.parse_consultas(texto)
    nomes = [n for n, _, _ in qs]
    assert len(qs) == 7 and len(set(nomes)) == 7
    for nome, titulo, sql in qs:
        assert titulo and not titulo.startswith("name")
        assert sql.split()[0].upper() in ("SELECT", "WITH"), nome
        assert not sql.endswith(";")


def test_esquema_define_tabelas_indice_e_restricoes():
    s = (PROJ / "sql" / "01_schema.sql").read_text(encoding="utf-8").lower()
    for trecho in ("create extension if not exists postgis", "agro.talhao", "agro.cena",
                   "agro.ndvi_observacao", "using gist", "geometry(multipolygon, 31984)",
                   "aprovado_coerente", "v_ndvi_aprovado"):
        assert trecho in s, trecho


# ----------------------------------------------------------------------------- integracao (opcional)
@pytest.mark.skipif(os.environ.get("PG_INTEGRACAO") != "1", reason="defina PG_INTEGRACAO=1 e tenha um PostGIS acessivel")
def test_fluxo_completo_no_banco(tmp_path):
    cfg = cp.configuracao(pedir_senha=False)
    cfg["dbname"] = "portfolio_geo_teste"
    cfg["password"] = cfg["password"] or ""

    import psycopg
    from psycopg import sql as psql

    with cp.conectar(cfg, dbname="postgres") as con:
        con.autocommit = True
        con.execute(psql.SQL("DROP DATABASE IF EXISTS {}").format(psql.Identifier(cfg["dbname"])))

    gpkg = _gpkg(tmp_path, [box(400000, 7850000, 400400, 7850400), box(405000, 7850000, 405400, 7850400)],
                 ids=["T01", "T02"])
    csv = tmp_path / "n.csv"
    csv.write_text(CSV.replace("T02,coco", "T02,cafe"), encoding="utf-8")

    cp.criar(cfg)
    cp.carregar(cfg, gpkg, csv)
    cp.carregar(cfg, gpkg, csv)  # idempotente: nao duplica

    with cp.conectar(cfg) as con:
        assert con.execute("SELECT count(*) FROM agro.ndvi_observacao").fetchone()[0] == 3
        assert con.execute("SELECT count(*) FROM agro.talhao").fetchone()[0] == 2
        assert con.execute("SELECT srid FROM geometry_columns WHERE f_table_name='talhao'").fetchone()[0] == 31984
        assert con.execute("SELECT count(*) FROM agro.v_ndvi_aprovado").fetchone()[0] == 1
        with pytest.raises(psycopg.errors.CheckViolation):
            con.execute("INSERT INTO agro.ndvi_observacao (cena_id, talhao_id, pixels_total, pixels_validos,"
                        " pct_validos, pct_fora_faixa, aprovado, motivo, ndvi_medio)"
                        " VALUES ('S2_B','T02',1,1,1,0,true,'ok',1.5)")
    cp.consultas(cfg)
