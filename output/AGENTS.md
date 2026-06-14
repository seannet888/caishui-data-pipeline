# AGENTS.md

Local rules for pipeline output, writer, and embedding lifecycle Modules.

## Owning Modules

- `schemas.py` owns Pydantic output contract types.
- `writer.py` is a thin Pipeline Writer Adapter plus seed verification marker.
- `embedding_lifecycle.py` owns production embedding rules.
- `preview_adapter.py` owns preview response shaping.

## Embedding Lifecycle

- Only chunks with `verification_status == 'verified'` get production embeddings.
- `unverified`, `rejected`, and withdrawn chunks must keep production `embedding = NULL` unless already retained for audit by explicit lifecycle rules.
- Idempotency key is SHA-256 of `document_id + content_hash + model + dimension`.
- Max automatic embedding retries: 3.
- Embedding failure must not change `verification_status`.
- Do not reintroduce embedding lifecycle branching into `writer.py`.

## Verification Methods

- MVP allows `seed` and `human`.
- `auto` is a reserved future value only; MVP code must not produce it.
- `manual_override` is forbidden. If a failed automatic check is human-confirmed, use `human` and explain the basis in notes.

## Rejected Chunks

- Rejected chunks may be stored for diagnostics.
- They do not get embeddings and do not participate in retrieval.
- Keep rejection reasons in notes.
- If parser/chunker fixes produce usable content later, create new chunk rows/versions rather than silently mutating rejected records to verified.
