from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


class Departamento(Base):
    __tablename__ = "departamentos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), unique=True, nullable=False)

    usuarios = relationship("Usuario", back_populates="departamento")


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(120), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    senha_hash = Column(String(255), nullable=False)
    perfil = Column(String(20), nullable=False, default="colaborador")  # colaborador | gestor | financeiro
    departamento_id = Column(Integer, ForeignKey("departamentos.id"), nullable=False)

    departamento = relationship("Departamento", back_populates="usuarios")
    solicitacoes = relationship("SolicitacaoReembolso", back_populates="solicitante")


class SolicitacaoReembolso(Base):
    __tablename__ = "solicitacoes_reembolso"
    __table_args__ = (
        UniqueConstraint("solicitante_id", "referencia_comprovante", name="uq_solicitante_comprovante"),
    )

    id = Column(Integer, primary_key=True, index=True)
    solicitante_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    categoria = Column(String(30), nullable=False)  # alimentacao | transporte | hospedagem | materiais
    valor = Column(Float, nullable=False)
    data_despesa = Column(Date, nullable=False)
    justificativa = Column(String(500), nullable=False)
    referencia_comprovante = Column(String(100), nullable=False)
    situacao = Column(String(30), nullable=False, default="rascunho")
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    solicitante = relationship("Usuario", back_populates="solicitacoes")
    historico = relationship("HistoricoAnalise", back_populates="solicitacao", cascade="all, delete-orphan")


class HistoricoAnalise(Base):
    __tablename__ = "historico_analises"

    id = Column(Integer, primary_key=True, index=True)
    solicitacao_id = Column(Integer, ForeignKey("solicitacoes_reembolso.id"), nullable=False)
    responsavel_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    etapa = Column(String(30), nullable=False)      # gestor | financeiro | pagamento
    decisao = Column(String(20), nullable=False)    # aprovada | recusada | paga
    observacao = Column(String(500), nullable=True)
    data_decisao = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    solicitacao = relationship("SolicitacaoReembolso", back_populates="historico")
    responsavel = relationship("Usuario")
