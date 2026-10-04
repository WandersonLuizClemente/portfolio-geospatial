# Projeto 2: NDVI por talhão em PostgreSQL + PostGIS

> **PROJETO DEMONSTRATIVO** · Status: **Em desenvolvimento**  
> Usa os resultados do [Projeto 1](../../05-precision-agriculture/01-ndvi-sentinel2-talhoes/): imagens públicas Sentinel-2 e 5 talhões anonimizados (T01 a T05). Os limites dos talhões não são publicados neste repositório.

## 1. Problema

Os resultados do Projeto 1 ficam em um CSV e em um GeoPackage. Arquivos soltos não garantem integridade (um NDVI de 1,5, um talhão que não existe), não permitem consultas espaciais e não servem de base para um mapa web.

## 2. Objetivo

Um banco espacial com esquema documentado, carga repetível a partir dos arquivos do Projeto 1 e consultas SQL que respondam perguntas sobre os talhões, o NDVI e a qualidade das observações.

## 3. Dados

| Origem | Conteúdo | Destino no banco |
|---|---|---|
| `talhoes.gpkg` (Projeto 1) | 5 polígonos, EPSG:31984 | `agro.talhao` |
| `ndvi_por_talhao.csv` (Projeto 1) | uma linha por talhão e cena | `agro.cena` e `agro.ndvi_observacao` |

## 4. Tratamento

- Geometrias convertidas para 2D e `MultiPolygon`, no EPSG:31984; inválidas são corrigidas antes da carga.
- Células vazias do CSV viram `NULL` (e não texto ou zero).
- Recusa a carga se o CSV citar um talhão que não existe no GeoPackage, se faltarem colunas ou se houver ids duplicados.

## 5. Banco de dados

```
agro.talhao (id PK, cultura, area_ha, geom MultiPolygon 31984, índice GIST)
    ▲
agro.ndvi_observacao (cena_id, talhao_id PK, pixels, pct_validos, aprovado, motivo, ndvi_*)
    ▼
agro.cena (cena_id PK, data, offset_stac, offset_usado, calibracao)

agro.v_ndvi_aprovado   -- visão com cultura, data e NDVI das observações aprovadas
```

Restrições que o banco garante sozinho: NDVI entre −1 e 1, `aprovado` coerente com `motivo`, NDVI só quando aprovado, geometria válida e chaves estrangeiras. Esquema completo em [`sql/01_schema.sql`](sql/01_schema.sql).

## 6. Análise

Sete consultas em [`sql/02_consultas.sql`](sql/02_consultas.sql):

1. observações aprovadas e NDVI médio por cultura;
2. NDVI médio mensal por cultura;
3. variação do NDVI por talhão entre dezembro–abril e junho–setembro;
4. taxa de aprovação e motivos de reprovação por talhão;
5. área, perímetro e centroide calculados pelo banco (`ST_Area`, `ST_Perimeter`, `ST_Centroid`);
6. talhões a até 5 km de cada talhão (`ST_DWithin`, usando o índice GIST);
7. como o offset de calibração foi decidido nas cenas.

## 7. Automação

`python projeto2.py tudo` cria o banco, carrega e roda as consultas. A carga usa `INSERT ... ON CONFLICT DO UPDATE`, então pode ser repetida sem duplicar dados.

## 8. Machine Learning

Não aplicável. Este projeto prepara a base de dados para os projetos seguintes.

## 9. Visualização

Resultados das consultas no terminal; com `--salvar-csv`, cada resultado é gravado em `outputs/`.

## 10. WebGIS

O banco é a fonte do Projeto 3 (mapa interativo e API por talhão).

## 11. Resultado

[INFORMAÇÃO A PREENCHER: tabela da consulta 1 e da consulta 4 obtidas com os dados reais do Projeto 1]

## 12. Valor

Dados de talhão e NDVI centralizados, consistentes e consultáveis por qualquer ferramenta (QGIS, Python, API), em vez de arquivos soltos.

## Limitações

- Carga em lote a partir de arquivos; não há ingestão contínua de novas cenas.
- Uma única tabela de observações por talhão e cena; estatísticas por pixel não são armazenadas.
- Sem controle de usuários e permissões além do padrão do PostgreSQL.

## Como reproduzir (Windows, CMD, na raiz do repositório)

Requisitos: Python com o ambiente virtual ativo (`pip install -r requirements.txt`), PostgreSQL com PostGIS instalado e os arquivos do Projeto 1 gerados.

```cmd
python projeto2.py testar
python projeto2.py tudo
```

A senha do PostgreSQL é pedida no terminal e nunca é gravada. Para outro servidor ou banco, defina antes `PGHOST`, `PGPORT`, `PGDATABASE` ou `PGUSER`. Os testes de integração com o banco rodam com `PG_INTEGRACAO=1`.

## Estrutura

```
06-postgis/01-ndvi-postgis/
├── sql/01_schema.sql        esquema, índices e restrições
├── sql/02_consultas.sql     consultas de exemplo
├── scripts/carregar_postgis.py
├── scripts/proj_env.py      isola PROJ/GDAL do PostgreSQL no Windows
├── tests/test_carga.py
└── outputs/                 resultados (não versionados)
```
