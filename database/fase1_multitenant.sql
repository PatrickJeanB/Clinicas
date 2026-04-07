-- ============================================================
--  FASE 1 — MULTI-TENANT APPCLINICAS
--  Rodar no Supabase SQL Editor (uma única execução)
--  Data: 2026-04-07
-- ============================================================
-- ORDEM DE EXECUÇÃO:
--   1. Novas tabelas (clinics, clinic_settings, clinic_users, subscriptions)
--   2. Adicionar clinic_id nas tabelas existentes
--   3. Inserir clínica inicial + preencher dados existentes
--   4. Índices de performance
--   5. Trigger → injeta clinic_id no JWT
--   6. RLS — isolamento por tenant
--   7. Verificação final
-- ============================================================


-- ============================================================
-- SEÇÃO 1: NOVAS TABELAS
-- ============================================================

-- 1.1 Clínicas (tenant raiz)
CREATE TABLE IF NOT EXISTS clinics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    slug            TEXT NOT NULL UNIQUE,
    plan            TEXT NOT NULL DEFAULT 'trial'
                        CHECK (plan IN ('trial','starter','pro','enterprise')),
    status          TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','suspended','cancelled')),
    trial_ends_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE clinics IS 'Tenant raiz do SaaS — cada linha é uma clínica cliente.';

-- 1.2 Configurações por clínica (substitui variáveis do .env hard-coded)
CREATE TABLE IF NOT EXISTS clinic_settings (
    clinic_id               UUID PRIMARY KEY REFERENCES clinics(id) ON DELETE CASCADE,

    -- IA
    ai_name                 TEXT        NOT NULL DEFAULT 'Assistente',
    ai_personality          TEXT,

    -- Identidade da clínica
    clinic_display_name     TEXT,
    doctor_name             TEXT,
    doctor_phone            TEXT,

    -- WhatsApp
    whatsapp_phone_id       TEXT,
    whatsapp_token          TEXT,           -- armazenado criptografado (Fernet)
    whatsapp_app_secret     TEXT,           -- armazenado criptografado (Fernet)
    whatsapp_verify_token   TEXT,
    whatsapp_configured     BOOLEAN NOT NULL DEFAULT FALSE,

    -- Google Calendar
    gcal_calendar_id        TEXT,
    gcal_credentials        JSONB,          -- armazenado criptografado (Fernet)
    gcal_configured         BOOLEAN NOT NULL DEFAULT FALSE,

    -- Agenda
    working_days            INTEGER[]   NOT NULL DEFAULT '{1,2,3,4,5}',
                                                -- 0=Dom 1=Seg … 6=Sáb
    working_start           TIME        NOT NULL DEFAULT '08:00',
    working_end             TIME        NOT NULL DEFAULT '18:00',
    appointment_duration    INTEGER     NOT NULL DEFAULT 50,    -- minutos

    -- Notificações agendadas
    briefing_hour           INTEGER     NOT NULL DEFAULT 7      -- hora 0-23
                                CHECK (briefing_hour BETWEEN 0 AND 23),
    confirmation_hour       INTEGER     NOT NULL DEFAULT 9
                                CHECK (confirmation_hour BETWEEN 0 AND 23),

    -- Geral
    timezone                TEXT        NOT NULL DEFAULT 'America/Sao_Paulo',
    test_mode               BOOLEAN     NOT NULL DEFAULT FALSE,
    debug_mode              BOOLEAN     NOT NULL DEFAULT FALSE,

    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE clinic_settings IS 'Configurações operacionais por clínica — substitui .env por tenant.';
COMMENT ON COLUMN clinic_settings.whatsapp_token     IS 'Criptografado com Fernet (ENCRYPTION_KEY).';
COMMENT ON COLUMN clinic_settings.whatsapp_app_secret IS 'Criptografado com Fernet (ENCRYPTION_KEY).';
COMMENT ON COLUMN clinic_settings.gcal_credentials   IS 'JSON criptografado com Fernet (ENCRYPTION_KEY).';

-- 1.3 Usuários vinculados à clínica
CREATE TABLE IF NOT EXISTS clinic_users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id   UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role        TEXT NOT NULL DEFAULT 'receptionist'
                    CHECK (role IN ('owner','doctor','receptionist')),
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (clinic_id, user_id)
);

COMMENT ON TABLE clinic_users IS 'Membros de cada clínica e seus papéis (owner/doctor/receptionist).';

