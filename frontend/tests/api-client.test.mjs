import test from 'node:test';
import assert from 'node:assert/strict';
import { BASE_URL, checkHealth, imageUrl, submitVerdict } from '../src/api/client.js';

test('local backend uses the non-conflicting port', () => {
  assert.equal(BASE_URL, 'http://localhost:8001/api/v1');
  assert.equal(imageUrl('/api/v1/images/abc'), 'http://localhost:8001/api/v1/images/abc');
});

test('a healthy different project is rejected', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ status: 'ok', database: 'ok' }) });
    const health = await checkHealth();
    assert.equal(health.alive, false);
    assert.equal(health.modelStatus, 'wrong-service');
  } finally { globalThis.fetch = original; }
});

test('failed moderator save reaches the caller', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => ({ ok: false, status: 503, json: async () => ({ detail: 'Verdict was not saved.' }) });
    await assert.rejects(submitVerdict('id', 'Non-Harmful'), /not saved/);
  } finally { globalThis.fetch = original; }
});
