# Retrieval eval set

`retrieval.json` is 20 question-and-expected-chunk pairs over `data/skyrimskills.pdf`, which is
checked into this repository so the harness needs no setup. Run it with
`uv run python scripts/eval_retrieval.py --rebuild`.

## Why it exists

Every retrieval knob in `project_configs` is adjustable and, until this file, unjudgeable. There
was no way to tell whether a config change made grounding better or worse, which makes an eval set
the prerequisite for any quality claim rather than a nice-to-have.

**V1 measured the concrete case this is aimed at.** On the real index the bare proper noun
`Thornwald` scored **0.2570** while a topically unrelated nonsense query scored **0.3185** — a
single rare token ranking *below* plausible prose under dense-only retrieval. That is a live
argument for turning on hybrid BM25 (`RAG_HYBRID`), and it was unprovable either way. Cases
`pn-*` and `neg-*` exist to settle it.

## The shape of a case

```json
{
  "id": "pn-runil",
  "kind": "proper_noun",
  "query": "Who is Runil?",
  "expect_any": ["Runil", "Journeyman Trainer"]
}
```

`expect_any` rather than one exact chunk, and it is not laziness. Chunk boundaries move with
`RAG_CHUNK_SIZE`, which is one of the knobs being evaluated, so pinning a chunk id would make the
eval measure the chunker instead of the retrieval. A hit is "any expected string appears in any
returned chunk".

`kind` is what stops the numbers being averaged into meaninglessness:

| kind | What it tests |
| --- | --- |
| `prose` | Ordinary questions in the document's own register. The easy case, and the baseline. |
| `proper_noun` | A single rare token with no supporting context. The case dense retrieval is worst at. |
| `nonsense` | Must score **lower than every real query**. A configuration where it does not is broken regardless of its recall. |

## One thing the extracted text does to your expectations

`skyrimskills.pdf` is a scan-derived PDF and `pypdf` returns it with a systematic `a` → `o`
substitution: **`Falkreath` extracts as `Folkreoth`**, `Khajiit` as `Khojiit`, `Battle Cry` as
`Bottle Cry`. The index contains the mangled forms, so `expect_any` uses them. An eval written
against the correct spelling would report 0% recall against a working index — which is exactly the
class of false negative an eval set is supposed to catch rather than produce.

The queries stay spelled correctly, because that is what a user types.

`data/characters.pdf` is deliberately **not** in the eval set: it is the scanned 6-page PDF that
extracts to zero characters without OCR, and including it would make the score depend on whether
Tesseract is installed.
