-- PgVectorBackend's storage belongs in the same Postgres instance as state.
--
-- `embedding vector` intentionally has no dimension typmod. Different projects
-- may choose different embedding providers or MRL dimensions, and pgvector
-- supports variable-dimension vectors in one column. A shared Qdrant collection
-- cannot: its dense dimension is fixed by whichever project writes first.
--
-- That trade-off means there is deliberately no one-size-fits-all HNSW index:
-- pgvector indexes variable dimensions with expression + partial indexes, which
-- must be picked per model/dimension from real traffic. The ordinary btree scope
-- index still narrows each query to its tenant/project/signature before cosine
-- ranking, and future measurements can justify a partial HNSW index safely.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS sentient_vectors (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_key            text NOT NULL,
  project_id          uuid,
  embedding_signature text,
  source              text NOT NULL,
  content             text NOT NULL,
  metadata            jsonb NOT NULL DEFAULT '{}'::jsonb,
  embedding           vector NOT NULL,
  dimensions          integer NOT NULL CHECK (dimensions > 0),
  created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS sentient_vectors_scope_idx
  ON sentient_vectors (user_key, project_id, embedding_signature);

CREATE INDEX IF NOT EXISTS sentient_vectors_source_idx
  ON sentient_vectors (source);
