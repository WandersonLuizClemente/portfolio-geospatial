"""Projeto 2: carrega talhoes e NDVI do Projeto 1 em PostgreSQL/PostGIS e roda consultas.

Subcomandos:
    criar       cria o banco (se nao existir), a extensao PostGIS e as tabelas
    carregar    le o GeoPackage e o CSV do Projeto 1 e grava no banco (pode rodar varias vezes)
    consultas   executa as consultas de sql/02_consultas.sql e imprime os resultados
    tudo        criar + carregar + consultas

Conexao (variaveis de ambiente, com padroes): PGHOST=localhost, PGPORT=5432,
PGDATABASE=portfolio_geo, PGUSER=postgres. A senha vem de PGPASSWORD ou e pedida no terminal.
Ela nunca e gravada em arquivo.
"""
import argparse
import getpass
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from proj_env import isolar_proj_gdal  # noqa: E402

isolar_proj_gdal()

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from shapely import force_2d, make_valid  # noqa: E402
from shapely.geometry import MultiPolygon  # noqa: E402

PROJ_DIR = Path(__file__).resolve().parents[1]
RAIZ = PROJ_DIR.parents[1]
P1 = RAIZ / "05-precision-agriculture" / "01-ndvi-sentinel2-talhoes"
SQL_DIR = PROJ_DIR / "sql"
SRID = 31984

COLUNAS_OBS = [
    "pixels_total", "pixels_validos", "pct_validos", "pct_fora_faixa", "red_dn_p50", "nir_dn_p50",
    "aprovado", "motivo", "ndvi_medio", "ndvi_mediana", "ndvi_desvio", "ndvi_p10", "ndvi_p90",
]


# ----------------------------------------------------------------------------- configuracao
def configuracao(env=None, pedir_senha=True) -> dict:
    env = os.environ if env is None else env
    cfg = {
        "host": env.get("PGHOST", "localhost"),
        "port": int(env.get("PGPORT", "5432")),
        "dbname": env.get("PGDATABASE", "portfolio_geo"),
        "user": env.get("PGUSER", "postgres"),
        "password": env.get("PGPASSWORD"),
    }
    if cfg["password"] is None and pedir_senha:
        cfg["password"] = getpass.getpass(f"Senha do usuario {cfg['user']} no PostgreSQL: ")
    return cfg


def conectar(cfg: dict, dbname=None):
    import psycopg  # importado aqui para os testes rodarem sem o driver

    return psycopg.connect(
        host=cfg["host"], port=cfg["port"], user=cfg["user"], password=cfg["password"],
        dbname=dbname or cfg["dbname"], connect_timeout=10,
    )


# ----------------------------------------------------------------------------- leitura dos dados
def ler_talhoes(caminho) -> gpd.GeoDataFrame:
    """Le os talhoes, garante EPSG:31984, 2D, MultiPolygon e geometria valida."""
    g = gpd.read_file(caminho)
    if g.crs is None:
        raise ValueError("O GeoPackage de talhoes esta sem CRS definido.")
    g = g.to_crs(SRID)
    faltando = {"id", "cultura"} - set(g.columns)
    if faltando:
        raise ValueError(f"Colunas ausentes nos talhoes: {sorted(faltando)}")
    if g["id"].duplicated().any():
        raise ValueError("Ha ids de talhao duplicados.")

    def ajustar(geom):
        geom = force_2d(geom)
        if not geom.is_valid:
            geom = make_valid(geom)
        # make_valid pode devolver colecao; mantem apenas os poligonos
        poligonos = [p for p in getattr(geom, "geoms", [geom]) if p.geom_type in ("Polygon", "MultiPolygon")]
        partes = []
        for p in poligonos:
            partes.extend(p.geoms if p.geom_type == "MultiPolygon" else [p])
        if not partes:
            raise ValueError("Geometria sem poligono apos correcao.")
        return MultiPolygon(partes)

    g = g.copy()
    g["geometry"] = g.geometry.apply(ajustar)
    if "area_ha" not in g.columns:
        g["area_ha"] = g.geometry.area / 10000
    return g[["id", "cultura", "area_ha", "geometry"]]


