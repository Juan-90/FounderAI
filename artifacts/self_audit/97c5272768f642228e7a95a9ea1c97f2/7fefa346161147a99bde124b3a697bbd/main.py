from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas, database

app = FastAPI(title="Barbearia Online API")

# Optional CORS middleware – useful for frontend dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure tables are created on startup
@app.on_event("startup")
async def startup():
    database.init_db()

# Dependency

def get_db():
    return database.get_db()


# CRUD – Agendamento

@app.post("/agendamentos", response_model=schemas.AgendamentoRead, status_code=201)
def create_agendamento(
    agendamento_in: schemas.AgendamentoCreate,
    db: Session = Depends(get_db),
):
    # Validate foreign keys exist
    cliente = db.query(models.Cliente).filter(models.Cliente.id == agendamento_in.cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente not found")
    barbeiro = db.query(models.Barbeiro).filter(models.Barbeiro.id == agendamento_in.barbeiro_id).first()
    if not barbeiro:
        raise HTTPException(status_code=404, detail="Barbeiro not found")
    servico = db.query(models.Servico).filter(models.Servico.id == agendamento