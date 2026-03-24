# LangGraph Supervisor (OpenAI)

Projeto base para criar workflows com LangGraph usando o modelo `gpt-4o`, arquitetura com supervisor, observabilidade no LangSmith (US) e persistencia com Postgres.

## Arquitetura

- `workflow_supervisor`: agente orquestrador.
- `math_expert`: agente para operacoes numericas (`add`, `multiply`, `divide`).
- `workflow_research_expert`: agente para orientacoes de setup LangGraph/LangSmith.

Implementacao principal em `src/agent/graph.py`.

## Requisitos

- Python 3.11+
- Credenciais:
  - `OPENAI_API_KEY`
  - `LANGSMITH_API_KEY`

## Setup rapido

```bash
python -m venv .venv
. .venv/Scripts/activate
python -m pip install -U pip
python -m pip install -e . "langgraph-cli[inmem]"
copy .env.example .env
```

Edite `.env` com suas chaves.

## Rodando local com Studio

```bash
PYTHONIOENCODING=utf-8 python -m langgraph_cli dev
```

Saidas esperadas:

- API: `http://127.0.0.1:2024`
- Docs: `http://127.0.0.1:2024/docs`
- Studio: `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`

## Testando via SDK (async)

```bash
python scripts/smoke_sdk_async.py
```

## Persistencia com Postgres (producao)

Quando `POSTGRES_CHECKPOINT_URI` estiver definido no `.env`, o graph habilita `PostgresSaver` automaticamente durante o `compile()`.

Exemplo:

```text
POSTGRES_PORT=5433
POSTGRES_CHECKPOINT_URI=postgresql://user:pass@host:5433/db
DATABASE_URL=postgresql://user:pass@host:5433/sdr_agents
```

Nota: usamos porta `5433` por padrao para evitar conflito com Postgres local em `5432`.

Sempre use `thread_id` em `configurable` para continuidade de estado entre interacoes.

## Testes

```bash
python -m pytest -q
```

## Pre-requisitos para validacao ponta a ponta

Antes de executar a Fase 13E (mensagem real via WhatsApp), preencha no `.env` local:

- `EVOLUTION_API_URL`
- `EVOLUTION_API_KEY`
- `EVOLUTION_INSTANCE`
- `CHATWOOT_URL`
- `CHATWOOT_API_TOKEN`
- `CHATWOOT_ACCOUNT_ID`
- `CHATWOOT_INBOX_ID`
- `LANGSMITH_PROJECT=sdr-agents`

Sem essas variaveis, o diagnostico vai marcar Evolution/Chatwoot como indisponiveis e o teste ponta a ponta ficara pendente.

## Deploy em producao

```bash
# Pre-requisito: SimplifiqueNet deve existir e estar
# com os servicos dependentes rodando
# Verificar: docker service ls

# Build da imagem (primeira vez e apos alteracoes)
cd /opt/sdr-agents
docker build -t sdr-agents:latest .

# Carregar variaveis e fazer deploy
set -a && source .env && set +a
docker stack deploy -c docker-stack.sdr.yml sdr-agents

# Verificar servicos
docker stack ps sdr-agents

# Para atualizar apos push no GitHub:
bash scripts/deploy.sh
```

## Dashboard SDR (servico separado)

Foi adicionada uma dashboard operacional separada com login/senha proprios, observabilidade de filas/integracoes e Prompt Studio com `draft`, `publish` e `rollback`.

- App: `src/dashboard_app/`
- Stack Swarm: `docker-stack.dashboard.yml`
- Dominio: `sdrs.agenciasimplifique.com.br`

### Variaveis minimas da dashboard

- `DASHBOARD_ADMIN_USER`
- `DASHBOARD_ADMIN_PASSWORD`
- `DASHBOARD_SESSION_SECRET`
- `DATABASE_URL`
- `RABBITMQ_MGMT_URL`, `RABBITMQ_MGMT_USER`, `RABBITMQ_MGMT_PASS`
- `CHATWOOT_URL`, `CHATWOOT_API_TOKEN`
- `EVOLUTION_API_URL`, `EVOLUTION_API_KEY`

### Deploy da dashboard

```bash
cd /opt/sdr-agents
docker build -t sdr-dashboard:latest .
docker stack deploy -c docker-stack.dashboard.yml sdr-dashboard
docker stack ps sdr-dashboard
```
