# NexusCorp — Plataforma de Gestão de Reembolsos Corporativos

## 1. Descrição da Solução
API REST desenvolvida em Python com **FastAPI**, **SQLAlchemy (SQLite)**, **JWT** e **bcrypt** para centralizar o registro, análise, aprovação e pagamento de reembolsos corporativos da NexusCorp, garantindo confidencialidade, segregação de funções e rastreabilidade completa das decisões.

---

## 2. Modelo de Dados (Entidades e Relacionamentos)
- **Departamento** (`departamentos`): `id` (PK), `nome` (único). Um departamento possui vários usuários.
- **Usuário** (`usuarios`): `id` (PK), `nome`, `email` (único), `senha_hash`, `perfil` (`colaborador`, `gestor`, `financeiro`), `departamento_id` (FK -> `departamentos.id`).
- **Solicitação de Reembolso** (`solicitacoes_reembolso`): `id` (PK), `solicitante_id` (FK -> `usuarios.id`), `categoria`, `valor`, `data_despesa`, `justificativa`, `referencia_comprovante`, `situacao`, `criado_em`. Possui restrição única composta `(solicitante_id, referencia_comprovante)`.
- **Histórico de Análise** (`historico_analises`): `id` (PK), `solicitacao_id` (FK -> `solicitacoes_reembolso.id`), `responsavel_id` (FK -> `usuarios.id`), `etapa`, `decisao`, `observacao`, `data_decisao`.

---

## 3. Contrato das Principais Operações da API
| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `POST` | `/auth/cadastro` | Cadastra novo usuário (sempre como `colaborador`). |
| `POST` | `/auth/login` | Autentica usuário e retorna token JWT Bearer. |
| `GET` | `/auth/me` | Retorna dados do usuário autenticado. |
| `POST` | `/solicitacoes/` | Registra nova solicitação em `rascunho`. |
| `GET` | `/solicitacoes/` | Lista solicitações com filtros (`departamento_id`, `situacao`, `categoria`). |
| `GET` | `/solicitacoes/{id}` | Detalha solicitação e histórico completo. |
| `PUT` | `/solicitacoes/{id}` | Edita solicitação enquanto em `rascunho`. |
| `DELETE` | `/solicitacoes/{id}` | Exclui solicitação enquanto em `rascunho`. |
| `POST` | `/solicitacoes/{id}/enviar` | Encaminha de `rascunho` para `aguardando_gestor`. |
| `POST` | `/solicitacoes/{id}/analise-gestor` | Gestor aprova ou recusa solicitação do seu departamento. |
| `POST` | `/solicitacoes/{id}/analise-financeira` | Financeiro realiza análise final (aprova ou recusa). |
| `POST` | `/solicitacoes/{id}/pagar` | Financeiro registra pagamento de solicitação aprovada. |

---

## 4. Matriz de Permissões
| Funcionalidade | Colaborador | Gestor | Financeiro |
| :--- | :---: | :---: | :---: |
| Criar / editar / excluir / enviar própria solicitação (rascunho) | Sim | Não | Não |
| Listar / detalhar próprias solicitações | Sim | - | - |
| Listar / detalhar solicitações do próprio departamento | Não | Sim | - |
| Listar / detalhar solicitações encaminhadas ao financeiro | Não | Não | Sim |
| Aprovar / recusar na etapa de gestor (mesmo departamento) | Não | Sim | Não |
| Aprovar / recusar na etapa financeira | Não | Não | Sim |
| Registrar pagamento | Não | Não | Sim |

---

## 5. Regras de Negócio Implementadas
- **RN01 / RN14**: Autenticação obrigatória via JWT com expiração (`401 Unauthorized`).
- **RN02 / RN03**: Isolamento por dono (colaborador) e por departamento (gestor) com bloqueio `403 Forbidden`.
- **RN04 / RN06**: Validação Pydantic para `valor > 0` e `data_despesa <= hoje` (`422 Unprocessable Entity`).
- **RN05**: Restrição única no banco para impedir comprovante duplicado por colaborador (`409 Conflict`).
- **RN07 / RN08 / RN10**: Máquina de estados rígida impedindo edição fora de rascunho ou etapas fora de ordem (`400 Bad Request`).
- **RN09**: Bloqueio explícito contra autoaprovação (`403 Forbidden`).
- **RN11 / RN12**: Justificativa obrigatória em recusas e gravação de histórico com responsável, etapa, decisão e data/hora.
- **RN13 / RN15**: Senhas armazenadas com hash `bcrypt`, jamais expostas nas respostas; cadastro público fixado em `colaborador`.

---

## 6. Decisões de Segurança
- **Hashing de senhas**: `bcrypt` com salt aleatório por senha.
- **Tokens JWT**: Assinados com `SECRET_KEY` via `.env` e tempo de expiração configurado.
- **Mensagens genéricas no login**: Impede enumeração de e-mails válidos.
- **Controle de acesso em camadas**: Dependências reutilizáveis (`get_current_user` e `exigir_perfil`) combinadas com validação de propriedade e departamento nas rotas.

---

## 7. Como Instalar, Executar e Testar

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Copiar variáveis de ambiente
copy .env.example .env

# 3. (Opcional) Popular banco com dados de teste (senha padrão: senha123)
python seed.py

# 4. Executar testes automatizados (8 cenários de homologação + regras extras)
python -m pytest -v

# 5. Subir servidor local
uvicorn app.main:app --reload
```

Acesse a documentação interativa (Swagger) em: `http://127.0.0.1:8000/docs`
