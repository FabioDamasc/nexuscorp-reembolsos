from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, exigir_perfil
from app.models import SolicitacaoReembolso, HistoricoAnalise, Usuario
from app.schemas import (
    SolicitacaoCreate,
    SolicitacaoUpdate,
    SolicitacaoResponse,
    AnaliseRequest,
    PagamentoRequest,
)

router = APIRouter(prefix="/solicitacoes", tags=["Solicitações de Reembolso"])


def _buscar_solicitacao(solicitacao_id: int, db: Session) -> SolicitacaoReembolso:
    sol = db.query(SolicitacaoReembolso).filter(SolicitacaoReembolso.id == solicitacao_id).first()
    if not sol:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")
    return sol


@router.post(
    "/",
    response_model=SolicitacaoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar solicitação de reembolso",
    description="Cria uma nova solicitação em rascunho. Valida valor > 0, data não futura e comprovante único.",
)
def criar_solicitacao(
    dados: SolicitacaoCreate,
    usuario: Usuario = Depends(exigir_perfil("colaborador")),
    db: Session = Depends(get_db),
):
    nova = SolicitacaoReembolso(
        solicitante_id=usuario.id,
        categoria=dados.categoria,
        valor=dados.valor,
        data_despesa=dados.data_despesa,
        justificativa=dados.justificativa,
        referencia_comprovante=dados.referencia_comprovante,
        situacao="rascunho",
    )
    db.add(nova)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe uma despesa registrada por você com esta referência de comprovante (RN05).",
        )
    db.refresh(nova)
    return nova