-- 1.4 Billing — assinaturas Stripe
CREATE TABLE IF NOT EXISTS subscriptions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id           UUID NOT NULL UNIQUE REFERENCES clinics(id) ON DELETE CASCADE,
    stripe_customer_id  TEXT,
    stripe_sub_id       TEXT,
    plan                TEXT NOT NULL DEFAULT 'trial'
                            CHECK (plan IN ('trial','starter','pro','enterprise')),
    status              TEXT NOT NULL DEFAULT 'active',
    current_period_end  TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE subscriptions IS 'Assinatura Stripe por clínica (1:1 com clinics).';


-- ============================================================
-- SEÇÃO 2: ADICIONAR clinic_id NAS TABELAS EXISTENTES
-- ============================================================
-- Coluna adicionada como nullable agora; NOT NULL é aplicado
-- na Seção 3, após preenchimento dos dados existentes.

ALTER TABLE patients
    ADD COLUMN IF NOT EXISTS clinic_id UUID REFERENCES clinics(id) ON DELETE CASCADE;

ALTER TABLE appointments
    ADD COLUMN IF NOT EXISTS clinic_id UUID REFERENCES clinics(id) ON DELETE CASCADE;

ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS clinic_id UUID REFERENCES clinics(id) ON DELETE CASCADE;

ALTER TABLE blocked_dates
    ADD COLUMN IF NOT EXISTS clinic_id UUID REFERENCES clinics(id) ON DELETE CASCADE;

-- documents pode não existir ainda — usa IF EXISTS
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'documents'
    ) THEN
        ALTER TABLE documents
            ADD COLUMN IF NOT EXISTS clinic_id UUID REFERENCES clinics(id) ON DELETE CASCADE;
    END IF;
END $$;


-- ============================================================
-- SEÇÃO 3: CLÍNICA INICIAL + BACKFILL DOS DADOS EXISTENTES
-- ============================================================
-- UUID fixo para a clínica padrão — não mude após rodar!
-- Use este ID ao configurar o backend na migração Fase 2.

INSERT INTO clinics (id, name, slug, plan, status, trial_ends_at, created_at)
VALUES (
    '00000000-0000-0000-0000-000000000001'::UUID,
    'Clínica Principal',
    'clinica-principal',
    'trial',
    'active',
    NOW() + INTERVAL '30 days',
    NOW()
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO clinic_settings (
    clinic_id,
    ai_name,
    ai_personality,
    clinic_display_name,
    doctor_name,
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
    '00000000-0000-0000-0000-000000000001'::UUID,
    'Assistente',
    'Profissional, empática e acolhedora',
    'AppClinicas',
    'Dr. Profissional',
    FALSE,
    FALSE,
    '{1,2,3,4,5}',
    '08:00',
    '18:00',
    50,
    7,
    9,
    'America/Sao_Paulo',
    FALSE,
    FALSE,
    NOW()
)
ON CONFLICT (clinic_id) DO NOTHING;

-- Preenche clinic_id em todos os registros já existentes
UPDATE patients
    SET clinic_id = '00000000-0000-0000-0000-000000000001'::UUID
    WHERE clinic_id IS NULL;

UPDATE appointments
    SET clinic_id = '00000000-0000-0000-0000-000000000001'::UUID
    WHERE clinic_id IS NULL;

UPDATE messages
    SET clinic_id = '00000000-0000-0000-0000-000000000001'::UUID
    WHERE clinic_id IS NULL;

UPDATE blocked_dates
    SET clinic_id = '00000000-0000-0000-0000-000000000001'::UUID
    WHERE clinic_id IS NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'documents'
    ) THEN
        EXECUTE '
            UPDATE documents
            SET clinic_id = ''00000000-0000-0000-0000-000000000001''::UUID
            WHERE clinic_id IS NULL
        ';
    END IF;
END $$;

-- Agora que o backfill foi feito, aplica NOT NULL
-- (falha se ainda houver NULLs — indicativo de problema a resolver antes)
ALTER TABLE patients      ALTER COLUMN clinic_id SET NOT NULL;
ALTER TABLE appointments  ALTER COLUMN clinic_id SET NOT NULL;
ALTER TABLE messages      ALTER COLUMN clinic_id SET NOT NULL;
ALTER TABLE blocked_dates ALTER COLUMN clinic_id SET NOT NULL;


