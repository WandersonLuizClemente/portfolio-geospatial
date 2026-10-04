"""Acesso ao banco (PostGIS) do Projeto 2. Todas as consultas usam parametros do driver."""
import os
from typing import Optional


def configuracao(env=None) -> dict:
    env = os.environ if env is None else env
    return {
        "host": env.get("PGHOST", "localhost"),
        "port": int(env.get("PGPORT", "5432")),
        "dbname": env.get("PGDATABASE", "portfolio_geo"),
        "user": env.get("PGUSER", "postgres"),
        "password": env.get("PGPASSWORD", ""),
    }


def _num(v):
    return None if v is None else float(v)


class RepositorioPostgis:
    def __init__(self, cfg: Optional[dict] = None):
        self.cfg = cfg or configuracao()

    def _conectar(self):
        import psycopg  # importado aqui para os testes rodarem sem o driver

        c = self.cfg
        return psycopg.connect(host=c["host"], port=c["port"], dbname=c["dbname"], user=c["user"],
                               password=c["password"], connect_timeout=5)

    def talhoes(self) -> dict:
        """Talhoes como GeoJSON (FeatureCollection) em WGS 84, como o Leaflet espera."""
        sql = """SELECT id, cultura, area_ha,
                        ST_AsGeoJSON(ST_Transform(geom, 4326), 6)::json AS geom
                 FROM agro.talhao ORDER BY id"""
        with self._conectar() as con:
            linhas = con.execute(sql).fetchall()
        feats = [{"type": "Feature", "geometry": g,
                  "properties": {"id": i, "cultura": c, "area_ha": _num(a)}} for i, c, a, g in linhas]
        return {"type": "FeatureCollection", "features": feats}

    def existe_talhao(self, talhao_id: str) -> bool:
        with self._conectar() as con:
            return con.execute("SELECT 1 FROM agro.talhao WHERE id = %s", (talhao_id,)).fetchone() is not None

    def ndvi(self, talhao_id: Optional[str] = None, inicio=None, fim=None) -> list:
        """Observacoes aprovadas de NDVI, mais antigas primeiro."""
        sql = """SELECT talhao_id, cultura, data, ndvi_medio, ndvi_mediana, pct_validos
                 FROM agro.v_ndvi_aprovado
                 WHERE (%(t)s::text IS NULL OR talhao_id = %(t)s::text)
                   AND (%(i)s::date IS NULL OR data >= %(i)s::date)
                   AND (%(f)s::date IS NULL OR data <= %(f)s::date)
                 ORDER BY data, talhao_id"""
        with self._conectar() as con:
            linhas = con.execute(sql, {"t": talhao_id, "i": inicio, "f": fim}).fetchall()
        return [{"talhao_id": t, "cultura": c, "data": d.isoformat(), "ndvi_medio": _num(m),
                 "ndvi_mediana": _num(md), "pct_validos": _num(p)} for t, c, d, m, md, p in linhas]

    def vizinhos(self, talhao_id: str, km: float) -> list:
        """Talhoes a ate `km` quilometros (usa o indice GIST via ST_DWithin)."""
        sql = """SELECT b.id, b.cultura, round(ST_Distance(a.geom, b.geom)::numeric, 0)
                 FROM agro.talhao a
                 JOIN agro.talhao b ON a.id <> b.id AND ST_DWithin(a.geom, b.geom, %(m)s)
                 WHERE a.id = %(t)s
                 ORDER BY 3, 1"""
        with self._conectar() as con:
            linhas = con.execute(sql, {"t": talhao_id, "m": km * 1000.0}).fetchall()
        return [{"id": i, "cultura": c, "distancia_m": _num(d)} for i, c, d in linhas]
