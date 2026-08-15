-- R7: encrypted provider credentials and durable web-chat memory.
create table if not exists provider_credentials (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references users(id) on delete cascade,
  provider      text not null,
  encrypted_key text not null,
  key_hint      text,
  created_at    timestamptz default now(),
  unique (user_id, provider)
);

create table if not exists chat_messages (
  id          uuid primary key default gen_random_uuid(),
  thread_id   uuid not null references chat_threads(id) on delete cascade,
  role        text not null,
  content     text not null,
  created_at  timestamptz default now()
);

create index if not exists chat_messages_thread_idx on chat_messages (thread_id, created_at);
create unique index if not exists chat_threads_project_session_idx
  on chat_threads (project_id, session_id);