-- ============================================================
-- SEÇÃO 4: ÍNDICES DE PERFORMANCE
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_patients_clinic_id       ON patients(clinic_id);
CREATE INDEX IF NOT EXISTS idx_appointments_clinic_id   ON appointments(clinic_id);
CREATE INDEX IF NOT EXISTS idx_messages_clinic_id       ON messages(clinic_id);
CREATE INDEX IF NOT EXISTS idx_blocked_dates_clinic_id  ON blocked_dates(clinic_id);
CREATE INDEX IF NOT EXISTS idx_clinic_users_clinic_id   ON clinic_users(clinic_id);
CREATE INDEX IF NOT EXISTS idx_clinic_users_user_id     ON clinic_users(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_clinic_id  ON subscriptions(clinic_id);
CREATE INDEX IF NOT EXISTS idx_clinics_slug             ON clinics(slug);


-- ============================================================
-- SEÇÃO 5: TRIGGER — INJETA clinic_id NO JWT
-- ============================================================
-- Quando um usuário é vinculado a uma clínica (INSERT/UPDATE em
-- clinic_users), seu raw_app_meta_data é atualizado com clinic_id
-- e clinic_role. Esses valores aparecem no JWT na próxima sessão:
--   auth.jwt() -> 'app_metadata' ->> 'clinic_id'
--   auth.jwt() -> 'app_metadata' ->> 'clinic_role'

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

COMMENT ON FUNCTION set_clinic_id_in_jwt() IS
    'Injeta clinic_id e clinic_role no app_metadata do JWT após vincular usuário à clínica.';

DROP TRIGGER IF EXISTS after_clinic_user_insert ON clinic_users;

CREATE TRIGGER after_clinic_user_insert
    AFTER INSERT OR UPDATE ON clinic_users
    FOR EACH ROW
    EXECUTE FUNCTION set_clinic_id_in_jwt();


-- ============================================================
-- SEÇÃO 6: RLS — ISOLAMENTO POR TENANT
-- ============================================================
-- Leitura do tenant do JWT:
--   (auth.jwt() -> 'app_metadata' ->> 'clinic_id')::UUID
--
-- service_role bypassa RLS automaticamente, mas criamos política
-- explícita para deixar a intenção documentada no banco.
-- O backend usa SUPABASE_SERVICE_ROLE_KEY → acesso total garantido.

-- Helper reutilizável
-- Retorna o clinic_id do JWT autenticado (NULL se não autenticado)
CREATE OR REPLACE FUNCTION current_clinic_id()
RETURNS UUID
LANGUAGE sql
STABLE
AS $$
    SELECT (auth.jwt() -> 'app_metadata' ->> 'clinic_id')::UUID;
$$;

-- ── clinics ───────────────────────────────────────────────────
ALTER TABLE clinics ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_isolation"       ON clinics;
DROP POLICY IF EXISTS "service_role_full_access" ON clinics;

CREATE POLICY "tenant_isolation" ON clinics
    FOR ALL TO authenticated
    USING (id = current_clinic_id());

CREATE POLICY "service_role_full_access" ON clinics
    FOR ALL TO service_role
    USING (true) WITH CHECK (true);

-- ── clinic_settings ───────────────────────────────────────────
ALTER TABLE clinic_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_isolation"         ON clinic_settings;
DROP POLICY IF EXISTS "service_role_full_access" ON clinic_settings;

CREATE POLICY "tenant_isolation" ON clinic_settings
    FOR ALL TO authenticated
    USING (clinic_id = current_clinic_id());

CREATE POLICY "service_role_full_access" ON clinic_settings
    FOR ALL TO service_role
    USING (true) WITH CHECK (true);

-- ── clinic_users ──────────────────────────────────────────────
ALTER TABLE clinic_users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_isolation"         ON clinic_users;
DROP POLICY IF EXISTS "service_role_full_access" ON clinic_users;

CREATE POLICY "tenant_isolation" ON clinic_users
    FOR ALL TO authenticated
    USING (clinic_id = current_clinic_id());

CREATE POLICY "service_role_full_access" ON clinic_users
    FOR ALL TO service_role
    USING (true) WITH CHECK (true);

-- ── subscriptions ─────────────────────────────────────────────
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_isolation"         ON subscriptions;
DROP POLICY IF EXISTS "service_role_full_access" ON subscriptions;

CREATE POLICY "tenant_isolation" ON subscriptions
    FOR ALL TO authenticated
    USING (clinic_id = current_clinic_id());

CREATE POLICY "service_role_full_access" ON subscriptions
    FOR ALL TO service_role
    USING (true) WITH CHECK (true);

-- ── patients ──────────────────────────────────────────────────
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE pol RECORD;
BEGIN
    FOR pol IN SELECT policyname FROM pg_policies WHERE tablename = 'patients' AND schemaname = 'public' LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON patients', pol.policyname);
    END LOOP;
END $$;

CREATE POLICY "tenant_isolation" ON patients
    FOR ALL TO authenticated
    USING (clinic_id = current_clinic_id());

CREATE POLICY "service_role_full_access" ON patients
    FOR ALL TO service_role
    USING (true) WITH CHECK (true);

-- ── appointments ──────────────────────────────────────────────
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE pol RECORD;
BEGIN
    FOR pol IN SELECT policyname FROM pg_policies WHERE tablename = 'appointments' AND schemaname = 'public' LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON appointments', pol.policyname);
    END LOOP;
END $$;

CREATE POLICY "tenant_isolation" ON appointments
    FOR ALL TO authenticated
    USING (clinic_id = current_clinic_id());

CREATE POLICY "service_role_full_access" ON appointments
    FOR ALL TO service_role
    USING (true) WITH CHECK (true);

-- ── messages ──────────────────────────────────────────────────
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE pol RECORD;
BEGIN
    FOR pol IN SELECT policyname FROM pg_policies WHERE tablename = 'messages' AND schemaname = 'public' LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON messages', pol.policyname);
    END LOOP;
END $$;

CREATE POLICY "tenant_isolation" ON messages
    FOR ALL TO authenticated
    USING (clinic_id = current_clinic_id());

CREATE POLICY "service_role_full_access" ON messages
    FOR ALL TO service_role
    USING (true) WITH CHECK (true);

-- ── blocked_dates ─────────────────────────────────────────────
ALTER TABLE blocked_dates ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE pol RECORD;
BEGIN
    FOR pol IN SELECT policyname FROM pg_policies WHERE tablename = 'blocked_dates' AND schemaname = 'public' LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON blocked_dates', pol.policyname);
    END LOOP;
END $$;

CREATE POLICY "tenant_isolation" ON blocked_dates
    FOR ALL TO authenticated
    USING (clinic_id = current_clinic_id());

CREATE POLICY "service_role_full_access" ON blocked_dates
    FOR ALL TO service_role
    USING (true) WITH CHECK (true);

-- ── documents (se existir) ────────────────────────────────────
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'documents'
    ) THEN
        EXECUTE 'ALTER TABLE documents ENABLE ROW LEVEL SECURITY';

        -- Remove todas as políticas existentes
        DECLARE pol RECORD;
        BEGIN
            FOR pol IN
                SELECT policyname FROM pg_policies
                WHERE tablename = 'documents' AND schemaname = 'public'
            LOOP
                EXECUTE format('DROP POLICY IF EXISTS %I ON documents', pol.policyname);
            END LOOP;
        END;

        EXECUTE '
            CREATE POLICY "tenant_isolation" ON documents
                FOR ALL TO authenticated
                USING (clinic_id = current_clinic_id())
        ';
        EXECUTE '
            CREATE POLICY "service_role_full_access" ON documents
                FOR ALL TO service_role
                USING (true) WITH CHECK (true)
        ';
    END IF;
