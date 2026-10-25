const env = import.meta.env || {};
const DEFAULT_URL = env.PROD ? 'https://memeguard-backend.onrender.com/api/v1' : 'http://localhost:8001/api/v1';
export const BASE_URL = (env.VITE_API_BASE_URL || DEFAULT_URL).replace(/\/$/, '');
const ROOT_URL = BASE_URL.replace(/\/api\/v1$/, '');
export const imageUrl = (path) => path ? new URL(path, `${ROOT_URL}/`).href : null;

async function apiFetch(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, { ...options, signal: options.signal || AbortSignal.timeout(150_000) });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (HTTP ${response.status}).`);
  return data;
}

export async function checkHealth() {
  try {
    const response = await fetch(`${ROOT_URL}/health`, { signal: AbortSignal.timeout(5000) });
    const data = await response.json();
    if (data.service !== 'memeguard') return { alive: false, modelStatus: 'wrong-service', code: response.status,
      message: 'This address belongs to a different application. Start MemeGuard on port 8001 and check VITE_API_BASE_URL.' };
    return { alive: response.ok, modelStatus: data.model_status, code: response.status, databaseReady: data.database_ready };
  } catch {
    return { alive: false, modelStatus: 'unreachable', code: null, message: 'MemeGuard is unreachable. Start its backend and check the API address.' };
  }
}

export const predictMeme = (formData) => apiFetch('/predict', { method: 'POST', body: formData });
export const getReviewQueue = (scope = 'all') => apiFetch(`/review-queue?scope=${scope}`);
export const submitVerdict = (id, human_verdict, notes = null) => apiFetch(`/review/${id}/verdict`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ human_verdict, notes }),
});