@router.get(
    "/",
    response_model=list[SolicitacaoResponse],
    summary="Listar solicitações com filtros",
    description="Aplica restrições de visibilidade conforme perfil (colaborador, gestor ou financeiro).",
)
def listar_solicitacoes(
    departamento_id: Optional[int] = Query(default=None),
    situacao: Optional[str] = Query(default=None),
    categoria: Optional[str] = Query(default=None),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(SolicitacaoReembolso).join(Usuario, SolicitacaoReembolso.solicitante_id == Usuario.id)

    # Restrição por perfil (RN02, RN03, Cenário 07)
    if usuario.perfil == "colaborador":
        query = query.filter(SolicitacaoReembolso.solicitante_id == usuario.id)
    elif usuario.perfil == "gestor":
        query = query.filter(Usuario.departamento_id == usuario.departamento_id)
    elif usuario.perfil == "financeiro":
        query = query.filter(
            SolicitacaoReembolso.situacao.in_(["aguardando_financeiro", "aprovada", "paga", "recusada"])
        )
        if departamento_id is not None:
            query = query.filter(Usuario.departamento_id == departamento_id)

    if situacao:
        query = query.filter(SolicitacaoReembolso.situacao == situacao)
    if categoria:
        query = query.filter(SolicitacaoReembolso.categoria == categoria)

    return query.all()


@router.get(
    "/{solicitacao_id}",
    response_model=SolicitacaoResponse,
    summary="Detalhar solicitação específica",
    description="Retorna detalhes e histórico de análises respeitando confidencialidade e departamento.",
)
def detalhar_solicitacao(
    solicitacao_id: int,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sol = _buscar_solicitacao(solicitacao_id, db)

    if usuario.perfil == "colaborador" and sol.solicitante_id != usuario.id:
        raise HTTPException(status_code=403, detail="Acesso negado a solicitações de outros colaboradores (RN02).")

    if usuario.perfil == "gestor" and sol.solicitante.departamento_id != usuario.departamento_id:
        raise HTTPException(status_code=403, detail="Acesso negado a solicitações de outro departamento (RN03).")

    if usuario.perfil == "financeiro" and sol.situacao in ("rascunho", "aguardando_gestor"):
        raise HTTPException(status_code=403, detail="Solicitação ainda não encaminhada ao financeiro.")

    return sol


@router.put(
    "/{solicitacao_id}",
    response_model=SolicitacaoResponse,
    summary="Editar solicitação em rascunho",
    description="Permite ao colaborador editar sua solicitação somente enquanto estiver em 'rascunho' (RN07).",
)
def atualizar_solicitacao(
    solicitacao_id: int,
    dados: SolicitacaoUpdate,
    usuario: Usuario = Depends(exigir_perfil("colaborador")),
    db: Session = Depends(get_db),
):
    sol = _buscar_solicitacao(solicitacao_id, db)

    if sol.solicitante_id != usuario.id:
        raise HTTPException(status_code=403, detail="Você só pode editar suas próprias solicitações (RN02).")

    if sol.situacao != "rascunho":
        raise HTTPException(status_code=400, detail="Solicitação só pode ser alterada em rascunho (RN07).")

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(sol, campo, valor)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Referência de comprovante já utilizada (RN05).")

    db.refresh(sol)
    return sol


@router.delete(
    "/{solicitacao_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir solicitação em rascunho",
    description="Permite ao colaborador excluir sua solicitação somente antes de ser enviada.",
)
def excluir_solicitacao(
    solicitacao_id: int,
    usuario: Usuario = Depends(exigir_perfil("colaborador")),
    db: Session = Depends(get_db),
):
    sol = _buscar_solicitacao(solicitacao_id, db)

    if sol.solicitante_id != usuario.id:
        raise HTTPException(status_code=403, detail="Você só pode excluir suas próprias solicitações (RN02).")

    if sol.situacao != "rascunho":
        raise HTTPException(status_code=400, detail="Somente solicitações em rascunho podem ser excluídas.")

    db.delete(sol)
    db.commit()


@router.post(
    "/{solicitacao_id}/enviar",
    response_model=SolicitacaoResponse,
    summary="Enviar solicitação para análise do gestor",
    description="Altera a situação de 'rascunho' para 'aguardando_gestor'.",
)
def enviar_para_gestor(
    solicitacao_id: int,
    usuario: Usuario = Depends(exigir_perfil("colaborador")),
    db: Session = Depends(get_db),
):
    sol = _buscar_solicitacao(solicitacao_id, db)

    if sol.solicitante_id != usuario.id:
        raise HTTPException(status_code=403, detail="Você só pode enviar suas próprias solicitações.")

    if sol.situacao != "rascunho":
        raise HTTPException(status_code=400, detail="Somente solicitações em rascunho podem ser enviadas.")

    sol.situacao = "aguardando_gestor"
    db.commit()
    db.refresh(sol)
    return sol


@router.post(
    "/{solicitacao_id}/analise-gestor",
    response_model=SolicitacaoResponse,
    summary="Análise do gestor (aprovar ou recusar)",
    description="Gestor do mesmo departamento analisa solicitação em 'aguardando_gestor' e grava histórico.",
)
def analisar_como_gestor(
    solicitacao_id: int,
    dados: AnaliseRequest,
    usuario: Usuario = Depends(exigir_perfil("gestor")),
    db: Session = Depends(get_db),
):
    sol = _buscar_solicitacao(solicitacao_id, db)

    if sol.solicitante_id == usuario.id:
        raise HTTPException(status_code=403, detail="Nenhum usuário pode aprovar a própria solicitação (RN09).")

    if sol.solicitante.departamento_id != usuario.departamento_id:
        raise HTTPException(status_code=403, detail="Gestor só pode analisar solicitações do próprio departamento (RN03).")

    if sol.situacao != "aguardando_gestor":
        raise HTTPException(status_code=400, detail="Solicitação não está aguardando análise do gestor.")

    if dados.decisao == "recusada" and not (dados.observacao and dados.observacao.strip()):
        raise HTTPException(status_code=400, detail="Toda recusa exige justificativa no histórico (RN11).")

    sol.situacao = "aguardando_financeiro" if dados.decisao == "aprovada" else "recusada"
    db.add(HistoricoAnalise(
        solicitacao_id=sol.id,
        responsavel_id=usuario.id,
        etapa="gestor",
        decisao=dados.decisao,
        observacao=dados.observacao,
    ))
    db.commit()
    db.refresh(sol)
    return sol


@router.post(
    "/{solicitacao_id}/analise-financeira",
    response_model=SolicitacaoResponse,
    summary="Análise financeira (aprovar ou recusar)",
    description="Financeiro analisa solicitação em 'aguardando_financeiro' e grava histórico.",
)
def analisar_como_financeiro(
    solicitacao_id: int,
    dados: AnaliseRequest,
    usuario: Usuario = Depends(exigir_perfil("financeiro")),
    db: Session = Depends(get_db),
):
    sol = _buscar_solicitacao(solicitacao_id, db)

    if sol.solicitante_id == usuario.id:
        raise HTTPException(status_code=403, detail="Nenhum usuário pode aprovar a própria solicitação (RN09).")

    if sol.situacao != "aguardando_financeiro":
        raise HTTPException(status_code=400, detail="Solicitação deve estar aprovada pelo gestor antes da análise financeira (RN08).")

    if dados.decisao == "recusada" and not (dados.observacao and dados.observacao.strip()):
        raise HTTPException(status_code=400, detail="Toda recusa exige justificativa no histórico (RN11).")

    sol.situacao = "aprovada" if dados.decisao == "aprovada" else "recusada"
    db.add(HistoricoAnalise(
        solicitacao_id=sol.id,
        responsavel_id=usuario.id,
        etapa="financeiro",
        decisao=dados.decisao,
        observacao=dados.observacao,
    ))
    db.commit()
    db.refresh(sol)
    return sol


@router.post(
    "/{solicitacao_id}/pagar",
    response_model=SolicitacaoResponse,
    summary="Registrar pagamento da solicitação",
    description="Financeiro registra pagamento apenas para solicitações em situação 'aprovada' (RN10).",
)
def registrar_pagamento(
    solicitacao_id: int,
    dados: PagamentoRequest,
    usuario: Usuario = Depends(exigir_perfil("financeiro")),
    db: Session = Depends(get_db),
):
    sol = _buscar_solicitacao(solicitacao_id, db)

    if sol.situacao != "aprovada":
        raise HTTPException(status_code=400, detail="Pagamento só pode ser registrado após aprovação financeira (RN10).")

    sol.situacao = "paga"
    db.add(HistoricoAnalise(
        solicitacao_id=sol.id,
        responsavel_id=usuario.id,
        etapa="pagamento",
        decisao="paga",
        observacao=dados.observacao,
    ))
    db.commit()
    db.refresh(sol)
    return sol
