-- ============================================================
--  APPCLINICAS — FASE 1: BANCO MULTI-TENANT
--  Rodar inteiro no Supabase SQL Editor (uma única execução)
--  Gerado em: 2026-04-07
-- ============================================================
-- ÍNDICE:
--   1. Extensões
--   2. Novas tabelas (clinics, clinic_settings, clinic_users, subscriptions)
--   3. Criar tabelas operacionais (patients, appointments, messages, blocked_dates, documents)
--   4. Clínica inicial de desenvolvimento
--   5. Índices de performance
--   6. Trigger — injetar clinic_id no JWT
--   7. RLS — isolamento por tenant
-- ============================================================


-- ============================================================
-- 1. EXTENSÕES
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;


-- ============================================================
-- 2. NOVAS TABELAS
-- ============================================================

-- Tenant principal — cada linha representa uma clínica cliente
CREATE TABLE IF NOT EXISTS clinics (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT        NOT NULL,
    slug          TEXT        NOT NULL UNIQUE,
    plan          TEXT        NOT NULL DEFAULT 'trial'
                                  CHECK (plan   IN ('trial','starter','pro','enterprise')),
    status        TEXT        NOT NULL DEFAULT 'active'
                                  CHECK (status IN ('active','suspended','cancelled')),
    trial_ends_at TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Configurações operacionais por clínica
-- Substitui as variáveis de ambiente hard-coded do .env monolítico
CREATE TABLE IF NOT EXISTS clinic_settings (
    clinic_id               UUID        PRIMARY KEY REFERENCES clinics(id) ON DELETE CASCADE,

    -- Agente IA
    ai_name                 TEXT        NOT NULL DEFAULT 'Secretaria',
    ai_personality          TEXT        NOT NULL DEFAULT 'empatica, calorosa, profissional',

    -- Identidade da clínica
    clinic_display_name     TEXT        NOT NULL,
    doctor_name             TEXT        NOT NULL,
    doctor_phone            TEXT        NOT NULL,

    -- WhatsApp / Meta (tokens armazenados criptografados via Fernet)
    whatsapp_phone_id       TEXT,
    whatsapp_token          TEXT,           -- criptografado
    whatsapp_app_secret     TEXT,           -- criptografado
    whatsapp_verify_token   TEXT,
    whatsapp_configured     BOOLEAN     NOT NULL DEFAULT false,

    -- Google Calendar (credenciais armazenadas criptografadas via Fernet)
    gcal_calendar_id        TEXT,
    gcal_credentials        JSONB,          -- criptografado
    gcal_configured         BOOLEAN     NOT NULL DEFAULT false,

    -- Agenda
    working_days            TEXT[]      NOT NULL DEFAULT ARRAY['monday','tuesday','wednesday','thursday','friday'],
    working_start           TEXT        NOT NULL DEFAULT '08:00',
    working_end             TEXT        NOT NULL DEFAULT '18:00',
    appointment_duration    INTEGER     NOT NULL DEFAULT 50,    -- minutos

    -- Notificações automáticas (hora do dia, 0–23)
    briefing_hour           INTEGER     NOT NULL DEFAULT 8
                                CHECK (briefing_hour      BETWEEN 0 AND 23),
    confirmation_hour       INTEGER     NOT NULL DEFAULT 19
                                CHECK (confirmation_hour  BETWEEN 0 AND 23),

    -- Geral
    timezone                TEXT        NOT NULL DEFAULT 'America/Sao_Paulo',
    test_mode               BOOLEAN     NOT NULL DEFAULT true,
    debug_mode              BOOLEAN     NOT NULL DEFAULT false,

    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Usuários vinculados a cada clínica
CREATE TABLE IF NOT EXISTS clinic_users (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id   UUID        NOT NULL REFERENCES clinics(id)    ON DELETE CASCADE,
    user_id     UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role        TEXT        NOT NULL CHECK (role IN ('owner','doctor','receptionist')),
    is_active   BOOLEAN     NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (clinic_id, user_id)
);

-- Assinaturas Stripe (1:1 com clinics)
CREATE TABLE IF NOT EXISTS subscriptions (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id           UUID        NOT NULL UNIQUE REFERENCES clinics(id) ON DELETE CASCADE,
    stripe_customer_id  TEXT        UNIQUE,
    stripe_sub_id       TEXT        UNIQUE,
    plan                TEXT        NOT NULL,
    status              TEXT        NOT NULL,
    current_period_end  TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ============================================================
-- 3. CRIAR TABELAS OPERACIONAIS (com clinic_id já incluído)
-- ============================================================

-- Pacientes da clínica
CREATE TABLE IF NOT EXISTS patients (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id   UUID        NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    name        TEXT        NOT NULL,
    phone       TEXT        NOT NULL,
    email       TEXT,
    notes       TEXT,
    is_active   BOOLEAN     NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (clinic_id, phone)   -- mesmo número pode existir em clínicas diferentes
);

-- Consultas agendadas
CREATE TABLE IF NOT EXISTS appointments (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id       UUID        NOT NULL REFERENCES clinics(id)    ON DELETE CASCADE,
    patient_id      UUID        NOT NULL REFERENCES patients(id)   ON DELETE CASCADE,
    datetime        TIMESTAMPTZ NOT NULL,
    duration_minutes INTEGER    NOT NULL DEFAULT 50,
    status          TEXT        NOT NULL DEFAULT 'scheduled'
                                    CHECK (status IN ('scheduled','confirmed','cancelled','completed')),
    notes           TEXT,
    google_event_id TEXT,
    is_recurring    BOOLEAN     NOT NULL DEFAULT false,
    recurrence_rule TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Histórico de mensagens WhatsApp
CREATE TABLE IF NOT EXISTS messages (
    id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id            UUID        NOT NULL REFERENCES clinics(id)   ON DELETE CASCADE,
    patient_id           UUID        NOT NULL REFERENCES patients(id)  ON DELETE CASCADE,
    direction            TEXT        NOT NULL CHECK (direction IN ('inbound','outbound')),
    content              TEXT        NOT NULL,
    message_type         TEXT        NOT NULL DEFAULT 'text'
                                         CHECK (message_type IN ('text','audio','image','document')),
    whatsapp_message_id  TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Datas bloqueadas na agenda
CREATE TABLE IF NOT EXISTS blocked_dates (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id   UUID        NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    date        DATE        NOT NULL,
    reason      TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Documentos e base RAG
CREATE TABLE IF NOT EXISTS documents (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id   UUID        NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    name        TEXT        NOT NULL,
    content     TEXT,
    embedding   vector(1536),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ============================================================
-- 4. CLÍNICA INICIAL DE DESENVOLVIMENTO
-- ============================================================
-- UUID fixo e previsível — não altere após a primeira execução.
-- O backend deve ler este ID via variável DEFAULT_CLINIC_ID
-- durante a transição para o modelo multi-tenant completo.

DO $$
DECLARE
    v_clinic_id UUID := '00000000-0000-0000-0000-000000000001';
BEGIN

    -- 4.1 Clínica principal de desenvolvimento
    INSERT INTO clinics (id, name, slug, plan, status, trial_ends_at, created_at)
    VALUES (
        v_clinic_id,
        'Clínica Dev',
        'dev',
        'pro',
        'active',
        NULL,       -- plano pro não tem trial
        now()
    )
    ON CONFLICT (id) DO NOTHING;

    -- 4.2 Configurações da clínica de desenvolvimento
    --     (espelha os valores atuais do .env para não quebrar o sistema)
    INSERT INTO clinic_settings (
        clinic_id,
        ai_name,
        ai_personality,
        clinic_display_name,
        doctor_name,
        doctor_phone,
        whatsapp_phone_id,
        whatsapp_configured,
        gcal_configured,
        working_days,
        working_start,
        working_end,
        appointment_duration,
        briefing_hour,
        confirmation_hour,
        timezone,
        test_mode,
        debug_mode,
        updated_at
    )
    VALUES (
        v_clinic_id,
        'Karen',
        'empatica, calorosa, profissional',
        'Clínica Dev',
        'Dr. Teste',
        '556592170206',
        '1111735818683804',  -- WHATSAPP_PHONE_NUMBER_ID do .env atual
        true,
        false,
        ARRAY['monday','tuesday','wednesday','thursday','friday'],
        '08:00',
        '18:00',
        50,
        8,
        19,
        'America/Sao_Paulo',
        false,
        false,
        now()
    )
    ON CONFLICT (clinic_id) DO NOTHING;

END $$;


-- ============================================================
-- 5. ÍNDICES DE PERFORMANCE
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_clinics_slug             ON clinics(slug);
CREATE INDEX IF NOT EXISTS idx_clinic_users_clinic_id   ON clinic_users(clinic_id);
CREATE INDEX IF NOT EXISTS idx_clinic_users_user_id     ON clinic_users(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_clinic_id  ON subscriptions(clinic_id);
CREATE INDEX IF NOT EXISTS idx_patients_clinic_id       ON patients(clinic_id);
CREATE INDEX IF NOT EXISTS idx_appointments_clinic_id   ON appointments(clinic_id);
CREATE INDEX IF NOT EXISTS idx_messages_clinic_id       ON messages(clinic_id);
CREATE INDEX IF NOT EXISTS idx_blocked_dates_clinic_id  ON blocked_dates(clinic_id);
CREATE INDEX IF NOT EXISTS idx_documents_clinic_id      ON documents(clinic_id);


-- ============================================================
-- 6. TRIGGER — INJETAR clinic_id NO JWT
-- ============================================================
-- Ao vincular um usuário a uma clínica (INSERT/UPDATE em clinic_users),
-- atualiza raw_app_meta_data em auth.users com { "clinic_id": "..." }.
--
-- O JWT gerado na próxima sessão do usuário conterá a claim:
--   auth.jwt() ->> 'clinic_id'
--
-- O backend usa service_role_key (ignora JWT), então isso é
-- exclusivo para o dashboard/frontend futuro.

CREATE OR REPLACE FUNCTION set_clinic_id_in_jwt()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    UPDATE auth.users
    SET raw_app_meta_data =
        COALESCE(raw_app_meta_data, '{}'::JSONB)
        || jsonb_build_object(
            'clinic_id',   NEW.clinic_id::TEXT,
            'clinic_role', NEW.role
        )
    WHERE id = NEW.user_id;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS after_clinic_user_insert ON clinic_users;

CREATE TRIGGER after_clinic_user_insert
    AFTER INSERT OR UPDATE ON clinic_users
    FOR EACH ROW
    EXECUTE FUNCTION set_clinic_id_in_jwt();


-- ============================================================
-- 7. RLS — ISOLAMENTO POR TENANT
-- ============================================================
-- Duas políticas por tabela:
--   • service_role_access : service_role tem acesso total (backend atual)
--   • tenant_isolation    : usuários autenticados veem apenas sua clínica
--
-- Leitura do tenant no JWT:
--   (auth.jwt() ->> 'clinic_id')::UUID
--
-- O backend usa SUPABASE_SERVICE_ROLE_KEY → bypassa RLS automaticamente.
-- Nenhuma mudança de código é necessária no backend atual.

-- ── helpers ───────────────────────────────────────────────────

-- Remove e recria políticas de uma tabela de forma idempotente
-- (evita erro "policy already exists" em re-execuções)

-- ── clinics ───────────────────────────────────────────────────

ALTER TABLE clinics ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "service_role_access" ON clinics;
DROP POLICY IF EXISTS "tenant_isolation"    ON clinics;

CREATE POLICY "service_role_access" ON clinics
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "tenant_isolation" ON clinics
    FOR ALL TO authenticated
    USING (id = (auth.jwt() ->> 'clinic_id')::UUID);

-- ── clinic_settings ───────────────────────────────────────────

ALTER TABLE clinic_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "service_role_access" ON clinic_settings;
DROP POLICY IF EXISTS "tenant_isolation"    ON clinic_settings;

CREATE POLICY "service_role_access" ON clinic_settings
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "tenant_isolation" ON clinic_settings
    FOR ALL TO authenticated
    USING (clinic_id = (auth.jwt() ->> 'clinic_id')::UUID);

-- ── clinic_users ──────────────────────────────────────────────

ALTER TABLE clinic_users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "service_role_access" ON clinic_users;
DROP POLICY IF EXISTS "tenant_isolation"    ON clinic_users;

CREATE POLICY "service_role_access" ON clinic_users
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "tenant_isolation" ON clinic_users
    FOR ALL TO authenticated
    USING (clinic_id = (auth.jwt() ->> 'clinic_id')::UUID);

-- ── subscriptions ─────────────────────────────────────────────

ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "service_role_access" ON subscriptions;
DROP POLICY IF EXISTS "tenant_isolation"    ON subscriptions;

CREATE POLICY "service_role_access" ON subscriptions
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "tenant_isolation" ON subscriptions
    FOR ALL TO authenticated
    USING (clinic_id = (auth.jwt() ->> 'clinic_id')::UUID);

-- ── patients ──────────────────────────────────────────────────

ALTER TABLE patients ENABLE ROW LEVEL SECURITY;

-- Remove todas as políticas antigas (nomes podem variar)
DO $$
DECLARE pol RECORD;
BEGIN
    FOR pol IN
        SELECT policyname FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'patients'
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON patients', pol.policyname);
    END LOOP;
END $$;

CREATE POLICY "service_role_access" ON patients
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "tenant_isolation" ON patients
    FOR ALL TO authenticated
    USING (clinic_id = (auth.jwt() ->> 'clinic_id')::UUID);

-- ── appointments ──────────────────────────────────────────────

ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE pol RECORD;
BEGIN
    FOR pol IN
        SELECT policyname FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'appointments'
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON appointments', pol.policyname);
    END LOOP;
END $$;

CREATE POLICY "service_role_access" ON appointments
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "tenant_isolation" ON appointments
    FOR ALL TO authenticated
    USING (clinic_id = (auth.jwt() ->> 'clinic_id')::UUID);

-- ── messages ──────────────────────────────────────────────────

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE pol RECORD;
BEGIN
    FOR pol IN
        SELECT policyname FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'messages'
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON messages', pol.policyname);
    END LOOP;
END $$;

CREATE POLICY "service_role_access" ON messages
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "tenant_isolation" ON messages
    FOR ALL TO authenticated
    USING (clinic_id = (auth.jwt() ->> 'clinic_id')::UUID);

-- ── blocked_dates ─────────────────────────────────────────────

ALTER TABLE blocked_dates ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE pol RECORD;
BEGIN
    FOR pol IN
        SELECT policyname FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'blocked_dates'
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON blocked_dates', pol.policyname);
    END LOOP;
END $$;

CREATE POLICY "service_role_access" ON blocked_dates
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "tenant_isolation" ON blocked_dates
    FOR ALL TO authenticated
    USING (clinic_id = (auth.jwt() ->> 'clinic_id')::UUID);

-- ── documents ─────────────────────────────────────────────────

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE pol RECORD;
BEGIN
    FOR pol IN
        SELECT policyname FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'documents'
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON documents', pol.policyname);
    END LOOP;
END $$;

CREATE POLICY "service_role_access" ON documents
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "tenant_isolation" ON documents
    FOR ALL TO authenticated
    USING (clinic_id = (auth.jwt() ->> 'clinic_id')::UUID);


-- ============================================================
-- VERIFICAÇÃO FINAL — rode após a execução para conferir
-- ============================================================

-- Tabelas novas
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('clinics','clinic_settings','clinic_users','subscriptions','documents')
ORDER BY table_name;

-- RLS ativo em todas as tabelas
SELECT tablename, rowsecurity AS rls_ativo
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN (
    'clinics','clinic_settings','clinic_users','subscriptions',
    'patients','appointments','messages','blocked_dates','documents'
  )
ORDER BY tablename;

-- Políticas criadas
SELECT tablename, policyname, roles, cmd
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;

-- Clínica inicial inserida
SELECT id, name, slug, plan, status FROM clinics;

-- Settings da clínica dev
SELECT clinic_id, ai_name, doctor_name, doctor_phone,
       whatsapp_phone_id, whatsapp_configured, test_mode
FROM clinic_settings;

-- Contagem de registros migrados com clinic_id
SELECT 'patients'      AS tabela, COUNT(*) AS total, COUNT(clinic_id) AS com_clinic_id FROM patients      UNION ALL
SELECT 'appointments',             COUNT(*),           COUNT(clinic_id)               FROM appointments  UNION ALL
SELECT 'messages',                 COUNT(*),           COUNT(clinic_id)               FROM messages      UNION ALL
SELECT 'blocked_dates',            COUNT(*),           COUNT(clinic_id)               FROM blocked_dates UNION ALL
SELECT 'documents',                COUNT(*),           COUNT(clinic_id)               FROM documents;