def _nulo(v):
    if v is None:
        return None
    if isinstance(v, float) and np.isnan(v):
        return None
    if v is pd.NA or v is pd.NaT:
        return None
    return v


def ler_observacoes(caminho):
    """Le o CSV do Projeto 1. Devolve (cenas, observacoes) como listas de dicionarios com None no lugar de NaN."""
    df = pd.read_csv(caminho)
    obrigatorias = {"data", "cena", "id", "calibracao", *COLUNAS_OBS}
    faltando = obrigatorias - set(df.columns)
    if faltando:
        raise ValueError(f"Colunas ausentes no CSV: {sorted(faltando)}")
    df["aprovado"] = df["aprovado"].astype(str).str.strip().str.lower().isin(("true", "1", "sim"))
    df["data"] = pd.to_datetime(df["data"]).dt.date

    cenas = []
    for cena_id, grupo in df.groupby("cena", sort=True):
        p = grupo.iloc[0]
        cenas.append({
            "cena_id": cena_id, "data": p["data"],
            "offset_stac": _nulo(p.get("offset_stac")), "offset_usado": _nulo(p.get("offset_usado")),
            "calibracao": p["calibracao"],
        })
    obs = []
    for _, r in df.iterrows():
        linha = {"cena_id": r["cena"], "talhao_id": r["id"]}
        for c in COLUNAS_OBS:
            v = _nulo(r[c])
            if c in ("pixels_total", "pixels_validos") and v is not None:
                v = int(v)
            if c == "aprovado":
                v = bool(v)
            elif isinstance(v, (np.floating, np.integer)):
                v = v.item()
            linha[c] = v
        obs.append(linha)
    return cenas, obs


def parse_consultas(texto: str) -> list:
    """Separa o arquivo SQL em consultas: [(nome, titulo, sql), ...]."""
    blocos = re.split(r"^-- name:\s*", texto, flags=re.MULTILINE)[1:]
    consultas = []
    for b in blocos:
        linhas = b.splitlines()
        nome = linhas[0].strip()
        titulo, corpo = nome, []
        for ln in linhas[1:]:
            m = re.match(r"^-- titulo:\s*(.*)", ln)
            if m:
                titulo = m.group(1).strip()
            else:
                corpo.append(ln)
        sql = "\n".join(corpo).strip().rstrip(";")
        if sql:
            consultas.append((nome, titulo, sql))
    return consultas


# ----------------------------------------------------------------------------- banco
def criar(cfg: dict) -> None:
    import psycopg
    from psycopg import sql as psql

    with conectar(cfg, dbname="postgres") as con:
        con.autocommit = True
        existe = con.execute("SELECT 1 FROM pg_database WHERE datname = %s", (cfg["dbname"],)).fetchone()
        if not existe:
            # UTF8 + collation C funciona em qualquer sistema (inclusive Windows em portugues)
            con.execute(psql.SQL(
                "CREATE DATABASE {} ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C' TEMPLATE template0"
            ).format(psql.Identifier(cfg["dbname"])))
            print(f"Banco '{cfg['dbname']}' criado (UTF8).")
        else:
            print(f"Banco '{cfg['dbname']}' ja existe.")
    with conectar(cfg) as con:
        try:
            con.execute((SQL_DIR / "01_schema.sql").read_text(encoding="utf-8"))
        except psycopg.errors.UndefinedFile as e:
            raise SystemExit(f"A extensao PostGIS nao esta instalada neste servidor PostgreSQL: {e}")
        versao = con.execute("SELECT postgis_version()::text").fetchone()[0]
    print(f"Esquema 'agro' pronto. PostGIS {versao}.")


