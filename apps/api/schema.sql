-- Al-Mu'allim — no-ads billing, progress and AI cost controls.
-- PostgreSQL 15+. Run in a controlled migration (never expose this file to browsers).
-- Authentication is external; auth_subject is the stable verified OIDC subject.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$ BEGIN
  CREATE TYPE am_tier AS ENUM ('free','pro_monthly','pro_annual','family_annual');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
  CREATE TYPE am_provider AS ENUM ('stripe','revenuecat','scholarship');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  auth_subject TEXT NOT NULL UNIQUE,
  email TEXT,
  timezone_name TEXT NOT NULL DEFAULT 'Europe/London',
  -- Once a local quota day begins, changing timezone must be separately verified.
  quota_timezone_name TEXT NOT NULL DEFAULT 'Europe/London',
  country_code CHAR(2),
  stripe_customer_id TEXT UNIQUE,
  revenuecat_app_user_id TEXT UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ,
  CHECK (country_code IS NULL OR country_code ~ '^[A-Z]{2}$')
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users (lower(email));

CREATE TABLE IF NOT EXISTS family_groups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  max_members SMALLINT NOT NULL DEFAULT 5 CHECK (max_members = 5),
  invite_code_hash BYTEA UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  dissolved_at TIMESTAMPTZ,
  UNIQUE (owner_user_id)
);
CREATE TABLE IF NOT EXISTS family_memberships (
  family_group_id UUID NOT NULL REFERENCES family_groups(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('owner','member')),
  joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (family_group_id,user_id),
  UNIQUE (user_id)
);
-- Concurrent invitations must not overfill a group.
CREATE OR REPLACE FUNCTION enforce_family_capacity() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE allowed_count INTEGER; member_count INTEGER;
BEGIN
  PERFORM 1 FROM family_groups WHERE id=NEW.family_group_id
    AND dissolved_at IS NULL FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Family group unavailable'; END IF;
  SELECT max_members INTO allowed_count FROM family_groups WHERE id=NEW.family_group_id;
  SELECT count(*) INTO member_count FROM family_memberships
    WHERE family_group_id=NEW.family_group_id;
  IF member_count >= allowed_count THEN RAISE EXCEPTION 'Family group full'; END IF;
  IF NEW.role = 'owner' AND NOT EXISTS (
    SELECT 1 FROM family_groups g WHERE g.id=NEW.family_group_id
    AND g.owner_user_id=NEW.user_id
  ) THEN RAISE EXCEPTION 'Incorrect owner'; END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_family_capacity ON family_memberships;
CREATE TRIGGER trg_family_capacity BEFORE INSERT ON family_memberships
FOR EACH ROW EXECUTE FUNCTION enforce_family_capacity();

CREATE TABLE IF NOT EXISTS subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider am_provider NOT NULL,
  provider_subscription_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  tier am_tier NOT NULL CHECK (tier <> 'free'),
  status TEXT NOT NULL CHECK (status IN (
    'trialing','active','past_due','paused','canceled','expired','unpaid','pending')),
  period_started_at TIMESTAMPTZ,
  current_period_end TIMESTAMPTZ,
  trial_end TIMESTAMPTZ,
  cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE,
  source_event_at TIMESTAMPTZ,
  environment TEXT NOT NULL DEFAULT 'production' CHECK (environment IN ('production','sandbox')),
  last_verified_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (provider,provider_subscription_id,environment)
);
CREATE INDEX IF NOT EXISTS idx_subs_user_active ON subscriptions(user_id,status,current_period_end);
CREATE INDEX IF NOT EXISTS idx_subs_owner_tier ON subscriptions(user_id,tier,current_period_end);

-- A one-time, short-lived invitation. Only hashed tokens are stored.
CREATE TABLE IF NOT EXISTS family_invites (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  family_group_id UUID NOT NULL REFERENCES family_groups(id) ON DELETE CASCADE,
  token_hash CHAR(64) NOT NULL UNIQUE,
  invited_email TEXT,
  expires_at TIMESTAMPTZ NOT NULL,
  accepted_by UUID REFERENCES users(id) ON DELETE SET NULL,
  accepted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_family_invites_group ON family_invites(family_group_id,expires_at);

-- Prevent two simultaneous upgrades from claiming the same free trial.
CREATE TABLE IF NOT EXISTS trial_claims (
  user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  first_claimed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  provider am_provider NOT NULL CHECK(provider IN ('stripe','revenuecat'))
);

-- Store dashboard price IDs; prices are never trusted from client-side currency selection.
CREATE TABLE IF NOT EXISTS billing_price_catalog (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  provider am_provider NOT NULL CHECK (provider IN ('stripe','revenuecat')),
  provider_price_or_product_id TEXT NOT NULL,
  country_code CHAR(2) NOT NULL CHECK (country_code ~ '^[A-Z]{2}$'),
  currency CHAR(3) NOT NULL,
  amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
  tier am_tier NOT NULL CHECK (tier <> 'free'),
  trial_days SMALLINT NOT NULL DEFAULT 0 CHECK (trial_days IN (0,7)),
  enabled BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE(provider,provider_price_or_product_id,country_code)
);
CREATE INDEX IF NOT EXISTS idx_price_country ON billing_price_catalog(provider,country_code,tier,enabled);

-- A timezone-safe day is computed once from users.quota_timezone_name.
CREATE TABLE IF NOT EXISTS daily_ai_quotas (
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  local_day DATE NOT NULL,
  timezone_name TEXT NOT NULL,
  verse_unlocks_used SMALLINT NOT NULL DEFAULT 0 CHECK (verse_unlocks_used BETWEEN 0 AND 3),
  qna_used SMALLINT NOT NULL DEFAULT 0 CHECK (qna_used BETWEEN 0 AND 5),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id,local_day)
);
-- Distinct verses: repeat visits to an unlocked lesson do not consume another credit.
CREATE TABLE IF NOT EXISTS verse_daily_unlocks (
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  local_day DATE NOT NULL,
  surah SMALLINT NOT NULL CHECK (surah BETWEEN 1 AND 114),
  ayah SMALLINT NOT NULL CHECK (ayah BETWEEN 1 AND 286),
  unlocked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id,local_day,surah,ayah)
);

