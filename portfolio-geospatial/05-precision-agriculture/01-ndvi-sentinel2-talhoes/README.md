# Projeto 1: Monitoramento de NDVI por talhão com Sentinel-2

> **PROJETO DEMONSTRATIVO** · Status: **Em desenvolvimento**  
> Imagens públicas (Sentinel-2) e 5 talhões de **áreas reais com uso autorizado**, anonimizados (T01 a T05).
> Autorização: [INFORMAÇÃO A PREENCHER]. Não usa dados de produção, imagens de clientes nem dados pessoais.

## 1. Problema

Acompanhar a saúde da vegetação por talhão ao longo do tempo exige processar imagens de satélite manualmente, o que é lento e difícil de repetir. Este projeto mostra como automatizar o processo.

## 2. Objetivo

Construir um pipeline em Python que, para 5 talhões de culturas diferentes, obtém imagens Sentinel-2, calcula o NDVI e gera estatísticas por talhão, séries temporais e mapas de forma reproduzível.

## 3. Dados

| Item | Descrição |
|------|-----------|
| Imagens | Sentinel-2 L2A (10 m), obtidas por catálogo STAC aberto |
| Talhões | 5 polígonos (T01 a T05), áreas reais anonimizadas: café (T01, T03), coco (T02), eucalipto (T04) e pasto (T05); de 53 a 393 ha |
| Região | Linhares, Espírito Santo |
| Período | [INFORMAÇÃO A PREENCHER] |
| Sistema de referência | SIRGAS 2000 / UTM 24S (EPSG:31984) |

## 4. Tratamento

Seleção de cenas, máscara de nuvens (banda SCL), recorte pelos talhões e padronização do sistema de referência.

## 5. Banco de dados

Neste projeto as saídas ficam em GeoPackage e CSV. A carga em PostGIS é feita no Projeto 2.

## 6. Análise

NDVI = (NIR − RED) / (NIR + RED), com as bandas B08 e B04. Estatísticas zonais por talhão (média, mínimo, máximo, desvio-padrão), série temporal e sinalização de talhões abaixo da média da região.

## 7. Automação

Scripts que executam o fluxo completo, da busca das imagens à geração dos mapas.

## 8. Machine Learning

Não aplicável a este projeto. Não há problema que justifique ML aqui. Ele entra no Projeto 5.

## 9. Visualização

Mapas de NDVI por data, mapa temático por talhão e gráfico de série temporal.

## 10. WebGIS

Aplicação possível, desenvolvida no Projeto 3.

## 11. Resultado

[INFORMAÇÃO A PREENCHER]

## 12. Valor

Indicar quais talhões merecem atenção primeiro, apoiando a decisão de um agrônomo. Este projeto **não** faz diagnóstico agronômico.

## Limitações

- Coco e café têm copas que misturam solo e vegetação no pixel de 10 m; eucalipto e pasto são mais homogêneos. A comparação entre culturas deve considerar isso.
- Resolução de 10 m: não substitui drone para análise de linhas de plantio.
- Cobertura de nuvens pode reduzir o número de cenas úteis.
- Não há interpretação agronômica dos resultados.

## Como reproduzir

```bash
# na raiz do repositório, com o ambiente virtual ativo
pip install -r requirements.txt

# 1) testes da lógica de NDVI (rodam sem internet)
python -m pytest 05-precision-agriculture/01-ndvi-sentinel2-talhoes/tests -q

# 2) pipeline (precisa de internet; lê só as janelas dos talhões)
cd 05-precision-agriculture/01-ndvi-sentinel2-talhoes
python scripts/ndvi_pipeline.py --talhoes data/public/talhoes.gpkg --inicio 2025-10-01 --fim 2026-09-30

# 3) gráfico da série temporal
python scripts/plot_series.py
```

O arquivo de talhões precisa ter as colunas `id` e `cultura` e um sistema de referência definido.

### Decisões de método

- **Máscara de nuvem:** banda SCL; só entram pixels de vegetação (4) e solo nu (5).
- **Cobertura mínima:** talhão com menos de 50% de pixels válidos na data é registrado, mas sem estatística.
- **Reflectância:** aplica escala e *offset* declarados em cada cena (baseline 04.00 em diante usa −0,1).
- **Janelas COG:** lê apenas o retângulo de cada talhão, sem baixar a cena inteira.
