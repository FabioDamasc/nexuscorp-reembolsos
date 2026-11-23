"""Script auxiliar para popular o banco SQLite com departamentos e usuários de teste."""
from app.core.database import Base, engine, SessionLocal
from app.core.security import gerar_hash_senha
from app.models import Departamento, Usuario


def popular_banco():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Departamento).count() > 0:
            print("Banco já populado.")
            return

        dep_com = Departamento(nome="Comercial")
        dep_tec = Departamento(nome="Tecnologia")
        dep_fin = Departamento(nome="Financeiro")
        db.add_all([dep_com, dep_tec, dep_fin])
        db.commit()

        senha = gerar_hash_senha("senha123")
        usuarios = [
            Usuario(nome="Ana Silva", email="ana@nexus.com", senha_hash=senha, perfil="colaborador", departamento_id=dep_com.id),
            Usuario(nome="Bruno Souza", email="bruno@nexus.com", senha_hash=senha, perfil="colaborador", departamento_id=dep_tec.id),
            Usuario(nome="Patrícia Lima", email="patricia@nexus.com", senha_hash=senha, perfil="gestor", departamento_id=dep_com.id),
            Usuario(nome="Carlos Mendes", email="carlos@nexus.com", senha_hash=senha, perfil="gestor", departamento_id=dep_tec.id),
            Usuario(nome="Fernanda Rocha", email="fernanda@nexus.com", senha_hash=senha, perfil="financeiro", departamento_id=dep_fin.id),
        ]
        db.add_all(usuarios)
        db.commit()
        print("Departamentos e usuários de teste criados com sucesso! Senha padrão: senha123")
    finally:
        db.close()


if __name__ == "__main__":
    popular_banco()
