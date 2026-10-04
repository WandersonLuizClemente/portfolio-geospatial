-- Projeto 2: esquema do banco espacial (PostgreSQL + PostGIS)
-- Pode ser executado varias vezes: usa IF NOT EXISTS.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS agro;

-- Talhoes (poligonos em SIRGAS 2000 / UTM 24S, EPSG:31984)
CREATE TABLE IF NOT EXISTS agro.talhao (
    id        text PRIMARY KEY,
    cultura   text NOT NULL,
    area_ha   numeric(10, 2),
    geom      geometry(MultiPolygon, 31984) NOT NULL,
    CONSTRAINT talhao_geom_valida CHECK (ST_IsValid(geom))
);
CREATE INDEX IF NOT EXISTS talhao_geom_gix ON agro.talhao USING gist (geom);

-- Cenas Sentinel-2 e como a calibracao (offset) foi decidida em cada uma
CREATE TABLE IF NOT EXISTS agro.cena (
    cena_id      text PRIMARY KEY,
    data         date NOT NULL,
    offset_stac  numeric,
    offset_usado numeric,
    calibracao   text NOT NULL
);
CREATE INDEX IF NOT EXISTS cena_data_idx ON agro.cena (data);

-- Uma linha por talhao e cena. Se foi reprovada, as estatisticas de NDVI ficam nulas.
CREATE TABLE IF NOT EXISTS agro.ndvi_observacao (
    cena_id         text    NOT NULL REFERENCES agro.cena (cena_id) ON DELETE CASCADE,
    talhao_id       text    NOT NULL REFERENCES agro.talhao (id)    ON DELETE CASCADE,
    pixels_total    integer NOT NULL CHECK (pixels_total >= 0),
    pixels_validos  integer NOT NULL CHECK (pixels_validos >= 0),
    pct_validos     numeric NOT NULL CHECK (pct_validos BETWEEN 0 AND 1),
    pct_fora_faixa  numeric NOT NULL CHECK (pct_fora_faixa BETWEEN 0 AND 1),
    red_dn_p50      numeric,
    nir_dn_p50      numeric,
    aprovado        boolean NOT NULL,
    motivo          text    NOT NULL CHECK (motivo IN ('ok', 'cobertura_baixa', 'calibracao')),
    ndvi_medio      numeric CHECK (ndvi_medio   BETWEEN -1 AND 1),
    ndvi_mediana    numeric CHECK (ndvi_mediana BETWEEN -1 AND 1),
    ndvi_desvio     numeric CHECK (ndvi_desvio  >= 0),
    ndvi_p10        numeric CHECK (ndvi_p10     BETWEEN -1 AND 1),
    ndvi_p90        numeric CHECK (ndvi_p90     BETWEEN -1 AND 1),
    PRIMARY KEY (cena_id, talhao_id),
    -- coerencia: aprovado <=> motivo 'ok' <=> tem NDVI
    CONSTRAINT aprovado_coerente CHECK (aprovado = (motivo = 'ok')),
    CONSTRAINT ndvi_so_se_aprovado CHECK (aprovado = (ndvi_medio IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS ndvi_obs_talhao_idx ON agro.ndvi_observacao (talhao_id);

-- Visao pronta para analise: so observacoes aprovadas, com cultura e data
CREATE OR REPLACE VIEW agro.v_ndvi_aprovado AS
SELECT o.talhao_id,
       t.cultura,
       c.data,
       o.ndvi_medio,
       o.ndvi_mediana,
       o.ndvi_desvio,
       o.pct_validos
FROM agro.ndvi_observacao o
JOIN agro.talhao t ON t.id = o.talhao_id
JOIN agro.cena   c ON c.cena_id = o.cena_id
WHERE o.aprovado;
