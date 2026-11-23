from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base, get_db
from app.core.security import gerar_hash_senha
from app.main import app
from app.models import Departamento, Usuario

TEST_DB_URL = "sqlite:///./test_nexuscorp.db"
engine_test = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


@pytest.fixture(autouse=True)
def db_session():
    Base.metadata.drop_all(bind=engine_test)
    Base.metadata.create_all(bind=engine_test)
    db = TestingSessionLocal()

    dep_com = Departamento(nome="Comercial")
    dep_tec = Departamento(nome="Tecnologia")
    dep_fin = Departamento(nome="Financeiro")
    db.add_all([dep_com, dep_tec, dep_fin])
    db.commit()

    senha = gerar_hash_senha("senha123")
    usuarios = [
        Usuario(nome="Ana", email="ana@nexus.com", senha_hash=senha, perfil="colaborador", departamento_id=dep_com.id),
        Usuario(nome="Bruno", email="bruno@nexus.com", senha_hash=senha, perfil="colaborador", departamento_id=dep_tec.id),
        Usuario(nome="Patricia", email="patricia@nexus.com", senha_hash=senha, perfil="gestor", departamento_id=dep_com.id),
        Usuario(nome="Carlos", email="carlos@nexus.com", senha_hash=senha, perfil="gestor", departamento_id=dep_tec.id),
        Usuario(nome="Fernanda", email="fernanda@nexus.com", senha_hash=senha, perfil="financeiro", departamento_id=dep_fin.id),
    ]
    db.add_all(usuarios)
    db.commit()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield db
    db.close()


client = TestClient(app)


