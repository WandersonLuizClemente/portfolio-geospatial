# Projeto 1: Monitoramento de NDVI por talhão com Sentinel-2

> **PROJETO DEMONSTRATIVO** · Status: **Em desenvolvimento**  
> Imagens públicas (Sentinel-2) e 5 talhões de **áreas reais com uso autorizado**, anonimizados (T01 a T05).
> Os limites **não são publicados** neste repositório. Não usa dados de produção, imagens de clientes nem dados pessoais.

## 1. Problema

Acompanhar a saúde da vegetação por talhão ao longo do tempo exige processar imagens de satélite manualmente, o que é lento e difícil de repetir.

## 2. Objetivo

Um pipeline em Python que, para 5 talhões de culturas diferentes, obtém imagens Sentinel-2, valida a calibração, calcula o NDVI e gera estatísticas por talhão e data de forma reproduzível.

## 3. Dados

| Item | Descrição |
|------|-----------|
| Imagens | Sentinel-2 L2A (10 m), por catálogo STAC aberto (Earth Search) |
| Talhões | 5 polígonos (T01 a T05): café (T01, T03), coco (T02), eucalipto (T04) e pasto (T05); de 53 a 393 ha. Não publicados |
| Região | Linhares, Espírito Santo |
| Período | 01/10/2025 a 30/09/2026 |
| Sistema de referência | SIRGAS 2000 / UTM 24S (EPSG:31984) |

## 4. Tratamento

1. Leitura apenas da janela de cada talhão (COG), sem baixar a cena inteira.
2. **Validação da calibração, por cena:** a reflectância é `DN × 0,0001 + offset`. O offset do catálogo (−0,1 para baseline ≥ 04.00) só é aceito se não gerar reflectância negativa nos pixels válidos; caso contrário, o pipeline testa outros offsets e registra o que usou (colunas `offset_stac`, `offset_usado`, `calibracao`). A decisão exige ao menos 500 pixels limpos na cena; com menos, a cena não é aprovada (`cobertura_baixa`).

   **Achado nos dados:** o catálogo declara offset −0,1, mas em 47 das 51 cenas do período os DN não trazem o +1000 embutido (vermelho com mediana ≈ 500). Aplicar −0,1 nelas gera reflectância negativa e NDVI saturado em ±1. Por isso o offset é validado pelos dados, cena a cena, e nunca assumido.
3. Máscara de nuvem e sombra pela banda SCL: entram só vegetação (4) e solo nu (5).
4. NDVI **sem recorte**: pixels com NDVI fora de [−1, 1] são descartados e contados (`pct_fora_faixa`). Talhão-data com mais de 5% deles é reprovado.
5. Talhão-data com menos de 80% de pixels válidos (padrão de `--min-validos`, ajustável) é reprovado (`motivo = cobertura_baixa`).

## 5. Banco de dados

Saídas em CSV. A carga em PostGIS é feita no Projeto 2.

## 6. Análise

NDVI = (NIR − RED) / (NIR + RED), com as bandas B08 e B04. Média, mediana, desvio-padrão e percentis 10 e 90 por talhão e data.

## 7. Automação

`python projeto1.py rodar` executa o fluxo completo: busca das cenas, validação, cálculo e CSV.

## 8. Machine Learning

Não aplicável a este projeto. Não há problema que justifique ML aqui. Ele entra no Projeto 5.

## 9. Visualização

Série temporal de NDVI por talhão (`python projeto1.py grafico`).

## 10. WebGIS

Aplicação possível, desenvolvida no Projeto 3.

## 11. Resultado

Período 01/10/2025 a 30/09/2026, cinco talhões, 51 cenas Sentinel-2 L2A (tile 24KUD), exigindo no mínimo 80% de pixels válidos por talhão e data.

- 255 combinações talhão-data; **105 aprovadas (41%)**. As demais foram reprovadas por nuvem/sombra.
- Em 47 das 51 cenas o offset do catálogo (−0,1) foi rejeitado pelos dados e usado 0,0.

| Cultura | Observações aprovadas | NDVI médio por data: p10 / mediana / p90 |
|---|---|---|
| Café | 46 | 0,50 / 0,64 / 0,75 |
| Coco | 19 | 0,65 / 0,78 / 0,82 |
| Eucalipto | 18 | 0,79 / 0,84 / 0,88 |
| Pasto | 22 | 0,64 / 0,74 / 0,84 |

Eucalipto e coco apresentam os maiores NDVI, e o café os menores e mais variáveis, coerente com a mistura de solo e copa no pixel de 10 m. Interpretação sazonal: [INFORMAÇÃO A PREENCHER]

## 12. Valor

Indicar quais talhões merecem atenção primeiro, apoiando a decisão de um agrônomo. Este projeto **não** faz diagnóstico agronômico.

## Limitações

- Resolução de 10 m: não substitui drone para análise de linhas de plantio.
- Coco e café têm copas que misturam solo e vegetação no pixel de 10 m; eucalipto e pasto são mais homogêneos.
- Cobertura de nuvens reduz o número de datas úteis, de forma desigual ao longo do ano.
- Em alguns meses (ex.: março e maio) restam poucas observações aprovadas, e quedas isoladas na série podem ser resíduo de nuvem fina que a máscara SCL não pegou.
- Não há interpretação agronômica dos resultados.

## Como reproduzir (Windows, CMD, na raiz do repositório)

```cmd
python projeto1.py testar
python projeto1.py preparar "C:\caminho\seus_talhoes_originais.gpkg"
python projeto1.py rodar
python projeto1.py grafico
```

O arquivo de talhões precisa ter um polígono por talhão. O comando `preparar` cria `data/private/talhoes.gpkg` com os campos `id`, `cultura` e `area_ha`; use `--culturas` para informar a cultura de cada polígono, na ordem do arquivo.
