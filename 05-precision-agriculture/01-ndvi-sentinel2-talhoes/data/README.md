# Dados do projeto

- `public/`: dados que podem ser publicados. E versionado.
- `private/`: uso local (limites reais dos talhoes). **Ignorado pelo Git. Nunca publicar.**
- `raw/` e `cache/`: imagens baixadas. Ignoradas pelo Git; o script baixa de novo.

O arquivo `private/talhoes.gpkg` e criado por `python projeto1.py preparar "<arquivo original>"`.
