# Projeto 3: Mapa web de NDVI por talhão (WebGIS)

> **PROJETO DEMONSTRATIVO** · Status: **Em desenvolvimento**  
> Usa os dados do [Projeto 1](../../05-precision-agriculture/01-ndvi-sentinel2-talhoes/) e do banco do [Projeto 2](../../06-postgis/01-ndvi-postgis/): imagens públicas Sentinel-2 e 5 talhões de áreas reais com uso autorizado, anonimizados (T01 a T05).

## 1. Problema

Resultados em CSV e em banco de dados não são fáceis de explorar por quem não programa. Um agrônomo ou gestor precisa ver, num mapa, quais talhões estão mais ou menos vigorosos em cada data.

## 2. Objetivo

Um mapa interativo em que cada talhão é colorido pelo NDVI da data escolhida, com série temporal ao clicar, e uma API que serve os mesmos dados a partir do PostGIS.

## 3. Dados

| Origem | Conteúdo |
|---|---|
| `agro.talhao` (Projeto 2) | 5 polígonos, convertidos para WGS 84 na saída |
| `agro.v_ndvi_aprovado` (Projeto 2) | NDVI médio de cada talhão e data, só observações aprovadas |

## 4. Tratamento

- A API converte a geometria de SIRGAS 2000 / UTM 24S (EPSG:31984) para WGS 84 (EPSG:4326) com `ST_Transform`, que é o que o Leaflet espera.
- Só observações aprovadas (≥ 80% de pixels válidos) chegam ao mapa. Datas sem dado aparecem em cinza, e não como zero.

## 5. Banco de dados

Leitura do esquema `agro` criado no Projeto 2. A API nunca escreve no banco.

## 6. Análise

Consulta espacial `ST_DWithin` (talhões a até X km, com índice GIST) exposta em `/vizinhos/{talhao}`.

## 7. Automação

`python projeto3.py exportar` gera arquivos estáticos a partir do banco; `python projeto3.py servir` sobe a API.

## 8. Machine Learning

Não aplicável.

## 9. Visualização e WebGIS

```
PostGIS ──► API FastAPI ──► GeoJSON/JSON ──► mapa Leaflet
   └──► exportar ──► docs/data/*.json ──► mesmo mapa, sem servidor
```

| Endpoint | Resposta |
|---|---|
| `GET /talhoes` | talhões em GeoJSON |
| `GET /ndvi?talhao=T01&inicio=2026-01-01&fim=2026-06-30` | observações aprovadas (filtros opcionais) |
| `GET /vizinhos/T01?km=5` | talhões a até 5 km |
| `GET /saude` | verificação de funcionamento |
| `GET /docs` | documentação interativa gerada pelo FastAPI |

O mapa tem controle de data, legenda, tabela de talhões e gráfico da série temporal. Funciona em tela de celular e em modo escuro.

Cuidados de segurança: as consultas usam parâmetros do driver (sem montar SQL por concatenação), a API só aceita GET, e o texto dos dados entra na página sem `innerHTML`.

## 10. Resultado

[INFORMAÇÃO A PREENCHER: captura de tela do mapa e link do GitHub Pages]

## 11. Valor

Qualquer pessoa vê no navegador, sem instalar nada, onde e quando o NDVI dos talhões variou.

## 12. Publicação

O mapa estático fica em `docs/` e pode ser publicado no GitHub Pages: em **Settings → Pages**, escolha **Deploy from a branch**, branch `main`, pasta **/ (root)**. O endereço é
`https://wandersonluizclemente.github.io/portfolio-geospatial/07-webgis/01-mapa-talhoes/docs/`.

## Limitações

- O mapa estático mostra o retrato dos dados no dia da exportação; para atualizar, rode `exportar` de novo.
- Não há autenticação: a API é de leitura e destinada a demonstração local.
- Sem interpretação agronômica; resolução de 10 m.

## Como reproduzir (Windows, CMD, na raiz do repositório)

Requisitos: ambiente virtual ativo (`pip install -r requirements.txt`) e o banco do Projeto 2 carregado.

```cmd
python projeto3.py testar
python projeto3.py exportar
python projeto3.py mapa
```

Abra `http://127.0.0.1:8080`. Para usar a API em vez dos arquivos, abra um segundo CMD:

```cmd
python projeto3.py servir
```

e acesse o mapa em `http://127.0.0.1:8080/?api=http://127.0.0.1:8000`. A documentação da API fica em `http://127.0.0.1:8000/docs`. A senha do PostgreSQL é pedida no terminal e nunca é gravada.

## Estrutura

```
07-webgis/01-mapa-talhoes/
├── api/main.py, api/repo.py        API FastAPI e acesso ao banco
├── scripts/exportar_estatico.py    gera docs/data/*.json
├── docs/index.html, docs/app.js    mapa Leaflet
├── docs/vendor/leaflet/            Leaflet 1.9.4 (licença BSD-2)
├── docs/data/                      dados exportados
└── tests/test_api.py
```

Mapa base © colaboradores do OpenStreetMap.
