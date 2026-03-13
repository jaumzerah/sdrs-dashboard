-- SDR Agents database schema
-- PostgreSQL 16+

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lid TEXT UNIQUE,
    jid TEXT,
    numero TEXT,
    usando_lid BOOLEAN NOT NULL DEFAULT FALSE,
    nome TEXT,
    email TEXT,
    origem TEXT,
    plataforma TEXT,
    campanha TEXT,
    canal TEXT,
    chatwoot_contact_id INTEGER,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_leads_lid ON leads(lid);
CREATE INDEX IF NOT EXISTS idx_leads_jid ON leads(jid);
CREATE INDEX IF NOT EXISTS idx_leads_numero ON leads(numero);

CREATE TABLE IF NOT EXISTS disparos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id),
    lid TEXT,
    jid TEXT,
    numero TEXT,
    campanha TEXT NOT NULL,
    disparado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    numero_remetente TEXT
);

CREATE TABLE IF NOT EXISTS agendamentos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id),
    data_hora TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'pendente',
    observacoes TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS avaliacao_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id),
    sdr_origem TEXT NOT NULL,
    nota FLOAT NOT NULL,
    tentativas INT NOT NULL,
    aprovado BOOLEAN NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
