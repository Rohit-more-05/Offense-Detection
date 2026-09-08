/**
 * api/client.js
 * =============
 * Centralised API client for the Meme Detection backend.
 * Phase 3: Full Triage & Probe error interception — surfaces rich diagnostic
 * objects (not plain strings) so the UI can render a deep telemetry panel.
 */

// Automatically use live Render API in production, otherwise fallback to localhost
const DEFAULT_URL = import.meta.env.PROD
  ? 'https://memeguard-backend.onrender.com/api/v1'
  : 'http://localhost:8000/api/v1';

export const BASE_URL = import.meta.env.VITE_API_BASE_URL || DEFAULT_URL;

// The health endpoint lives at the root (not under /api/v1)
const HEALTH_URL = BASE_URL.replace('/api/v1', '') + '/health';

// ── Triage helper ─────────────────────────────────────────────────────────────
/**
 * Runs a 3-step diagnostic and returns a structured DiagnosticReport object.
 * This is called whenever a fetch throws a TypeError (network drop) so the UI
 * can show EXACTLY what went wrong rather than "Failed to fetch".
 */
async function runTriage(targetRoute, rawError) {
  const timestamp = new Date().toISOString();
  const report = {
    timestamp,
    targetRoute,
    rawError: rawError?.message ?? String(rawError),
    // filled in below
    clientOnline: navigator.onLine,
    healthPingStatus: null,   // 'ok' | 'dead' | 'timeout'
    healthPingCode: null,
    inferredFaultLayer: null,
    inferredFaultReason: null,
    detailedTrace: null,
    backendPayload: null,     // set when backend returned a structured 4xx/5xx
  };

  // ── Step A: Client network status ────────────────────────────────────────────
  if (!navigator.onLine) {
    report.inferredFaultLayer  = 'CLIENT_NETWORK';
    report.inferredFaultReason = 'Your browser reports it is OFFLINE (navigator.onLine = false). Check your internet connection.';
    report.detailedTrace       = `Local network disconnect detected at ${timestamp}. No request was ever sent to the server.`;
    return report;
  }

  // ── Step B: Gateway health probe ─────────────────────────────────────────────
  try {
    const controller = new AbortController();
    const tid = setTimeout(() => controller.abort(), 5000); // 5 s timeout
    const healthRes = await fetch(HEALTH_URL, { signal: controller.signal });
    clearTimeout(tid);

    report.healthPingCode   = healthRes.status;
    report.healthPingStatus = healthRes.ok ? 'ok' : 'error';

    if (healthRes.ok) {
      // Backend container is alive — crash was in the analysis endpoint itself
      let modelStatus = 'unknown';
      try {
        const hJson = await healthRes.json();
        modelStatus = hJson.model_status ?? 'unknown';
      } catch (_) { /* ignore */ }

      report.inferredFaultLayer  = 'BACKEND_ENDPOINT';
      report.inferredFaultReason = `Backend container is ALIVE (health=OK, model_status=${modelStatus}) but the /predict endpoint crashed internally. Likely cause: Python RuntimeError during BERT inference, OCR extraction, or database write.`;
      report.detailedTrace       = `Health ping to ${HEALTH_URL} returned HTTP 200. The failure is ISOLATED to the /api/v1/predict route. Check Render logs for [TELEMETRY:LAZY_LOAD] or SQLAlchemy traceback.`;
    } else {
      // ── Step C: Server returned 4xx/5xx ─────────────────────────────────────
      report.healthPingStatus    = 'error';
      report.inferredFaultLayer  = 'RENDER_CONTAINER';
      report.inferredFaultReason = `Backend returned HTTP ${healthRes.status} on health check. Container is degraded. Possible Render OOM kill during 400MB BERT model weight loading (INT8 quantisation phase).`;
      report.detailedTrace       = `Health ping to ${HEALTH_URL} returned HTTP ${healthRes.status}. This typically indicates the Render free-tier instance (512 MB RAM) was killed by the OS while loading PyTorch model weights. Self-healing will retry on next request.`;
    }
  } catch (healthErr) {
    // ── Step C: Health ping completely unreachable ───────────────────────────
    const isTimeout = healthErr.name === 'AbortError';
    report.healthPingStatus    = isTimeout ? 'timeout' : 'dead';
    report.inferredFaultLayer  = 'RENDER_CONTAINER';
    report.inferredFaultReason = isTimeout
      ? `Backend health probe TIMED OUT after 5 seconds. Render container is cold-starting or was killed (OOM event likely during model loading phase).`
      : `Backend host is completely UNREACHABLE. DNS resolution failed or Render service is down. CORS pre-flight may also have been blocked.`;
    report.detailedTrace       = `fetch(${HEALTH_URL}) threw: ${healthErr.message}. This is a transport-layer failure — the TCP connection never completed.`;
  }

  return report;
}