-- One request identifier for retry-safe Q&A billing; no prompt/voice recording retained.
CREATE TABLE IF NOT EXISTS ai_usage_events (
  request_id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  operation TEXT NOT NULL CHECK (operation IN ('verse_studio','teacher_qna')),
  charged BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_usage_user_date ON ai_usage_events(user_id,created_at);

CREATE TABLE IF NOT EXISTS scholarship_gifts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  checkout_session_id TEXT NOT NULL UNIQUE,
  donor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  currency CHAR(3) NOT NULL,
  amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
  payment_status TEXT NOT NULL DEFAULT 'pending' CHECK (payment_status IN ('pending','paid','refunded')),
  received_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS scholarships (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  request_note TEXT CHECK (length(request_note) <= 500),
  request_status TEXT NOT NULL DEFAULT 'pending' CHECK (request_status IN ('pending','approved','declined','revoked')),
  months_requested SMALLINT NOT NULL CHECK (months_requested IN (3,6)),
  approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
  sponsor_gift_id UUID REFERENCES scholarship_gifts(id) ON DELETE SET NULL,
  granted_at TIMESTAMPTZ,
  valid_until TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK ((request_status <> 'approved') OR
         (granted_at IS NOT NULL AND valid_until IS NOT NULL AND valid_until > granted_at))
);
CREATE UNIQUE INDEX IF NOT EXISTS uniq_pending_scholarship ON scholarships(user_id)
 WHERE request_status='pending';
CREATE INDEX IF NOT EXISTS idx_scholarship_active ON scholarships(user_id,valid_until)
 WHERE request_status='approved';

-- One canonical, reusable result per verse/language/evidence/prompt version.
-- Only validated responses may be published. Manual review is a separate grade.
CREATE TABLE IF NOT EXISTS verse_studio_cache (
  surah SMALLINT NOT NULL CHECK (surah BETWEEN 1 AND 114),
  ayah SMALLINT NOT NULL CHECK (ayah BETWEEN 1 AND 286),
  language VARCHAR(12) NOT NULL,
  content_version TEXT NOT NULL,
  source_digest CHAR(64) NOT NULL,
  tafsir_json JSONB,
  drills_json JSONB,
  verified_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
  validation_status TEXT NOT NULL DEFAULT 'pending' CHECK (
    validation_status IN ('pending','automated_pass','scholar_reviewed','rejected')),
  generated_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (surah,ayah,language,content_version,source_digest),
  CHECK (tafsir_json IS NULL OR jsonb_typeof(tafsir_json)='object'),
  CHECK (drills_json IS NULL OR jsonb_typeof(drills_json)='object'),
  CHECK (jsonb_typeof(verified_sources)='array')
);
CREATE INDEX IF NOT EXISTS idx_cache_published ON verse_studio_cache(surah,ayah,language)
 WHERE validation_status IN ('automated_pass','scholar_reviewed');
-- AI topic-answer cache may contain only approved generic educational answers.
CREATE TABLE IF NOT EXISTS approved_faq_cache (
  canonical_topic TEXT NOT NULL,
  language VARCHAR(12) NOT NULL,
  prompt_version TEXT NOT NULL,
  answer_json JSONB NOT NULL,
  review_status TEXT NOT NULL CHECK(review_status IN ('reviewed','pending')),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(canonical_topic,language,prompt_version)
);

-- Deduplication must be transactionally committed alongside state mutations.
CREATE TABLE IF NOT EXISTS billing_webhook_events (
  provider am_provider NOT NULL CHECK (provider IN ('stripe','revenuecat')),
  event_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  event_at TIMESTAMPTZ,
  processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (provider,event_id)
);
CREATE TABLE IF NOT EXISTS billing_reconciliation_queue (
  provider am_provider NOT NULL,
  external_user_id TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (provider, external_user_id)
);

-- If using Supabase direct client access, enable RLS and explicit policies.
-- This schema assumes DB credentials are held ONLY by the FastAPI backend.
-- The app role must never permit direct browser SQL access.
