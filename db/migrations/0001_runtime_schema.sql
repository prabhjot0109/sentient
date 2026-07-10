-- 0001_runtime_schema.sql — Sentient multi-project runtime relational core (R1, v3 schema).
-- Idempotent: every statement is CREATE ... IF NOT EXISTS. Mirrored by
-- logic/state/sqlite_store.py::SQLiteStateStore._init() (TEXT ids, INTEGER bools).
-- provider_credentials and chat_messages belong to R7 (0002), not here.

-- Identity. For Neon Auth, external_auth_id = JWT `sub`; users_sync is mirrored here on first login.
-- For local/dev, a single row with external_auth_id = the "__default__" sentinel.
create table if not exists users (
  id                uuid primary key default gen_random_uuid(),
  external_auth_id  text unique,                 -- neon_auth users_sync id / JWT sub
  email             text,
  created_at        timestamptz default now()
);

-- Game-mod (Mantella) path: static key in the URL -> user. Web path uses JWT instead.
create table if not exists api_keys (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references users(id) on delete cascade,
  key_hash    text not null unique,              -- sha256(raw_key); raw key never stored
  label       text,
  revoked     boolean default false,
  created_at  timestamptz default now()
);

-- The "Projects" sidebar layer.
create table if not exists projects (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references users(id) on delete cascade,
  name         text not null,
  base_preset  text not null default 'custom',   -- 'skyrim' | 'fallout4' | 'custom'
  status       text not null default 'active',   -- 'active' | 'reindexing_required'
  created_at   timestamptz default now()
);

-- The dynamic variable matrix — replaces env constants, one row per project.
create table if not exists project_configs (
  project_id            uuid primary key references projects(id) on delete cascade,
  llm_provider          text,
  embedding_provider    text,
  model_name            text,
  embedding_model_name  text,
  temperature           double precision,
  max_tokens            integer,
  mrl_vector_size       integer,                 -- Gemini MRL truncation dim; NULL = provider default
  reasoning_effort      text,
  reasoning_format      text,
  rag_search_type       text,
  rag_top_k             integer,
  rag_fetch_k           integer,
  rag_mmr_lambda        double precision,
  rag_score_threshold   double precision,
  rag_chunk_size        integer,
  rag_chunk_overlap     integer,
  persona_prompt        text,                    -- the project's single editable persona (game voice);
                                                 -- NULL -> base_preset template -> generic
  history_window        integer,                 -- thread-memory messages folded into generation (R7);
                                                 -- NULL = default (20)
  embedding_signature   text,                    -- derived: sha256(provider|model|dim); guards reindex
  updated_at            timestamptz default now()
);

create table if not exists chat_threads (
  id          uuid primary key default gen_random_uuid(),
  project_id  uuid not null references projects(id) on delete cascade,
  npc_name    text,                              -- Mantella speaker label; plain metadata, no FK
  session_id  text not null,                     -- external mod client token (Mantella)
  title       text,                              -- sidebar label (defaults to first user message)
  created_at  timestamptz default now(),
  updated_at  timestamptz default now()
);
create index if not exists chat_threads_session_idx on chat_threads (session_id);

-- Document registry with embedding signature for the reindex guard (R6).
create table if not exists documents (
  id                  uuid primary key default gen_random_uuid(),
  project_id          uuid not null references projects(id) on delete cascade,
  filename            text not null,
  chunk_count         integer default 0,
  embedding_signature text,
  status              text not null default 'processing', -- processing|ready|failed|reindexing
  created_at          timestamptz default now(),
  updated_at          timestamptz default now(),
  unique (project_id, filename)
);
