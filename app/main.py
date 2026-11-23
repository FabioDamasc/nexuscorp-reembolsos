from fastapi import FastAPI
from app.core.database import Base, engine
from app.routers import auth, solicitacoes

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="NexusCorp — Plataforma de Gestão de Reembolsos Corporativos",
    description="API REST para controle de despesas, fluxo de aprovação e rastreabilidade de reembolsos.",
    version="1.0.0",
)

app.include_router(auth.router)
app.include_router(solicitacoes.router)
