-- H4: token accounting owned in our own database.
--
-- A quota check cannot query a third-party dashboard on every request, so these
-- counters live here regardless of what tracing sits on top (H8). Nullable on
-- purpose: a user message has no usage, and some providers report none. A
-- default of 0 would turn missing telemetry into a real-looking zero in every
-- sum built on top of these columns.
alter table chat_messages add column if not exists model             text;
alter table chat_messages add column if not exists prompt_tokens     integer;
alter table chat_messages add column if not exists completion_tokens integer;
alter table chat_messages add column if not exists total_tokens      integer;

-- H6: the per-user storage quota needs a number to sum. bigint, not integer:
-- a per-user total crosses 2 GB long before a single upload does.
alter table documents add column if not exists size_bytes bigint;