def carregar(cfg: dict, gpkg: Path, csv: Path) -> None:
    talhoes = ler_talhoes(gpkg)
    cenas, obs = ler_observacoes(csv)
    ids = set(talhoes["id"])
    sem_talhao = sorted({o["talhao_id"] for o in obs} - ids)
    if sem_talhao:
        raise SystemExit(f"O CSV tem talhoes que nao existem no GeoPackage: {sem_talhao}")

    with conectar(cfg) as con:
        with con.cursor() as cur:
            for _, t in talhoes.iterrows():
                cur.execute(
                    """INSERT INTO agro.talhao (id, cultura, area_ha, geom)
                       VALUES (%s, %s, %s, ST_Multi(ST_SetSRID(ST_GeomFromWKB(%s), %s)))
                       ON CONFLICT (id) DO UPDATE
                       SET cultura = EXCLUDED.cultura, area_ha = EXCLUDED.area_ha, geom = EXCLUDED.geom""",
                    (t["id"], t["cultura"], round(float(t["area_ha"]), 2), t.geometry.wkb, SRID),
                )
            cur.executemany(
                """INSERT INTO agro.cena (cena_id, data, offset_stac, offset_usado, calibracao)
                   VALUES (%(cena_id)s, %(data)s, %(offset_stac)s, %(offset_usado)s, %(calibracao)s)
                   ON CONFLICT (cena_id) DO UPDATE
                   SET data = EXCLUDED.data, offset_stac = EXCLUDED.offset_stac,
                       offset_usado = EXCLUDED.offset_usado, calibracao = EXCLUDED.calibracao""",
                cenas,
            )
            campos = ["cena_id", "talhao_id", *COLUNAS_OBS]
            atualiza = ", ".join(f"{c} = EXCLUDED.{c}" for c in COLUNAS_OBS)
            cur.executemany(
                f"""INSERT INTO agro.ndvi_observacao ({', '.join(campos)})
                    VALUES ({', '.join('%(' + c + ')s' for c in campos)})
                    ON CONFLICT (cena_id, talhao_id) DO UPDATE SET {atualiza}""",
                obs,
            )
        con.commit()
        n = {t: con.execute(f"SELECT count(*) FROM agro.{t}").fetchone()[0]
             for t in ("talhao", "cena", "ndvi_observacao")}
        con.execute("ANALYZE agro.talhao")
    print(f"Carga concluida: {n['talhao']} talhoes, {n['cena']} cenas, {n['ndvi_observacao']} observacoes.")


def consultas(cfg: dict, saida_csv: bool = False) -> None:
    texto = (SQL_DIR / "02_consultas.sql").read_text(encoding="utf-8")
    with conectar(cfg) as con:
        for nome, titulo, sql in parse_consultas(texto):
            cur = con.execute(sql)
            colunas = [d.name for d in cur.description]
            df = pd.DataFrame(cur.fetchall(), columns=colunas)
            print(f"\n== {titulo} ({nome}) ==")
            print(df.to_string(index=False) if len(df) else "(sem linhas)")
            if saida_csv:
                pasta = PROJ_DIR / "outputs"
                pasta.mkdir(exist_ok=True)
                df.to_csv(pasta / f"{nome}.csv", index=False)


# ----------------------------------------------------------------------------- linha de comando
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comando", choices=["criar", "carregar", "consultas", "tudo"])
    ap.add_argument("--gpkg", default=str(P1 / "data" / "private" / "talhoes.gpkg"))
    ap.add_argument("--csv", default=str(P1 / "outputs" / "tables" / "ndvi_por_talhao.csv"))
    ap.add_argument("--salvar-csv", action="store_true", help="grava o resultado de cada consulta em outputs/")
    a = ap.parse_args(argv)

    cfg = configuracao()
    try:
        if a.comando in ("criar", "tudo"):
            criar(cfg)
        if a.comando in ("carregar", "tudo"):
            for rotulo, p in (("GeoPackage de talhoes", a.gpkg), ("CSV de NDVI", a.csv)):
                if not Path(p).exists():
                    raise SystemExit(f"{rotulo} nao encontrado: {p}\nRode antes o Projeto 1 (preparar e rodar).")
            carregar(cfg, Path(a.gpkg), Path(a.csv))
        if a.comando in ("consultas", "tudo"):
            consultas(cfg, a.salvar_csv)
    except Exception as e:  # erros de conexao ficam legiveis em vez de um traceback longo
        if e.__class__.__module__.startswith("psycopg"):
            raise SystemExit(f"Erro no PostgreSQL ({e.__class__.__name__}): {e}")
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
