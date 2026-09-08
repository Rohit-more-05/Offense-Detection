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

  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isBackendAlive, setIsBackendAlive] = useState(true);

  // Proactive Health and Gateway Pre-Flight Check (Phase 3 Requirement)
  useEffect(() => {
    let mounted = true;
    const verifyHealth = async () => {
      const alive = await checkHealth();
      if (mounted) setIsBackendAlive(alive);
      
      // Attempt self-healing reconnection polling if dead
      if (!alive && mounted) {
        setTimeout(verifyHealth, 5000);
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
      setError(err.message || 'Detection failed. Is the backend running?');
    } finally {
      setLoading(false);
    }
  }, [selectedFile]);

  return (
    <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
      {/* Page header */}
      <div className="mb-8 text-center">
        <h1 className="bg-gradient-to-r from-violet-300 via-indigo-300 to-cyan-300 bg-clip-text text-3xl font-extrabold tracking-tight text-transparent sm:text-4xl">
          Meme Harm Detection
        </h1>
        <p className="mt-2 text-slate-400 text-sm">
          Upload a meme to classify it with mock inference — Phase 1 demo.
        </p>
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

        {/* Error */}
        {error && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300" id="upload-error">
            ⚠ {error}
          </div>
        )}

        {/* System Degradation Notice */}
        {!isBackendAlive && !error && (
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-300" id="health-warning">
            ⚠️ System Degradation Notice: Connection to Render Inference Cluster timed out. Attempting automatic self-healing reconnection...
          </div>
        )}

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