END $$;


-- ============================================================
-- SEÇÃO 7: VERIFICAÇÃO FINAL
-- ============================================================

-- 7.1 Tabelas novas criadas
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('clinics','clinic_settings','clinic_users','subscriptions')
ORDER BY table_name;

-- 7.2 RLS habilitado em todas as tabelas relevantes
SELECT tablename, rowsecurity AS rls_enabled
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN (
    'clinics','clinic_settings','clinic_users','subscriptions',
    'patients','appointments','messages','blocked_dates'
  )
ORDER BY tablename;

-- 7.3 Políticas criadas
SELECT tablename, policyname, roles, cmd
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;

-- 7.4 Clínica inicial inserida
SELECT id, name, slug, plan, status, trial_ends_at FROM clinics;

-- 7.5 Contagem de registros migrados com clinic_id
SELECT
    'patients'      AS tabela, COUNT(*) AS total, COUNT(clinic_id) AS com_clinic_id FROM patients
UNION ALL SELECT
    'appointments',            COUNT(*),           COUNT(clinic_id)               FROM appointments
UNION ALL SELECT
    'messages',                COUNT(*),           COUNT(clinic_id)               FROM messages
UNION ALL SELECT
    'blocked_dates',           COUNT(*),           COUNT(clinic_id)               FROM blocked_dates;
