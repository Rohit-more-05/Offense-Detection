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
      throw Object.assign(new Error(errorData.detail || `HTTP ${response.status}`), {
        status: response.status,
        data: errorData,
      });
    }

    const data = await response.json();
    console.log('[API] SUCCESS', fullUrl, data);
    return data;
  } catch (error) {
    if (!error.status) {
      // Network or parse error (not an HTTP error we already caught)
      console.error('[API] FAILED', fullUrl, error.message);
    }
    throw error;
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
