from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict

CategoriaDespesa = Literal["alimentacao", "transporte", "hospedagem", "materiais"]
DecisaoAnalise = Literal["aprovada", "recusada"]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UsuarioCadastro(BaseModel):
    nome: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    senha: str = Field(..., min_length=6)
    departamento_id: int
    # Perfil não é aceito aqui (RN15): todo cadastro público nasce como 'colaborador'


class UsuarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: EmailStr
    perfil: str
    departamento_id: int


class SolicitacaoCreate(BaseModel):
    categoria: CategoriaDespesa
    valor: float = Field(..., gt=0, description="Valor da despesa deve ser maior que zero (RN04)")
    data_despesa: date
    justificativa: str = Field(..., min_length=5, max_length=500)
    referencia_comprovante: str = Field(..., min_length=3, max_length=100)

    @field_validator("data_despesa")
    @classmethod
    def validar_data_nao_futura(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Despesas com datas futuras não são permitidas (RN06).")
        return v


class SolicitacaoUpdate(BaseModel):
    categoria: Optional[CategoriaDespesa] = None
    valor: Optional[float] = Field(default=None, gt=0)
    data_despesa: Optional[date] = None
    justificativa: Optional[str] = Field(default=None, min_length=5, max_length=500)
    referencia_comprovante: Optional[str] = Field(default=None, min_length=3, max_length=100)

    @field_validator("data_despesa")
    @classmethod
    def validar_data_nao_futura(cls, v: Optional[date]) -> Optional[date]:
        if v and v > date.today():
            raise ValueError("Despesas com datas futuras não são permitidas (RN06).")
        return v


class AnaliseRequest(BaseModel):
    decisao: DecisaoAnalise
    observacao: Optional[str] = Field(default=None, max_length=500)


class PagamentoRequest(BaseModel):
    observacao: Optional[str] = Field(default="Pagamento realizado.", max_length=500)


class HistoricoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    responsavel_id: int
    etapa: str
    decisao: str
    observacao: Optional[str]
    data_decisao: datetime


class SolicitacaoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    solicitante_id: int
    categoria: str
    valor: float
    data_despesa: date
    justificativa: str
    referencia_comprovante: str
    situacao: str
    criado_em: datetime
    historico: list[HistoricoResponse] = []
