from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import gerar_hash_senha, verificar_senha, criar_token_acesso
from app.core.dependencies import get_current_user
from app.models import Usuario, Departamento
from app.schemas import UsuarioCadastro, UsuarioResponse, TokenResponse

router = APIRouter(prefix="/auth", tags=["Autenticação e Usuários"])


@router.post(
    "/cadastro",
    response_model=UsuarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar novo colaborador",
    description="Registra um novo usuário sempre com perfil 'colaborador' (RN15).",
)
def cadastrar_usuario(dados: UsuarioCadastro, db: Session = Depends(get_db)):
    if db.query(Usuario).filter(Usuario.email == dados.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado.")

    if not db.query(Departamento).filter(Departamento.id == dados.departamento_id).first():
        raise HTTPException(status_code=404, detail="Departamento não encontrado.")

    novo = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=gerar_hash_senha(dados.senha),
        perfil="colaborador",  # RN15: sempre nasce como colaborador
        departamento_id=dados.departamento_id,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Autenticar usuário",
    description="Valida e-mail e senha e retorna um token JWT Bearer.",
)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == form.username).first()
    # RN13 / Cenário 03: mensagem genérica sem revelar se o e-mail existe
    if not usuario or not verificar_senha(form.password, usuario.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = criar_token_acesso({
        "sub": usuario.email,
        "usuario_id": usuario.id,
        "perfil": usuario.perfil,
        "departamento_id": usuario.departamento_id,
    })
    return {"access_token": token, "token_type": "bearer"}


@router.get(
    "/me",
    response_model=UsuarioResponse,
    summary="Consultar perfil autenticado",
    description="Retorna os dados do usuário atualmente autenticado sem expor credenciais.",
)
def meu_perfil(usuario: Usuario = Depends(get_current_user)):
    return usuario
