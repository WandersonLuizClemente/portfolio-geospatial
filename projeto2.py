"""Atalho para o Projeto 2 (NDVI no PostgreSQL/PostGIS).

Rode da raiz do repositorio, com o ambiente virtual ativo:

    python projeto2.py testar       # testes que nao precisam de banco
    python projeto2.py criar        # cria o banco portfolio_geo, o PostGIS e as tabelas
    python projeto2.py carregar     # grava talhoes e NDVI do Projeto 1 (pode repetir)
    python projeto2.py consultas    # roda as consultas SQL e mostra os resultados
    python projeto2.py tudo         # criar + carregar + consultas

Conexao: variaveis PGHOST, PGPORT, PGDATABASE (padrao portfolio_geo), PGUSER (padrao postgres).
A senha e pedida no terminal (ou lida de PGPASSWORD) e nunca e gravada.
"""
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PROJ = RAIZ / "06-postgis" / "01-ndvi-postgis"


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "ajuda"):
        print(__doc__)
        return 0
    comando, extra = sys.argv[1], sys.argv[2:]
    py = str(sys.executable)
    if comando == "testar":
        cmd = [py, "-m", "pytest", str(PROJ / "tests"), "-q", "-p", "no:cacheprovider", *extra]
        return subprocess.call(cmd, cwd=str(RAIZ))
    if comando in ("criar", "carregar", "consultas", "tudo"):
        cmd = [py, str(PROJ / "scripts" / "carregar_postgis.py"), comando, *extra]
        return subprocess.call(cmd, cwd=str(RAIZ))
    print(f"Comando desconhecido: {comando}\n{__doc__}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
