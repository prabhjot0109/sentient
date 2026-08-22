-- G4: reconstruct game-conversation identity from the payload.
--
-- Mantella sends no session_id, but it re-sends the whole conversation every
-- turn. The transcript stored after turn N equals the payload arriving at turn
-- N+1 minus the system message and minus the final user turn, so hashing that
-- slice keys a thread with no client change. `prefix_hash` holds the hash the
-- NEXT turn is expected to arrive with; it advances on every turn.
alter table chat_threads add column if not exists prefix_hash text;

create index if not exists chat_threads_project_prefix_idx
  on chat_threads (project_id, prefix_hash);
