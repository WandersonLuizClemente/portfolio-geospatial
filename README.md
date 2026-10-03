# Portfólio Geoespacial

**Transformar dados geoespaciais em inteligência para tomada de decisão.**

Repositório de projetos de **SIG/GIS, Python, dados geoespaciais, banco de dados espacial (PostGIS), WebGIS e agricultura de precisão**, com foco em problemas reais de agro e meio ambiente.

> **PROJETO DEMONSTRATIVO:** os projetos deste repositório são demonstrativos e usam
> **dados públicos** (por exemplo, imagens Sentinel-2). No Projeto 1, os limites de talhões
> são de **áreas reais com uso autorizado**, anonimizadas. Nenhum projeto contém imagens de
> clientes, dados de produção ou dados pessoais.

## Autor

**Wanderson Luiz** · Analista de Dados Geoespaciais · Drone, GIS e Python · Agro e Ambiental  
LinkedIn: [linkedin.com/in/wluizclemente](https://www.linkedin.com/in/wluizclemente)

A experiência profissional está descrita no LinkedIn. Este repositório reúne apenas projetos construídos para demonstrar competências de forma pública e reproduzível.

## Projetos

| # | Projeto | Área | Status |
|---|---------|------|--------|
| 1 | [Monitoramento de NDVI por talhão com Sentinel-2](05-precision-agriculture/01-ndvi-sentinel2-talhoes/) | Agricultura de precisão, GIS, Python | Em desenvolvimento |
| 2 | Banco geoespacial: ETL para PostGIS e consultas espaciais | PostGIS, automação | Planejado |
| 3 | WebGIS: mapa interativo e API por talhão | WebGIS, API | Planejado |
| 4 | Falhas de plantio em ortomosaico público | Drone, visão computacional | Planejado |
| 5 | Machine Learning com avaliação por métricas | ML geoespacial | Planejado |
| 6 | Monitoramento ambiental com Google Earth Engine | Ambiental, sensoriamento remoto | Planejado |
| 7 | Qualidade posicional: RTK/PPK/GCP e erro (RMSE) | Fotogrametria | Planejado |

## Padrão de cada projeto

Cada projeto segue a mesma estrutura de documentação:

**Problema → Objetivo → Dados → Tratamento → Banco de dados → Análise → Automação → Machine Learning (quando justificado) → Visualização → WebGIS → Resultado → Valor**

e inclui README próprio, código organizado, resultado visual (mapa, gráfico ou dashboard) e instruções para reproduzir.

## Estrutura do repositório

```text
portfolio-geospatial/
├── 01-gis/
├── 02-python/
├── 03-geospatial-data-science/
├── 04-machine-learning/
├── 05-precision-agriculture/
├── 06-postgis/
├── 07-webgis/
├── datasets/
├── notebooks/
├── scripts/
├── maps/
├── dashboards/
└── README.md
```

## Como preparar o ambiente

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux/macOS:  source .venv/bin/activate
pip install -r requirements.txt
python scripts/check_env.py
```

## Licença

Distribuído sob a licença MIT. Veja o arquivo [LICENSE](LICENSE).
