"""Atalho para o Projeto 1 (NDVI por talhao com Sentinel-2).

Rode SEMPRE da raiz do repositorio (a pasta onde esta este arquivo):

    python projeto1.py testar                          # testes (sem internet)
    python projeto1.py preparar "C:\\caminho\\talhoes_originais.gpkg"
    python projeto1.py rodar                           # baixa as cenas e calcula (precisa de internet)
    python projeto1.py grafico                         # gera o grafico da serie temporal
"""
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PROJ = RAIZ / "05-precision-agriculture" / "01-ndvi-sentinel2-talhoes"
SCRIPTS = PROJ / "scripts"


def executar(cmd, cwd):
    return subprocess.call([str(c) for c in cmd], cwd=str(cwd))


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "ajuda"):
        print(__doc__)
        return 0
    comando, extra = sys.argv[1], sys.argv[2:]
    py = sys.executable
    if comando == "testar":
        return executar([py, "-m", "pytest", PROJ / "tests", "-q", "-p", "no:cacheprovider", *extra], RAIZ)
    if comando == "preparar":
        if not extra:
            print('Informe o arquivo original:  python projeto1.py preparar "C:\\caminho\\talhoes_originais.gpkg"')
            return 2
        origem = Path(extra[0]).resolve()  # o script roda em outra pasta; usa caminho absoluto
        return executar([py, SCRIPTS / "preparar_talhoes.py", origem, *extra[1:]], PROJ)
    if comando == "rodar":
        return executar([py, SCRIPTS / "ndvi_pipeline.py", *extra], PROJ)
    if comando == "grafico":
        return executar([py, SCRIPTS / "plot_series.py", *extra], PROJ)
    print(f"Comando desconhecido: {comando}\n{__doc__}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
