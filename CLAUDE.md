# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

ChếMeme: a Vietnamese meme generator. A LangGraph agent (Gemini) picks templates, writes captions, renders text with Pillow, self-critiques the rendered images and returns the top 3. FastAPI backend + Next.js frontend, deployed separately (Cloud Run + Vercel; Neon Postgres; Cloudflare R2). The user writes in Vietnamese; UI copy, prompts and most code comments are Vietnamese.

## Commands

Backend (run from `backend/`, venv already at `backend/.venv`):

```bash
.venv/bin/uvicorn app.main:app --reload --port 8000 --env-file .env   # --env-file needed for LANGSMITH_* (see Gotchas)
.venv/bin/python -m pytest -q                                          # all tests (always FakeLLM, no quota used)
.venv/bin/python -m pytest tests/test_users.py::test_one_vote_per_user_per_pair -q   # single test
.venv/bin/ruff check . && .venv/bin/ruff format --check .              # CI runs both
.venv/bin/python -m scripts.make_templates     # redraw the 6 starter templates + JSON
.venv/bin/python -m scripts.index_templates    # embed templates (needs GOOGLE_API_KEY)
.venv/bin/python -m scripts.seed_arena --limit 10   # create agent-vs-baseline pairs for /arena (uses Gemini quota)
.venv/bin/python -m evals.run_eval templates|safety|quality [--limit N]
```

Frontend (from `frontend/`): `npm run dev`, `npm run typecheck`, `npm run build`. No ESLint. CI (`.github/workflows/ci.yml`) = backend ruff + pytest on Python 3.12, frontend typecheck + build on Node 22.

Without `GOOGLE_API_KEY` (or with `LLM_FAKE=1`) the backend silently uses `FakeLLM`; `GET /api/health` reports `fake_llm`.

## Architecture

**Agent graph** (`backend/agent/graph.py`, nodes in `agent/nodes.py`): `understand` → (`refuse` | `describe_image` for uploads | `pick_templates`) → `write_captions` → `render` → `critique` → `select` → loop back to `write_captions` (max `max_rounds`=2) or END. Principle: Gemini only understands, writes and judges; rendering (`render/renderer.py`) and the keep/drop decision (`select`) are plain code. Candidates accumulate across rounds in state; `select` relaxes thresholds on the last round and prefers one winner per template.

**LLM layer** (`agent/llm.py`): `LLM.structured(schema, system, user, images, temperature)` returns Pydantic models from `agent/state.py`. `GeminiLLM` uses `reasoning_effort` (default `low`; default effort measured ~20–26 s/call vs ~8 s on low) and falls back to `GEMINI_FALLBACK_MODEL` on 503/429. **`FakeLLM` parses the prompt text** (`Tình huống: …`, `TEMPLATE id=<id> boxes=<a,b>`, `K=`, `N_IMAGES=`, `#i overflow=true`), so changing prompt formatting in `nodes.py`/`baseline.py` can break FakeLLM and the whole test suite.

**Streaming**: nodes emit events via `langgraph.config.get_stream_writer()`; `app/service.py::stream_job` runs `graph.astream(stream_mode=["custom","values"])`, forwards custom events as SSE and persists winners at the end. Event types (`node_start`, `node_end`, `candidate`, `scored`, `result`, `refused`, `error`, `done`) are consumed by `frontend/components/JobView.tsx`. `critique` judges batches in a thread pool but emits events from the main thread because the stream writer is bound to the graph's context.

**Templates & RAG**: each template is `data/templates/<id>.json` (boxes in 0–1 ratios, `style` impact|caption|label, `max_chars`, `hint`, `when_to_use`, `examples`) plus an image in `data/templates/images/`. `rag/search.py` does hybrid search (in-memory cosine over vectors cached in `data/template_index.json`, invalidated by text hash, + BM25 on diacritic-folded text) fused with RRF. pgvector was deliberately not used.

**Renderer**: NFC-normalizes text, keeps explicit `\n`, binary-searches the largest font that fits each box, flags `overflow` instead of failing. Fonts (Anton, Be Vietnam Pro, OFL) are bundled in `render/fonts/`. Every saved meme is stored twice: `memes/<id>.webp` and a `.jpg` copy for `og:image` (`service.save_meme_image` / `delete_meme_files`).

**Storage** (`app/storage.py`): `LocalStorage` (served at `/files/...`) or `R2Storage`. Key prefixes: `uploads/` (EXIF-stripped user photos), `drafts/<job>/` (candidates), `memes/` (public results).

**Database** (`app/db.py`): SQLAlchemy 2.0; SQLite file `backend/chememe.db` when `DATABASE_URL` is unset, Postgres (Neon) otherwise (`postgresql://` is rewritten to psycopg 3). **No migrations**: `init_db` runs `create_all` then `check_schema`, which raises `SchemaOutdated` if an existing table lacks a model column. The user deliberately removed Alembic; do not reintroduce it without asking. Adding a column means a manual `ALTER TABLE` or recreating tables.

**Auth & users**: frontend gets a Google ID token via Google Identity Services (`components/GoogleSignIn.tsx`) → `POST /api/auth/google` (`app/auth.py` verifies with `GOOGLE_CLIENT_ID`) → backend issues its own session token (only the SHA-256 is stored in `sessions`). The token lives in `localStorage` and is sent as `Authorization: Bearer` (no cookies: frontend and backend are on different domains). FastAPI deps `optional_user` / `require_user`. Rules: memes with an owner can only be edited/deleted by that owner; guest memes stay editable by anyone with the job link; `owner` is only exposed when `profile_public`. Job quota is counted from the `jobs` table over 24 h (`app/quota.py`: 20 signed-in, 5 guest by IP hash); other limits use in-memory `slowapi`. User routes are in `app/users_api.py`, everything else in `app/api.py`; errors are `app.errors.ApiError` → `{"code","message"}`.

**Arena**: pairs come only from seeded arena jobs (`Job.arena=True`, one `agent` + one `baseline` per topic from `evals/topics.jsonl`), never from user memes. Pair tokens are HMAC-signed (`app/security.py`); votes have a unique `(user_id, pair_key)` index.

**Frontend**: Next.js 16 App Router (page `params`/`searchParams` are Promises), Tailwind v4 with theme tokens in `app/globals.css` (Claude-like palette: ivory, clay, serif headings). All API calls go through `lib/api.ts` (adds the bearer token, clears it on 401). `/m/[id]` and `/u/[username]` are server-rendered for Open Graph previews.

## Gotchas

- `get_settings()` is `lru_cache`d and reads `.env` into the Settings object only, not `os.environ`. Libraries reading env directly (LangSmith) need `--env-file`. Tests set env vars in `tests/conftest.py` before importing the app, and tweak limits by mutating `get_settings()` attributes.
- `JobView` must not abort its fetch in the effect cleanup: under React StrictMode (dev) that cancelled the run request before it was sent (jobs stuck in `created`).
- `backend/storage/`, `backend/chememe.db` and `backend/.env` hold the user's real data and secrets. Never delete or overwrite them; use a scratch dir via `LOCAL_STORAGE_DIR` / `DATABASE_URL` for experiments. Opening a missing SQLite path (even read-only checks via SQLAlchemy/sqlite3) creates an empty file.
- When stopping dev servers, don't run `pkill -f <pattern>` in the same shell command that contains that pattern (e.g. the uvicorn start line); it matches and kills the shell itself. Kill by PID.
