# Phase 1 Addendum — Full-Stack Observability & Autonomous Debugging Directive

Append this to `implementation_plan.md` under a new section titled "Phase 1.5 — Observability Layer" before proceeding to Phase 2.

---

## Objective

Before any further feature work, instrument **every function, every API route, every service call, and every frontend component** with structured logging so that success/failure status is visible in three places simultaneously:
1. The backend terminal (uvicorn console)
2. The browser console log (frontend)
3. Swagger UI (`/docs`) via response metadata / logged request-response cycles

The goal is to make every choke point identifiable without needing a debugger attached.

---

## Backend Logging Requirements (FastAPI)

1. Create `backend/app/logger.py` with a shared Python `logging` instance:
   - Use `logging.basicConfig` or a `dictConfig` with a formatter that includes timestamp, module name, function name, and line number.
   - Log level controlled by `.env` (`LOG_LEVEL=DEBUG` for dev).
   - Output to both stdout (terminal) and a rotating file handler (`backend/logs/app.log`).

2. Every function in `services/`, `routers/`, `database.py`, and `models/` must:
   - Log an `INFO` entry on entry: `logger.info(f"[{function_name}] START — args: {...}")`
   - Log an `INFO` entry on successful exit: `logger.info(f"[{function_name}] SUCCESS — result: {...}")`
   - Wrap risky logic in `try/except` and log `ERROR` with full traceback on failure: `logger.error(f"[{function_name}] FAILED — reason: {str(e)}", exc_info=True)`
   - Never use bare `except:` — always catch specific exceptions and re-raise as FastAPI `HTTPException` with a descriptive `detail` message so the error surfaces in Swagger UI's response body, not just the terminal.

3. Add a global middleware in `main.py` that logs every incoming request (method, path, client IP) and every outgoing response (status code, latency in ms):
   ```python
   @app.middleware("http")
   async def log_requests(request, call_next):
       # log request start, call_next, log response status + duration, return response
   ```

4. Add a global exception handler in `main.py`:
   ```python
   @app.exception_handler(Exception)
   async def global_exception_handler(request, exc):
       # log full traceback, return JSON {"error": str(exc), "path": request.url.path}
   ```

5. Database layer (`database.py`):
   - Log on engine creation: confirm Supabase connection string host (mask password) and log `"Supabase connection pool initialized"`.
   - On startup (`main.py` `@app.on_event("startup")` or lifespan), run a lightweight `SELECT 1` against Supabase and log `"Supabase connection successful"` or `"Supabase connection FAILED: {reason}"`.
   - Log a check confirming the `predictions` table exists (`information_schema.tables` query) and log the result explicitly.

6. Every router endpoint (`predict.py`, `review.py`) must log:
   - Request received with key params (filename, item_id, etc.)
   - Each internal step (file saved, inference called, DB write attempted, DB write confirmed)
   - Final response payload before returning

7. Swagger UI visibility: ensure every endpoint has explicit `response_model` and documented error responses (`responses={500: {...}, 404: {...}}`) so failure modes are visible directly in `/docs`, not just inferred from logs.

---

## Frontend Logging Requirements (React)

1. In `src/api/client.js`, wrap every API call (axios/fetch) with:
   - `console.log("[API] Calling", url, payload)` before the request
   - `console.log("[API] SUCCESS", url, response.data)` on success
   - `console.error("[API] FAILED", url, error.response?.data || error.message)` on failure

2. Every component (`UploadZone.jsx`, `ResultsCard.jsx`, `ReviewQueueTable.jsx`, etc.) must log:
   - On mount: `console.log("[ComponentName] mounted")`
   - On key state transitions (upload started, upload complete, error state): `console.log("[ComponentName] state: ...")`
   - On any caught error: `console.error("[ComponentName] ERROR:", err)`

3. Add a top-level React Error Boundary component that logs the full error + component stack to console and displays a visible fallback UI instead of a blank white screen.

---

## Autonomous Debugging Loop

Once logging is added, run the full verification checklist from the existing Phase 1 plan end-to-end. Do not stop iterating until **all** of the following exact conditions are confirmed and printed/logged:

```
Supabase connection successful
predictions table exists as required
build is successful
logic is robust
```

If any step fails, use the logged error reason (terminal + browser console + Swagger response body) to pinpoint the exact failing function, fix it, re-run the full verification checklist from step 1, and repeat until all four conditions above are met with no unhandled exceptions anywhere in the stack.

---

## Security Note (must fix before this proceeds)

The current plan's `.env` block contains a live Supabase password in plaintext inside `implementation_plan.md`. Before any commit or push:
- Move the real credentials into `.env` only (already gitignored), never in a markdown file.
- Rotate the Supabase password since it has already been exposed in this plan document.
- Confirm `.env` is listed in `.gitignore` before the first commit.