def _headers(email: str, senha: str = "senha123") -> dict:
    resp = client.post("/auth/login", data={"username": email, "password": senha})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _criar_solicitacao(headers: dict, valor: float = 180.0, comprovante: str = "NF-001") -> dict:
    resp = client.post(
        "/solicitacoes/",
        headers=headers,
        json={
            "categoria": "alimentacao",
            "valor": valor,
            "data_despesa": date.today().isoformat(),
            "justificativa": "Almoço com cliente externo",
            "referencia_comprovante": comprovante,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def test_cenario_01_acesso_indevido():
    sol_bruno = _criar_solicitacao(_headers("bruno@nexus.com"))
    resp = client.get(f"/solicitacoes/{sol_bruno['id']}", headers=_headers("ana@nexus.com"))
    assert resp.status_code == 403


def test_cenario_02_gestor_outro_departamento():
    h_bruno = _headers("bruno@nexus.com")
    sol_bruno = _criar_solicitacao(h_bruno)
    client.post(f"/solicitacoes/{sol_bruno['id']}/enviar", headers=h_bruno)

    resp = client.post(
        f"/solicitacoes/{sol_bruno['id']}/analise-gestor",
        headers=_headers("patricia@nexus.com"),
        json={"decisao": "aprovada"},
    )
    assert resp.status_code == 403


def test_cenario_03_credenciais_incorretas():
    resp = client.post("/auth/login", data={"username": "ana@nexus.com", "password": "errada"})
    assert resp.status_code == 401
    assert "senha" not in resp.json()["detail"].lower()


def test_cenario_04_tentativa_alteracao_permissoes():
    resp = client.post(
        "/auth/cadastro",
        json={
            "nome": "Invasor",
            "email": "invasor@nexus.com",
            "senha": "senha123",
            "departamento_id": 1,
            "perfil": "financeiro",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["perfil"] == "colaborador"


def test_cenario_05_aprovacao_fora_da_sequencia():
    h_bruno = _headers("bruno@nexus.com")
    sol = _criar_solicitacao(h_bruno)
    client.post(f"/solicitacoes/{sol['id']}/enviar", headers=h_bruno)

    resp = client.post(
        f"/solicitacoes/{sol['id']}/analise-financeira",
        headers=_headers("fernanda@nexus.com"),
        json={"decisao": "aprovada"},
    )
    assert resp.status_code == 400


def test_cenario_06_manipulacao_solicitacao_apos_envio():
    h_bruno = _headers("bruno@nexus.com")
    sol = _criar_solicitacao(h_bruno, valor=180.0)
    client.post(f"/solicitacoes/{sol['id']}/enviar", headers=h_bruno)

    resp = client.put(f"/solicitacoes/{sol['id']}", headers=h_bruno, json={"valor": 1800.0})
    assert resp.status_code == 400


def test_cenario_07_consulta_com_filtros_gestor():
    h_ana = _headers("ana@nexus.com")
    h_bruno = _headers("bruno@nexus.com")
    s_ana = _criar_solicitacao(h_ana, comprovante="NF-ANA")
    s_bruno = _criar_solicitacao(h_bruno, comprovante="NF-BRUNO")
    client.post(f"/solicitacoes/{s_ana['id']}/enviar", headers=h_ana)
    client.post(f"/solicitacoes/{s_bruno['id']}/enviar", headers=h_bruno)

    resp = client.get("/solicitacoes/?situacao=aguardando_gestor", headers=_headers("patricia@nexus.com"))
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert s_ana["id"] in ids
    assert s_bruno["id"] not in ids


def test_cenario_08_historico_financeiro_completo():
    h_bruno = _headers("bruno@nexus.com")
    h_carlos = _headers("carlos@nexus.com")
    h_fin = _headers("fernanda@nexus.com")

    sol = _criar_solicitacao(h_bruno)
    assert client.post(f"/solicitacoes/{sol['id']}/enviar", headers=h_bruno).status_code == 200
    assert client.post(f"/solicitacoes/{sol['id']}/analise-gestor", headers=h_carlos, json={"decisao": "aprovada", "observacao": "OK gestor"}).status_code == 200
    assert client.post(f"/solicitacoes/{sol['id']}/analise-financeira", headers=h_fin, json={"decisao": "aprovada", "observacao": "OK financeiro"}).status_code == 200
    resp_pago = client.post(f"/solicitacoes/{sol['id']}/pagar", headers=h_fin, json={"observacao": "PIX realizado"})
    assert resp_pago.status_code == 200

    dados = resp_pago.json()
    assert dados["situacao"] == "paga"
    assert len(dados["historico"]) == 3
    assert [h["etapa"] for h in dados["historico"]] == ["gestor", "financeiro", "pagamento"]


def test_regras_negocio_adicionais():
    h_ana = _headers("ana@nexus.com")

    # RN04: valor <= 0
    r_val = client.post("/solicitacoes/", headers=h_ana, json={
        "categoria": "transporte", "valor": 0, "data_despesa": date.today().isoformat(),
        "justificativa": "Uber", "referencia_comprovante": "NF-ZERO"
    })
    assert r_val.status_code == 422

    # RN06: data futura
    amanha = (date.today() + timedelta(days=1)).isoformat()
    r_data = client.post("/solicitacoes/", headers=h_ana, json={
        "categoria": "transporte", "valor": 50.0, "data_despesa": amanha,
        "justificativa": "Uber", "referencia_comprovante": "NF-FUT"
    })
    assert r_data.status_code == 422

    # RN05: comprovante duplicado
    _criar_solicitacao(h_ana, comprovante="NF-DUP")
    r_dup = client.post("/solicitacoes/", headers=h_ana, json={
        "categoria": "alimentacao", "valor": 40.0, "data_despesa": date.today().isoformat(),
        "justificativa": "Lanche", "referencia_comprovante": "NF-DUP"
    })
    assert r_dup.status_code == 409

    # RN11: recusa sem justificativa
    sol = _criar_solicitacao(h_ana, comprovante="NF-REC")
    client.post(f"/solicitacoes/{sol['id']}/enviar", headers=h_ana)
    r_rec = client.post(f"/solicitacoes/{sol['id']}/analise-gestor", headers=_headers("patricia@nexus.com"), json={"decisao": "recusada"})
    assert r_rec.status_code == 400
