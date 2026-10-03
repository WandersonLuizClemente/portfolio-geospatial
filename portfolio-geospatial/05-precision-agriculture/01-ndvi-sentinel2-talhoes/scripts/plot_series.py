"""Gráfico da série temporal de NDVI por talhão.

Uso:
    python scripts/plot_series.py --csv outputs/tables/ndvi_por_talhao.csv
Saída: outputs/maps/serie_temporal_ndvi.png
"""
import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

# Uma cor por cultura (distinguíveis entre si); talhões da mesma cultura mudam o traço.
CORES = {"cafe": "#7a4b2a", "coco": "#2a9d8f", "eucalipto": "#1d6fa5", "pasto": "#d98c1f"}
TRACOS = ["-", "--", ":"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="outputs/tables/ndvi_por_talhao.csv")
    ap.add_argument("--saida", default="outputs/maps/serie_temporal_ndvi.png")
    a = ap.parse_args()

    df = pd.read_csv(a.csv, parse_dates=["data"])
    ok = df[df["aprovado"]].copy()
    if ok.empty:
        raise SystemExit("Nenhuma observação aprovada para plotar.")

    fig, ax = plt.subplots(figsize=(11, 5.5))
    contagem = {}
    for tid, g in ok.sort_values("data").groupby("id"):
        cultura = g["cultura"].iloc[0]
        k = contagem.get(cultura, 0)
        contagem[cultura] = k + 1
        ax.plot(g["data"], g["ndvi_medio"], TRACOS[k % 3], marker="o", markersize=3.5,
                linewidth=1.8, color=CORES.get(cultura, "#555555"), label=f"{tid} · {cultura}")
    ax.set_ylabel("NDVI médio do talhão")
    ax.set_ylim(0, 1)
    ax.set_title("NDVI por talhão · Sentinel-2 L2A · pixels válidos (SCL)", loc="left")
    ax.grid(alpha=0.25)
    ax.legend(ncol=3, frameon=False, fontsize=9, loc="lower center", bbox_to_anchor=(0.5, -0.28))
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    fig.autofmt_xdate()
    fig.tight_layout()
    Path(a.saida).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.saida, dpi=150)
    print(f"Gravado: {a.saida}")


if __name__ == "__main__":
    main()
