"""Atalho para o Projeto 3 (WebGIS: API + mapa dos talhoes).

Rode da raiz do repositorio, com o ambiente virtual ativo:

    python projeto3.py testar      # testes que nao precisam de banco
    python projeto3.py exportar    # grava docs/data/*.json a partir do banco (precisa do Projeto 2)
    python projeto3.py mapa        # abre o mapa estatico em http://127.0.0.1:8080 (sem banco)
    python projeto3.py servir      # sobe a API em http://127.0.0.1:8000 (precisa do banco)

A senha do PostgreSQL (exportar e servir) e pedida no terminal e nunca e gravada.
"""
import getpass
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PROJ = RAIZ / "07-webgis" / "01-mapa-talhoes"


def com_senha() -> dict:
    env = dict(os.environ)
    if "PGPASSWORD" not in env:
        env["PGPASSWORD"] = getpass.getpass(f"Senha do usuario {env.get('PGUSER', 'postgres')} no PostgreSQL: ")
    return env


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "ajuda"):
        print(__doc__)
        return 0
    comando, extra = sys.argv[1], sys.argv[2:]
    py = str(sys.executable)
    if comando == "testar":
        return subprocess.call([py, "-m", "pytest", str(PROJ / "tests"), "-q", "-p", "no:cacheprovider", *extra],
                               cwd=str(RAIZ))
    if comando == "exportar":
        return subprocess.call([py, str(PROJ / "scripts" / "exportar_estatico.py"), *extra], cwd=str(PROJ),
                               env=com_senha())
    if comando == "mapa":
        print("Mapa em http://127.0.0.1:8080  (Ctrl+C para parar)")
        return subprocess.call([py, "-m", "http.server", "8080", "--bind", "127.0.0.1"], cwd=str(PROJ / "docs"))
    if comando == "servir":
        print("API em http://127.0.0.1:8000/docs  |  mapa com a API: http://127.0.0.1:8080/?api=http://127.0.0.1:8000")
        return subprocess.call([py, "-m", "uvicorn", "api.main:criar_app_padrao", "--factory",
                                "--host", "127.0.0.1", "--port", "8000", *extra], cwd=str(PROJ), env=com_senha())
    print(f"Comando desconhecido: {comando}\n{__doc__}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
