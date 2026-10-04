"""API do WebGIS (FastAPI). Le os talhoes e o NDVI do banco PostGIS do Projeto 2.

Executar (raiz do repositorio):  python projeto3.py servir
Documentacao interativa:         http://127.0.0.1:8000/docs
"""
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


class ObservacaoNdvi(BaseModel):
    talhao_id: str
    cultura: str
    data: date
    ndvi_medio: float
    ndvi_mediana: Optional[float] = None
    pct_validos: Optional[float] = None


class Vizinho(BaseModel):
    id: str
    cultura: str
    distancia_m: float


def criar_app(repo) -> FastAPI:
    app = FastAPI(title="Talhoes e NDVI", version="1.0",
                  description="PROJETO DEMONSTRATIVO. Dados de 5 talhoes anonimizados e NDVI Sentinel-2.")
    # Somente leitura (GET): liberar qualquer origem permite abrir o mapa a partir de outro endereco.
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

    @app.get("/saude")
    def saude():
        return {"status": "ok"}

    @app.get("/talhoes")
    def talhoes():
        """Talhoes em GeoJSON (WGS 84)."""
        return repo.talhoes()

    @app.get("/ndvi", response_model=list[ObservacaoNdvi])
    def ndvi(talhao: Optional[str] = Query(None, max_length=32, description="id do talhao, ex.: T01"),
             inicio: Optional[date] = None, fim: Optional[date] = None):
        """Observacoes aprovadas de NDVI, com filtros opcionais."""
        if inicio and fim and inicio > fim:
            raise HTTPException(status_code=422, detail="'inicio' deve ser anterior ou igual a 'fim'.")
        return repo.ndvi(talhao, inicio, fim)

    @app.get("/vizinhos/{talhao_id}", response_model=list[Vizinho])
    def vizinhos(talhao_id: str, km: float = Query(5.0, gt=0, le=100)):
        """Talhoes a ate `km` quilometros do talhao informado."""
        if not repo.existe_talhao(talhao_id):
            raise HTTPException(status_code=404, detail=f"Talhao '{talhao_id}' nao encontrado.")
        return repo.vizinhos(talhao_id, km)

    return app


def criar_app_padrao() -> FastAPI:
    """Usada pelo uvicorn (--factory): conecta usando as variaveis PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD."""
    from api.repo import RepositorioPostgis

    return criar_app(RepositorioPostgis())
