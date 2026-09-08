import React, { useCallback, useEffect, useState } from 'react';
import { Scan, Loader2, RotateCcw } from 'lucide-react';
import UploadZone from '../components/UploadZone';
import ResultsCard from '../components/ResultsCard';
import { predictMeme, checkHealth } from '../api/client';
import { MIN_LOADING_MS } from '../utils/constants';

/**
 * Dashboard page ("/")
 * Main meme upload + prediction result view.
 */
export default function Dashboard() {
  useEffect(() => {
    console.log('[Dashboard] mounted');
  }, []);

  const [selectedFile, setSelectedFile]   = useState(null);
  const [previewUrl, setPreviewUrl]       = useState(null);
  const [result, setResult]               = useState(null);
  const [loading, setLoading]             = useState(false);
  // error can be: null | string | DiagnosticReport object
  const [error, setError]                 = useState(null);
  const [healthInfo, setHealthInfo]       = useState(null); // { alive, modelStatus, code }

  // ── Proactive pre-flight health check ──────────────────────────────────────
  useEffect(() => {
    let mounted = true;
    const verifyHealth = async () => {
      const info = await checkHealth();
      if (!mounted) return;
      setHealthInfo(info);
      if (!info.alive) {
        // Retry every 8 seconds if backend is down
        setTimeout(verifyHealth, 8000);
      }
    };
    verifyHealth();
    return () => { mounted = false; };
  }, []);

  const handleFileSelected = useCallback((file, url) => {
    console.log('[Dashboard] state: file selected —', file.name);
    setSelectedFile(file);
    setPreviewUrl(url);
    setResult(null);
    setError(null);
  }, []);

  const handleClear = useCallback(() => {
    console.log('[Dashboard] state: cleared');
    setSelectedFile(null);
    setPreviewUrl(null);
    setResult(null);
    setError(null);
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!selectedFile) return;
    console.log('[Dashboard] state: upload started —', selectedFile.name);
    setLoading(true);
    setError(null);
    setResult(null);

    const t0 = Date.now();
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const data = await predictMeme(formData);

      // Enforce minimum loading time for UX realism
      const elapsed = Date.now() - t0;
      if (elapsed < MIN_LOADING_MS) {
        await new Promise((r) => setTimeout(r, MIN_LOADING_MS - elapsed));
      }

      console.log('[Dashboard] state: upload complete — prediction_id=%s', data.prediction_id);
      setResult(data);
    } catch (err) {
      console.error('[Dashboard] ERROR:', err);
      // If the API layer produced a diagnosticReport, pass the whole object
      if (err.diagnosticReport) {
        setError(err.diagnosticReport);
      } else {
        // Fallback: plain string so nothing is ever silent
        setError(err.message || 'Detection failed. Is the backend running?');
      }
    } finally {
      setLoading(false);
    }
  }, [selectedFile]);

  // ── Renders the rich terminal-style diagnostic panel ───────────────────────
  const renderErrorPanel = () => {
    if (!error) return null;

    // Plain string fallback
    if (typeof error === 'string') {
      return (
        <div
          className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300"
          id="upload-error"
        >
          ⚠ {error}
        </div>
      );
    }

    // Rich structured DiagnosticReport
    const r = error;
    const bp = r.backendPayload;

    // Colour-code the fault layer
    const layerColour = {
      CLIENT_NETWORK:   'text-yellow-400',
      RENDER_CONTAINER: 'text-red-400',
      BACKEND_ENDPOINT: 'text-orange-400',
    }[r.inferredFaultLayer] ?? 'text-red-400';

    const pingBadge = () => {
      if (r.healthPingStatus === 'ok')      return <span className="text-green-400">✅ ALIVE (HTTP {r.healthPingCode})</span>;
      if (r.healthPingStatus === 'timeout') return <span className="text-amber-400">⏱ TIMEOUT (5 s)</span>;
      if (r.healthPingStatus === 'dead')    return <span className="text-red-400">❌ DEAD</span>;
      if (r.healthPingStatus === 'error')   return <span className="text-orange-400">⚠ HTTP {r.healthPingCode}</span>;
      return <span className="text-slate-400">— skipped (client offline)</span>;
    };

    return (
      <div
        className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300"
        id="upload-error"
      >
        {/* Header */}
        <div className="font-bold border-b border-red-500/20 pb-2 mb-3 text-red-400 flex items-center gap-2">
          <span>⚠️ CRITICAL ANALYSIS FAILURE DIAGNOSTICS</span>
          <span className={`ml-auto text-xs font-mono px-2 py-0.5 rounded bg-red-900/40 ${layerColour}`}>
            {r.inferredFaultLayer ?? 'UNKNOWN'}
          </span>
        </div>

        <ul className="space-y-1.5 font-mono text-xs">
          <li>
            <span className="text-slate-400">[TIMESTAMP]          </span>
            <span className="text-white">{r.timestamp}</span>
          </li>
          <li>
            <span className="text-slate-400">[TARGET ROUTE]       </span>
            <span className="text-violet-300">/api/v1{r.targetRoute}</span>
          </li>
          <li>
            <span className="text-slate-400">[CLIENT ONLINE]      </span>
            <span className={r.clientOnline ? 'text-green-400' : 'text-red-400'}>
              {r.clientOnline ? '✅ YES' : '❌ NO — browser is offline'}
            </span>
          </li>
          <li>
            <span className="text-slate-400">[HEALTH PING]        </span>
            {pingBadge()}
          </li>
          <li>
            <span className="text-slate-400">[FAULT LAYER]        </span>
            <span className={layerColour}>{r.inferredFaultLayer ?? '—'}</span>
          </li>
          <li>
            <span className="text-slate-400">[SYSTEM FAULT]       </span>
            <span className="text-red-300 break-all">{r.inferredFaultReason}</span>
          </li>
          <li>
            <span className="text-slate-400">[DIAGNOSTIC TRACE]   </span>
            <span className="text-amber-300 break-all">{r.detailedTrace}</span>
          </li>
          <li>
            <span className="text-slate-400">[RAW ERROR]          </span>
            <span className="text-slate-300 break-all">{r.rawError}</span>
          </li>

          {/* Backend structured payload (Phase 2/3 gateway exceptions) */}
          {bp && bp.phase && (
            <>
              <li className="mt-2 pt-2 border-t border-red-500/20">
                <span className="text-slate-400">[BACKEND PHASE]      </span>
                <span className="text-orange-300">{bp.phase}</span>
              </li>
              {bp.hardware_state && (
                <li>
                  <span className="text-slate-400">[HARDWARE STATE]     </span>
                  <span className="text-amber-300">
                    CPU threads: {bp.hardware_state.cpu_threads} | Memory pressure: {bp.hardware_state.memory_pressure}
                  </span>
                </li>
              )}
              {bp.remediation && (
                <li>
                  <span className="text-slate-400">[REMEDIATION]        </span>
                  <span className="text-green-300">{bp.remediation}</span>
                </li>
              )}
              {bp.error_message && (
                <li>
                  <span className="text-slate-400">[INTERNAL MSG]       </span>
                  <span className="text-slate-300 break-all">{bp.error_message}</span>
                </li>
              )}
            </>
          )}

          <li className="pt-2 border-t border-red-500/20">
            <span className="text-slate-400">[POSSIBLE CAUSE]     </span>
            <span className="text-slate-300">
              Model loading phase exceeded Render's 512 MB RAM ceiling, API session was dropped by the DB connection pool, or CORS pre-flight was blocked.
            </span>
          </li>
        </ul>
      </div>
    );
  };

  const isBackendAlive = healthInfo ? healthInfo.alive : true; // optimistic until first check

  return (
    <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
      {/* Page header */}
      <div className="mb-8 text-center">
        <h1 className="bg-gradient-to-r from-violet-300 via-indigo-300 to-cyan-300 bg-clip-text text-3xl font-extrabold tracking-tight text-transparent sm:text-4xl">
          Meme Harm Detection
        </h1>
        <p className="mt-2 text-slate-400 text-sm">
          Upload a meme to classify it with AI inference.
        </p>

        {/* Inline health status badge */}
        {healthInfo && (
          <div className="mt-2 inline-flex items-center gap-1.5 text-xs font-mono px-2 py-1 rounded-full border border-slate-700 bg-slate-800/60">
            <span className={`w-2 h-2 rounded-full ${healthInfo.alive ? 'bg-green-400 animate-pulse' : 'bg-red-500'}`} />
            <span className={healthInfo.alive ? 'text-green-400' : 'text-red-400'}>
              Backend {healthInfo.alive ? 'Online' : 'Offline'}
            </span>
            {healthInfo.alive && healthInfo.modelStatus !== 'unknown' && (
              <span className="text-slate-400">— model: {healthInfo.modelStatus}</span>
            )}
          </div>
        )}
      </div>

      {/* Upload card */}
      <div className="rounded-2xl border border-slate-700/50 bg-slate-800/40 p-6 shadow-xl shadow-black/20 backdrop-blur-sm space-y-5">
        <UploadZone
          onFileSelected={handleFileSelected}
          selectedFile={selectedFile}
          previewUrl={previewUrl}
          onClear={handleClear}
          disabled={loading}
        />

        {/* System Degradation Notice */}
        {healthInfo && !healthInfo.alive && !error && (
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-300 font-mono" id="health-warning">
            <div className="font-bold text-amber-400 mb-1">⚠️ SYSTEM DEGRADATION NOTICE</div>
            <div>Connection to Render Inference Cluster timed out (HTTP {healthInfo.code ?? 'N/A'}).</div>
            <div className="text-xs text-amber-400/70 mt-1">Attempting automatic self-healing reconnection every 8 seconds...</div>
          </div>
        )}

        {/* Rich diagnostic error panel */}
        {renderErrorPanel()}

        {/* Action buttons */}
        <div className="flex gap-3">
          <button
            id="btn-run-detection"
            onClick={handleSubmit}
            disabled={!selectedFile || loading || !isBackendAlive}
            className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-violet-500/20 hover:from-violet-500 hover:to-indigo-500 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none"
          >
            {loading ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Analysing…
              </>
            ) : (
              <>
                <Scan size={16} />
                Run Detection
              </>
            )}
          </button>

          {(result || error) && (
            <button
              id="btn-reset"
              onClick={handleClear}
              className="flex items-center gap-2 rounded-xl border border-slate-600/50 bg-slate-700/50 px-4 py-3 text-sm font-medium text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
            >
              <RotateCcw size={14} />
              Reset
            </button>
          )}
        </div>
      </div>

      {/* Loading skeleton */}
      {loading && (
        <div className="mt-6 rounded-2xl border border-slate-700/50 bg-slate-800/40 p-6 space-y-4 animate-pulse">
          <div className="h-5 w-1/3 rounded-lg bg-slate-700/60" />
          <div className="h-3 w-full rounded-lg bg-slate-700/60" />
          <div className="h-16 w-full rounded-xl bg-slate-700/40" />
          <div className="grid grid-cols-2 gap-3">
            <div className="h-40 rounded-xl bg-slate-700/40" />
            <div className="h-40 rounded-xl bg-slate-700/40" />
          </div>
        </div>
      )}

      {/* Results */}
      {!loading && result && (
        <div className="mt-6 rounded-2xl border border-slate-700/50 bg-slate-800/40 p-6 shadow-xl shadow-black/20 backdrop-blur-sm" id="results-card">
          <ResultsCard result={result} originalPreview={previewUrl} />
        </div>
      )}
    </main>
  );
}
