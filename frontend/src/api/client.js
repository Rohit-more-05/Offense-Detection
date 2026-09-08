/**
 * api/client.js
 * =============
 * Centralised API client for the Meme Detection backend.
 * All calls log to the browser console (START, SUCCESS, FAILED)
 * to satisfy the Phase 1.5 observability directive.
 */

// Automatically use live Render API in production, otherwise fallback to localhost
const DEFAULT_URL = import.meta.env.PROD 
  ? 'https://memeguard-backend.onrender.com/api/v1' 
  : 'http://localhost:8000/api/v1';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || DEFAULT_URL;

// ── Generic fetch wrapper ──────────────────────────────────────────────────────
async function apiFetch(url, options = {}) {
  const fullUrl = `${BASE_URL}${url}`;
  console.log('[API] Calling', fullUrl, options.body ?? '');

  try {
    const response = await fetch(fullUrl, options);

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      console.error('[API] FAILED', fullUrl, errorData);
      
      // Parse detailed Backend Gateway Exceptions (Phase 3 Requirement)
      let errorMessage = errorData.detail || `HTTP ${response.status}`;
      if (errorData.phase && errorData.hardware_state) {
          errorMessage = `Backend Gateway Fault: [${errorData.detail}] | Phase: ${errorData.phase} | CPU: ${errorData.hardware_state.cpu_threads} | Mem: ${errorData.hardware_state.memory_pressure} | Action: ${errorData.remediation}`;
      }

      throw Object.assign(new Error(errorMessage), {
        status: response.status,
        data: errorData,
      });
    }

    const data = await response.json();
    console.log('[API] SUCCESS', fullUrl, data);
    return data;
  } catch (error) {
    // Dynamic Type Fingerprinting for generic network drops (Phase 3 Requirement)
    if (error.message === 'Failed to fetch' || error.message.includes('NetworkError')) {
      console.error('[API] FATAL: Network request dropped. Running diagnostic...');
      let healthStatus = 'Backend Unreachable / Possible Render OOM Kill';
      let statusCode = '503 Service Unavailable';
      
      if (!navigator.onLine) {
        healthStatus = 'Client Offline';
        statusCode = 'N/A';
      } else {
        try {
          // Lightning-fast background ping to /health
          const healthRes = await fetch(`${BASE_URL}/health`);
          if (healthRes.ok) {
            healthStatus = 'Backend Alive — Endpoint specific runtime crash or CORS block';
            statusCode = 'Endpoint Failed';
          }
        } catch (healthErr) {
          // Retain default unreachable status
        }
      }
      
      error.message = `Network Fault: [${healthStatus}] | Status: ${statusCode} | Context: Model lazy-load execution phase.`;
    }

    if (!error.status) {
      console.error('[API] FAILED', fullUrl, error.message);
    }
    throw error;
  }
}

// ── Diagnostic / Health ────────────────────────────────────────────────────────
export async function checkHealth() {
  try {
    const res = await fetch(`${BASE_URL}/health`);
    return res.ok;
  } catch (err) {
    return false;
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
