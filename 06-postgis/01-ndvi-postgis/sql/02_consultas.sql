-- Projeto 2: consultas de exemplo.
-- Cada consulta comeca com "-- name: <identificador>" e a linha seguinte "-- titulo: ...".

-- name: q1_resumo_por_cultura
-- titulo: Observacoes aprovadas e NDVI medio por cultura
SELECT cultura,
       count(*)                          AS observacoes,
       round(avg(ndvi_medio), 3)         AS ndvi_medio,
       round(min(ndvi_medio), 3)         AS ndvi_min,
       round(max(ndvi_medio), 3)         AS ndvi_max
FROM agro.v_ndvi_aprovado
GROUP BY cultura
ORDER BY ndvi_medio DESC;

-- name: q2_ndvi_mensal_por_cultura
-- titulo: NDVI medio mensal por cultura
SELECT to_char(date_trunc('month', data), 'YYYY-MM') AS mes,
       cultura,
       count(*)                  AS observacoes,
       round(avg(ndvi_medio), 3) AS ndvi_medio
FROM agro.v_ndvi_aprovado
GROUP BY 1, 2
ORDER BY 1, 2;

-- name: q3_variacao_entre_periodos
-- titulo: Variacao do NDVI por talhao, de dezembro-abril para junho-setembro
WITH periodos AS (
    SELECT talhao_id,
           cultura,
           avg(ndvi_medio) FILTER (WHERE extract(month FROM data) IN (12, 1, 2, 3, 4)) AS ndvi_dez_abr,
           avg(ndvi_medio) FILTER (WHERE extract(month FROM data) IN (6, 7, 8, 9))     AS ndvi_jun_set
    FROM agro.v_ndvi_aprovado
    GROUP BY talhao_id, cultura
)
SELECT talhao_id,
       cultura,
       round(ndvi_dez_abr, 3)                AS ndvi_dez_abr,
       round(ndvi_jun_set, 3)                AS ndvi_jun_set,
       round(ndvi_jun_set - ndvi_dez_abr, 3) AS variacao
FROM periodos
ORDER BY variacao;

-- name: q4_aprovacao_por_talhao
-- titulo: Taxa de aprovacao e motivos de reprovacao por talhao
SELECT talhao_id,
       count(*)                                              AS observacoes,
       count(*) FILTER (WHERE motivo = 'ok')                 AS aprovadas,
       count(*) FILTER (WHERE motivo = 'cobertura_baixa')    AS cobertura_baixa,
       count(*) FILTER (WHERE motivo = 'calibracao')         AS calibracao,
       round(100.0 * count(*) FILTER (WHERE aprovado) / count(*), 1) AS pct_aprovadas
FROM agro.ndvi_observacao
GROUP BY talhao_id
ORDER BY talhao_id;

-- name: q5_geometria_calculada
-- titulo: Area, perimetro e centroide calculados pelo banco
SELECT id,
       cultura,
       area_ha                                              AS area_ha_cadastrada,
       round((ST_Area(geom) / 10000)::numeric, 2)           AS area_ha_calculada,
       round(ST_Perimeter(geom)::numeric, 0)                AS perimetro_m,
       round(ST_Y(ST_Transform(ST_Centroid(geom), 4326))::numeric, 5) AS lat_centroide,
       round(ST_X(ST_Transform(ST_Centroid(geom), 4326))::numeric, 5) AS lon_centroide
FROM agro.talhao
ORDER BY id;

-- name: q6_vizinhos_ate_5km
-- titulo: Talhoes a ate 5 km de cada talhao (consulta espacial com indice GIST)
SELECT a.id                                   AS talhao,
       b.id                                   AS vizinho,
       b.cultura                              AS cultura_vizinho,
       round((ST_Distance(a.geom, b.geom))::numeric, 0) AS distancia_m
FROM agro.talhao a
JOIN agro.talhao b
  ON a.id <> b.id
 AND ST_DWithin(a.geom, b.geom, 5000)
ORDER BY a.id, distancia_m;

-- name: q7_calibracao_das_cenas
-- titulo: Como o offset de calibracao foi decidido nas cenas
SELECT calibracao,
       offset_usado,
       count(*) AS cenas
FROM agro.cena
GROUP BY calibracao, offset_usado
ORDER BY cenas DESC;
