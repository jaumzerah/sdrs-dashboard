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

### Setup inicial da VPS (executar uma unica vez)

```bash
# 1. Adicionar usuario debian ao grupo docker
#    OBRIGATORIO — sem isso o CI/CD falha
sudo usermod -aG docker debian
# Fazer logout e login novamente para o grupo ser aplicado
# Verificar: groups | grep docker

# 2. Criar diretorio do projeto
sudo mkdir -p /opt/sdr-agents
sudo chown debian:debian /opt/sdr-agents

# 3. Clonar o repositorio
cd /opt
git clone <URL_DO_REPOSITORIO> sdr-agents

# 4. Criar o .env de producao
cd /opt/sdr-agents
cp .env.example .env
nano .env  # preencher com valores reais de producao

# 5. Garantir que Docker reinicia apos reboot da VPS
sudo systemctl enable docker

# 6. Subir o stack pela primeira vez
docker compose -f docker-compose.prod.yml up -d

# 7. Verificar se os 4 servicos subiram
docker compose -f docker-compose.prod.yml ps
```

### Secrets necessarios no GitHub Actions

Configurar em Settings -> Secrets and variables -> Actions:

- `VPS_HOST`      # IP ou dominio da VPS
- `VPS_USER`      # debian
- `VPS_SSH_KEY`   # conteudo da chave privada SSH dedicada ao deploy

Gerar par de chaves SSH dedicado para o deploy
(nao reutilizar chave pessoal):

```bash
ssh-keygen -t ed25519 -C "deploy@sdr-agents" -f ~/.ssh/sdr_deploy
```

Adicionar `~/.ssh/sdr_deploy.pub` ao `~/.ssh/authorized_keys` da VPS.
Cadastrar conteudo de `~/.ssh/sdr_deploy` no secret `VPS_SSH_KEY`.

### Fluxo apos setup

Todo push na branch `main`:

1. Testes rodam no GitHub Actions
2. Se passar: `deploy.sh` executa na VPS via SSH
3. Se falhar: deploy e bloqueado automaticamente

NUNCA commitar o `.env` real no repositorio.
