from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from .database import Base
import enum

class StatusAgendamentoEnum(str, enum.Enum):
    AGENDADO = "agendado"
    CANCELADO = "cancelado"
    CONCLUIDO = "concluido"


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)

    agendamentos = relationship("Agendamento", back_populates="cliente")


class Barbeiro(Base):
    __tablename__ = "barbeiros"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    especialidade = Column(String, nullable=True)

    agendamentos = relationship("Agendamento", back_populates="barbeiro")


class Servico(Base):
    __tablename__ = "servicos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    descricao = Column(String, nullable=True)
    preco = Column(Integer, nullable=False)

    agendamentos = relationship("Agendamento", back_populates="servico")


class Agendamento(Base):
    __tablename__ = "agendamentos"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    barbeiro_id = Column(Integer, ForeignKey("barbeiros.id"), nullable=False)
    servico_id = Column(Integer, ForeignKey("servicos.id"), nullable=False)
    data_hora = Column(DateTime, nullable=False)
    status = Column(Enum(StatusAgendamentoEnum), default=StatusAgendamentoEnum.AGENDADO, nullable=False)
    cancelado_em = Column(DateTime, nullable=True)

    cliente = relationship("Cliente", back_populates="agendamentos")
    barbeiro = relationship("Barbeiro", back_populates="agendamentos")
    servico = relationship("Servico", back_populates="agendamentos")
