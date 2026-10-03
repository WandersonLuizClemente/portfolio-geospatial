"""Pipeline de NDVI por talhao com Sentinel-2 L2A (Earth Search / AWS, dados abertos).

Para cada cena do periodo:
  1. le so a janela de cada talhao (COG, sem baixar a cena inteira);
  2. CONFERE A CALIBRACAO (offset de reflectancia) com os proprios dados da cena;
  3. aplica a mascara de nuvem/sombra (banda SCL);
  4. calcula o NDVI SEM recortar valores fora de [-1, 1] (eles viram pixels descartados);
  5. grava estatisticas por talhao e data, com as evidencias de calibracao.

Uso (da raiz do repositorio):   python projeto1.py rodar
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from proj_env import isolar_proj_gdal

isolar_proj_gdal()  # antes de importar geopandas/rasterio

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import rasterio  # noqa: E402
from rasterio import features  # noqa: E402
from rasterio.enums import Resampling  # noqa: E402
from rasterio.windows import Window, from_bounds  # noqa: E402
from shapely.geometry import box  # noqa: E402

PROJ_DIR = Path(__file__).resolve().parents[1]
STAC_URL = "https://earth-search.aws.element84.com/v1"
COLECAO = "sentinel-2-l2a"
# Classes SCL aceitas: 4 = vegetacao, 5 = solo nu. O resto (nuvem, sombra, agua, defeito) e descartado.
SCL_VALIDAS = (4, 5)
OFFSET_ESA_BASELINE_4 = -0.1        # baseline >= 04.00: DN carrega +1000 (reflectancia = DN*0.0001 - 0.1)
TOL_REFLECTANCIA_NEG = -0.005       # reflectancia abaixo disso e fisicamente implausivel
LIMITE_PIXELS_NEGATIVOS = 0.20      # acima disso o offset testado e rejeitado
MIN_PIXELS_PARA_DECIDIR_OFFSET = 500  # abaixo disso a cena nao tem pixels limpos suficientes para calibrar
LIMITE_FORA_DA_FAIXA = 0.05         # acima disso (pixels com NDVI impossivel) o talhao da data e reprovado
COLUNAS_OBRIGATORIAS = ("id", "cultura")


@dataclass
class Cena:
    id: str
    data: str
    red: str
    nir: str
    scl: str
    escala: float = 0.0001
    offset_stac: Optional[float] = None   # offset declarado no catalogo (None = nao declarado)
    baseline: Optional[str] = None        # ex.: "05.11"


@dataclass
class Leitura:
    talhao: pd.Series
    dentro: np.ndarray   # pixels dentro do poligono
    red: np.ndarray      # DN
    nir: np.ndarray      # DN
    scl: np.ndarray

    @property
    def base(self) -> np.ndarray:
        """Pixels do talhao com SCL aceita e DN > 0 (0 = sem dado)."""
        return self.dentro & np.isin(self.scl, SCL_VALIDAS) & (self.red > 0) & (self.nir > 0)


# ----------------------------------------------------------------------------- catalogo
def buscar_cenas(bbox, inicio: str, fim: str, max_nuvem: float) -> list:
    """Consulta o catalogo STAC e devolve as cenas com bandas red (B04), nir (B08) e scl."""
    from pystac_client import Client

    busca = Client.open(STAC_URL).search(
        collections=[COLECAO], bbox=list(bbox), datetime=f"{inicio}/{fim}",
        query={"eo:cloud_cover": {"lt": max_nuvem}},
    )
    cenas = []
    for item in busca.items():
        a = item.assets
        if not all(k in a for k in ("red", "nir", "scl")):
            continue
        info = (a["red"].extra_fields.get("raster:bands") or [{}])[0]
        cenas.append(Cena(
            id=item.id, data=item.datetime.date().isoformat(),
            red=a["red"].href, nir=a["nir"].href, scl=a["scl"].href,
            escala=float(info.get("scale", 0.0001)),
            offset_stac=float(info["offset"]) if "offset" in info else None,
            baseline=item.properties.get("s2:processing_baseline"),
        ))
    cenas.sort(key=lambda c: c.data)
    return cenas


# ----------------------------------------------------------------------------- calculo
def _janela_inteira(janela: Window) -> Window:
    """Arredonda uma janela fracionaria para fora, cobrindo todos os pixels tocados."""
    c0, r0 = int(np.floor(janela.col_off)), int(np.floor(janela.row_off))
    c1 = int(np.ceil(janela.col_off + janela.width))
    r1 = int(np.ceil(janela.row_off + janela.height))
    return Window(c0, r0, c1 - c0, r1 - r0)


def ndvi_bruto(red_dn, nir_dn, escala: float, offset: float):
    """NDVI sem recorte. Vira NaN onde nao ha dado (DN = 0) ou a soma das reflectancias e <= 0."""
    red = red_dn.astype("float32") * escala + offset
    nir = nir_dn.astype("float32") * escala + offset
    den = nir + red
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir - red) / den
    ndvi[(red_dn == 0) | (nir_dn == 0) | (den <= 0)] = np.nan
    return ndvi


def offset_esperado(baseline) -> Optional[float]:
    try:
        return OFFSET_ESA_BASELINE_4 if float(baseline) >= 4.0 else 0.0
    except (TypeError, ValueError):
        return None


def candidatos(cena: Cena) -> list:
    """Offsets a testar, em ordem de preferencia: o do catalogo, depois o da baseline, depois 0 e -0,1."""
    primario = cena.offset_stac
    if primario is None:
        primario = offset_esperado(cena.baseline)
    if primario is None:
        primario = OFFSET_ESA_BASELINE_4
    lista = [primario]
    for off in (0.0, OFFSET_ESA_BASELINE_4):
        if off not in lista:
            lista.append(off)
    return lista


def ler_talhoes(cena: Cena, talhoes: gpd.GeoDataFrame) -> list:
    """Le as janelas de red, nir e scl de cada talhao contido na cena."""
    leituras = []
    with rasterio.open(cena.red) as r, rasterio.open(cena.nir) as n, rasterio.open(cena.scl) as s:
        geoms = talhoes.to_crs(r.crs).geometry
        limites = box(*r.bounds)
        for (_, talhao), geom in zip(talhoes.iterrows(), geoms):
            if not limites.contains(geom):
                continue  # talhao fora desta cena (limite de tile)
            janela = _janela_inteira(from_bounds(*geom.bounds, transform=r.transform))
            transf = r.window_transform(janela)
            red = r.read(1, window=janela)
            nir = n.read(1, window=janela)
            # SCL tem 20 m: le a mesma area e reamostra (vizinho mais proximo) para a grade de 10 m
            jan_scl = from_bounds(*r.window_bounds(janela), transform=s.transform)
            scl = s.read(1, window=jan_scl, out_shape=red.shape, resampling=Resampling.nearest)
            dentro = features.geometry_mask([geom], out_shape=red.shape, transform=transf, invert=True)
            if int(dentro.sum()) == 0:
                continue
            leituras.append(Leitura(talhao, dentro, red, nir, scl))
    return leituras


def fracao_negativa(leituras: list, escala: float, offset: float) -> Optional[float]:
    """Fracao dos pixels validos (todos os talhoes da cena) com reflectancia negativa para um offset."""
    neg = tot = 0
    for l in leituras:
        v = l.base
        if not v.any():
            continue
        red = l.red[v].astype("float32") * escala + offset
        nir = l.nir[v].astype("float32") * escala + offset
        neg += int(((red < TOL_REFLECTANCIA_NEG) | (nir < TOL_REFLECTANCIA_NEG)).sum())
        tot += int(v.sum())
    return None if tot < MIN_PIXELS_PARA_DECIDIR_OFFSET else neg / tot


def escolher_offset(cena: Cena, leituras: list):
    """Escolhe o offset que NAO produz reflectancia negativa. Devolve (offset, status)."""
    cands = candidatos(cena)
    for i, off in enumerate(cands):
        frac = fracao_negativa(leituras, cena.escala, off)
        if frac is None:
            return cands[0], "sem_pixels_validos"
        if frac <= LIMITE_PIXELS_NEGATIVOS:
            return off, ("ok" if i == 0 else "corrigido_pelos_dados")
    return None, "calibracao_invalida"


def estatisticas(cena: Cena, leituras: list, offset: float, status: str, min_validos: float) -> list:
    linhas = []
    for l in leituras:
        t = l.talhao
        n_total = int(l.dentro.sum())
        base = l.base
        ndvi = ndvi_bruto(l.red, l.nir, cena.escala, offset)
        fora = base & (~np.isfinite(ndvi) | (np.abs(ndvi) > 1))
        ok = base & ~fora
        n_base, n_ok = int(base.sum()), int(ok.sum())
        pct = n_ok / n_total
        pct_fora = int(fora.sum()) / n_base if n_base else 0.0

        if status == "sem_pixels_validos":
            motivo = "cobertura_baixa"
        elif status == "calibracao_invalida" or pct_fora > LIMITE_FORA_DA_FAIXA:
            motivo = "calibracao"
        elif pct < min_validos:
            motivo = "cobertura_baixa"
        else:
            motivo = "ok"

        reg = {
            "data": cena.data, "cena": cena.id, "id": t["id"], "cultura": t["cultura"],
            "area_ha": t.get("area_ha", np.nan),
            "pixels_total": n_total, "pixels_validos": n_ok, "pct_validos": round(pct, 3),
            "pct_fora_faixa": round(pct_fora, 3),
            "offset_stac": cena.offset_stac if cena.offset_stac is not None else np.nan,
            "offset_usado": offset, "calibracao": status,
            "red_dn_p50": float(np.median(l.red[base])) if n_base else np.nan,
            "nir_dn_p50": float(np.median(l.nir[base])) if n_base else np.nan,
            "aprovado": motivo == "ok", "motivo": motivo,
        }
        if motivo == "ok":
            v = ndvi[ok]
            reg.update(ndvi_medio=float(v.mean()), ndvi_mediana=float(np.median(v)),
                       ndvi_desvio=float(v.std()), ndvi_p10=float(np.percentile(v, 10)),
                       ndvi_p90=float(np.percentile(v, 90)))
        linhas.append(reg)
    return linhas


def ndvi_por_talhao(cena: Cena, talhoes: gpd.GeoDataFrame, min_validos: float = 0.8) -> list:
    """Estatisticas de NDVI de cada talhao em uma cena."""
    leituras = ler_talhoes(cena, talhoes)
    if not leituras:
        return []
    offset, status = escolher_offset(cena, leituras)
    if offset is None:
        offset = candidatos(cena)[0]
    return estatisticas(cena, leituras, offset, status, min_validos)


# ----------------------------------------------------------------------------- execucao
def carregar_talhoes(caminho: str) -> gpd.GeoDataFrame:
    if not Path(caminho).exists():
        sys.exit(f"Arquivo de talhoes nao encontrado: {caminho}\n"
                 'Prepare-o com:  python projeto1.py preparar "C:\\caminho\\talhoes_originais.gpkg"')
    g = gpd.read_file(caminho)
    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in g.columns]
    if faltando:
        sys.exit(f"Colunas ausentes no arquivo de talhoes: {faltando}")
    if g.crs is None:
        sys.exit("O arquivo de talhoes nao tem sistema de referencia definido.")
    return g


def imprimir_resumo(df: pd.DataFrame) -> None:
    print("\n" + "=" * 70 + "\nRESUMO (copie este bloco se precisar de ajuda)\n" + "=" * 70)
    print(f"Linhas: {len(df)} | aprovadas: {int(df['aprovado'].sum())}")
    print("Motivos:", df["motivo"].value_counts().to_dict())
    por_cena = df.drop_duplicates("cena")
    print("Calibracao (numero de cenas):", por_cena["calibracao"].value_counts().to_dict())
    print("Offset usado (numero de cenas):", por_cena["offset_usado"].value_counts().to_dict())
    print("Offset do catalogo (numero de cenas):", por_cena["offset_stac"].value_counts(dropna=False).to_dict())
    ok = df[df["aprovado"]]
    if ok.empty:
        print("Nenhuma observacao aprovada.")
        return
    print("\nNDVI medio por cultura (aprovadas): n | minimo / mediana / maximo")
    for cult, g in ok.groupby("cultura"):
        print(f"  {cult:<10} {len(g):>3} | {g['ndvi_medio'].min():.2f} / {g['ndvi_medio'].median():.2f} / {g['ndvi_medio'].max():.2f}")
    if (ok["ndvi_mediana"] >= 0.99).mean() > 0.5:
        print("\nATENCAO: o NDVI ainda parece saturado em mais da metade das linhas. Envie este resumo.")
    if (por_cena["calibracao"] == "corrigido_pelos_dados").any():
        print("\nNOTA: em algumas cenas o offset do catalogo foi rejeitado pelos dados (reflectancia negativa).")
    print("=" * 70)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--talhoes", default=str(PROJ_DIR / "data" / "private" / "talhoes.gpkg"))
    ap.add_argument("--inicio", default="2025-10-01", help="AAAA-MM-DD")
    ap.add_argument("--fim", default="2026-09-30", help="AAAA-MM-DD")
    ap.add_argument("--max-nuvem", type=float, default=70.0, help="cobertura maxima de nuvem da cena (%%)")
    ap.add_argument("--min-validos", type=float, default=0.8, help="fracao minima de pixels validos por talhao")
    ap.add_argument("--saida", default=str(PROJ_DIR / "outputs" / "tables" / "ndvi_por_talhao.csv"))
    a = ap.parse_args()

    os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
    os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "3")
    os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")

    talhoes = carregar_talhoes(a.talhoes)
    bbox = talhoes.to_crs(4326).total_bounds
    print(f"{len(talhoes)} talhoes. Buscando cenas de {a.inicio} a {a.fim}...")
    cenas = buscar_cenas(bbox, a.inicio, a.fim, a.max_nuvem)
    if not cenas:
        sys.exit("Nenhuma cena encontrada. Aumente --max-nuvem ou amplie o periodo.")
    print(f"{len(cenas)} cenas encontradas.")

    registros = []
    for i, cena in enumerate(cenas, 1):
        for tentativa in (1, 2):
            try:
                registros += ndvi_por_talhao(cena, talhoes, a.min_validos)
                print(f"[{i}/{len(cenas)}] {cena.data} {cena.id}")
                break
            except Exception as e:  # uma cena com falha nao derruba o processamento
                if tentativa == 2:
                    warnings.warn(f"Cena {cena.id} ignorada: {e}")
                else:
                    time.sleep(2)

    if not registros:
        sys.exit("Nenhum talhao processado.")
    df = pd.DataFrame(registros).sort_values(["id", "data"])
    Path(a.saida).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.saida, index=False)
    print(f"\nGravado: {a.saida}")
    imprimir_resumo(df)


if __name__ == "__main__":
    main()
