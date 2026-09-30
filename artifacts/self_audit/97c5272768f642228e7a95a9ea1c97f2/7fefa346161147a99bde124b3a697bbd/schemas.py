from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class StatusAgendamento(str, Enum):
    AGENDADO = "agendado"
    CANCELADO = "cancelado"
    CONCLUIDO = "concluido"


class ClienteCreate(BaseModel):
    nome: str
    email: str


class BarbeiroCreate(BaseModel):
    nome: str
    especialidade: Optional[str] = None


class ServicoCreate(BaseModel):
    nome: str
    descricao: Optional[str] = None
    preco: int


class AgendamentoCreate(BaseModel):
    cliente_id: int
    barbeiro_id: int
    servico_id: int
    data_hora: datetime


class AgendamentoUpdate(BaseModel):
    data_hora: Optional[datetime] = None
    servico_id: Optional[int] = None


class AgendamentoRead(BaseModel):
    id: int
    cliente_id: int
    barbeiro_id: int
    servico_id: int
    data_hora: datetime
    status: StatusAgendamento
    cancelado_em: Optional[datetime] = None

    class Config:
        orm_mode = True