// ── Generic fetch wrapper ──────────────────────────────────────────────────────
async function apiFetch(url, options = {}) {
  const fullUrl = `${BASE_URL}${url}`;
  const timestamp = new Date().toISOString();
  console.log(`[API][${timestamp}] CALL → ${fullUrl}`);

  try {
    const response = await fetch(fullUrl, options);

    if (!response.ok) {
      // Try to parse the structured backend payload we built in Phase 2/3
      const errorData = await response.json().catch(() => ({
        detail: response.statusText,
      }));
      console.error(`[API] HTTP ${response.status} from ${fullUrl}`, errorData);

      // Build a rich error object — NOT a plain string
      const err = new Error(errorData.detail || `HTTP ${response.status}`);
      err.status          = response.status;
      err.data            = errorData;
      err.isDiagnostic    = true;
      // Attach backend-structured fields directly for the UI to read
      err.diagnosticReport = {
        timestamp,
        targetRoute: url,
        rawError: `HTTP ${response.status} — ${errorData.detail || response.statusText}`,
        clientOnline: navigator.onLine,
        healthPingStatus: 'ok',       // we got a response, so server is alive
        healthPingCode: response.status,
        inferredFaultLayer: 'BACKEND_ENDPOINT',
        inferredFaultReason: errorData.detail || `Backend returned HTTP ${response.status}`,
        detailedTrace: errorData.remediation ?? null,
        backendPayload: errorData,    // {detail, phase, hardware_state, remediation, error_message}
      };
      throw err;
    }

    const data = await response.json();
    console.log(`[API] SUCCESS ${fullUrl}`, data);
    return data;

  } catch (error) {
    // Only run triage for TypeError (network drop) not for our own thrown errors
    if (!error.isDiagnostic && (error instanceof TypeError || error.message === 'Failed to fetch')) {
      console.error(`[API] NETWORK DROP on ${fullUrl} — running triage...`);
      const report = await runTriage(url, error);
      error.isDiagnostic    = true;
      error.diagnosticReport = report;
    }

    if (!error.status && !error.isDiagnostic) {
      console.error(`[API] FAILED ${fullUrl}`, error.message);
    }
    throw error;
  }
}

// ── Diagnostic / Health ────────────────────────────────────────────────────────
export async function checkHealth() {
  try {
    const res = await fetch(HEALTH_URL, { signal: AbortSignal.timeout?.(5000) });
    if (res.ok) {
      const json = await res.json().catch(() => ({}));
      return { alive: true, modelStatus: json.model_status ?? 'unknown', code: res.status };
    }
    return { alive: false, modelStatus: 'error', code: res.status };
  } catch (err) {
    return { alive: false, modelStatus: 'unreachable', code: null };
  }
}

// ── Public API functions ───────────────────────────────────────────────────────

/**
 * Submit a meme image for harm classification.
 * @param {FormData} formData - Must contain `file` and optionally `manual_text_override`.
 */
export async function predictMeme(formData) {
  console.log('[API] predictMeme — preparing upload');
  return apiFetch('/predict', {
    method: 'POST',
    body: formData,
    // Note: do NOT set Content-Type header; fetch sets it automatically for FormData
  });
}

/**
 * Fetch the human-review queue (pending moderation items).
 */
export async function getReviewQueue() {
  console.log('[API] getReviewQueue');
  return apiFetch('/review-queue', { method: 'GET' });
}

/**
 * Submit a human verdict for a pending review item.
 * @param {string} itemId - prediction_id UUID
 * @param {'Harmful'|'Non-Harmful'} humanVerdict
 * @param {string|null} notes
 */
export async function submitVerdict(itemId, humanVerdict, notes = null) {
  console.log('[API] submitVerdict — itemId=%s verdict=%s', itemId, humanVerdict);
  return apiFetch(`/review/${itemId}/verdict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ human_verdict: humanVerdict, notes }),
  });
}
