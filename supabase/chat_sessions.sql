create extension if not exists pgcrypto;
create table if not exists public.chat_sessions (
    id uuid primary key default gen_random_uuid(),
    client_id text not null,
    title text not null,
    preview text not null default '',
    messages jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists chat_sessions_client_id_updated_at_idx on public.chat_sessions (client_id, updated_at desc);