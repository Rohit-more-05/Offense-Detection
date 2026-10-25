import React, { useCallback, useEffect, useState } from 'react';
import { Scan, Loader2, RotateCcw } from 'lucide-react';
import UploadZone from '../components/UploadZone';
import ResultsCard from '../components/ResultsCard';
import { predictMeme, checkHealth } from '../api/client';

export default function Dashboard() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [healthInfo, setHealthInfo] = useState(null);
  useEffect(() => {
    let active = true;
    async function refresh() { const info = await checkHealth(); if (active) setHealthInfo(info); }
    const initial = setTimeout(refresh, 0);
    const timer = setInterval(refresh, 10000);
    return () => { active = false; clearTimeout(initial); clearInterval(timer); };
  }, []);
  const handleFileSelected = useCallback((file, url) => {
    setSelectedFile(file); setPreviewUrl(url); setResult(null); setError('');
  }, []);
  const handleClear = useCallback(() => {
    setSelectedFile(null); setPreviewUrl(null); setResult(null); setError('');
  }, []);
  async function handleSubmit() {
    if (!selectedFile || loading) return;
    setLoading(true); setError(''); setResult(null);
    try {
      const form = new FormData();
      form.append('file', selectedFile);
      setResult(await predictMeme(form));
    } catch (err) { setError(err.message || 'Analysis failed. Please retry.'); }
    finally { setLoading(false); }
  }
  return <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
    <h1 className="text-3xl font-bold text-slate-100">Meme analysis</h1>
    <p className="mb-6 mt-2 text-sm text-slate-400">Upload an image to inspect its text, model prediction and moderation status.</p>
    {healthInfo && <p className={`mb-4 text-sm ${healthInfo.alive ? 'text-emerald-300' : 'text-amber-300'}`}>
      {healthInfo.alive ? `MemeGuard online · model ${healthInfo.modelStatus}` : healthInfo.message}
    </p>}
    {healthInfo?.alive && !healthInfo.databaseReady && <p role="alert" className="mb-4 rounded-lg bg-amber-500/10 p-3 text-sm text-amber-300">Database is not ready. Check its connection and migrations before saving moderator feedback.</p>}
    <div className="space-y-5 rounded-2xl border border-slate-700 bg-slate-800/40 p-6">
      <UploadZone onFileSelected={handleFileSelected} selectedFile={selectedFile} previewUrl={previewUrl} onClear={handleClear} disabled={loading} />
      {error && <p role="alert" id="upload-error" className="rounded-lg bg-red-500/10 p-3 text-sm text-red-300">{error}</p>}
      <div className="flex gap-3">
        <button id="btn-run-detection" onClick={handleSubmit} disabled={!selectedFile || loading || !healthInfo?.alive}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-violet-600 px-5 py-3 font-semibold text-white hover:bg-violet-500 disabled:opacity-40">
          {loading ? <><Loader2 size={18} className="animate-spin" />Analysing...</> : <><Scan size={18} />Run Detection</>}
        </button>
        <button onClick={handleClear} disabled={loading} className="rounded-xl border border-slate-600 px-4 text-slate-300 disabled:opacity-40" aria-label="Reset upload"><RotateCcw size={18} /></button>
      </div>
      {loading && <p role="status" className="text-sm text-slate-400">Reading the image and checking context. External verification may take up to a minute.</p>}
    </div>
    {result && !loading && <div className="mt-6 rounded-2xl border border-slate-700 bg-slate-800/40 p-6" id="results-card">
      <ResultsCard key={result.prediction_id} result={result} originalPreview={previewUrl} />
    </div>}
  </main>;
}
