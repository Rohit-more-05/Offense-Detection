import React, { useState } from 'react';
import { submitVerdict } from '../api/client';
import { LABEL_CONFIG } from '../utils/constants';
import ConfidenceMeter from './ConfidenceMeter';
import ModerationBanner from './ModerationBanner';

export default function ResultsCard({ result, originalPreview }) {
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const labelCfg = LABEL_CONFIG[result.label] || LABEL_CONFIG['Needs review'];
  async function correct(verdict) {
    setPending(true); setError(''); setMessage('');
    try {
      await submitVerdict(result.prediction_id, verdict);
      setMessage(`Saved human verdict: ${verdict}. Available for dataset export; the model has not been retrained.`);
    } catch (err) { setError(err.message); }
    finally { setPending(false); }
  }
  return <div className="space-y-4">
    <div className="flex items-center justify-between gap-3">
      <span id="result-label-pill" className={`rounded-full px-3 py-1 text-sm font-bold ${labelCfg.pillClass}`}>{result.label}</span>
      <span className="text-xs text-slate-400">{result.execution_time_ms} ms</span>
    </div>
    <p className="text-sm text-slate-200" id="result-reason">{result.reason}</p>
    <p className="text-xs text-slate-400">Decision source: {result.decision_source === 'context_verifier' ? 'Contextual verification' : result.decision_source === 'baseline' ? 'Local multimodal model' : result.decision_source === 'input_scope' ? 'Input type check' : 'Manual review needed'}</p>
    <ModerationBanner decision={result.moderation_decision} persisted={result.persisted} />
    {!result.persisted && <p role="alert" className="rounded-lg bg-red-500/15 p-3 text-sm text-red-200">Not saved to the database. This upload cannot receive feedback until the connection is restored and you upload it again.</p>}
    {originalPreview && <img src={originalPreview} alt="Uploaded image" className="max-h-72 w-full rounded-lg object-contain" />}
    {result.harmful_probability != null && <details className="rounded-lg border border-slate-700 p-3">
      <summary className="cursor-pointer text-sm text-slate-300">Local model output: {result.baseline_label}</summary>
      <div className="mt-3"><ConfidenceMeter confidence={result.harmful_probability} /></div>
      <p className="mt-2 text-xs text-slate-400">Raw local-model score, not confidence in the final decision. It may disagree with the contextual verifier.</p>
    </details>}
    <details className="rounded-lg border border-slate-700 p-3">
      <summary className="cursor-pointer text-sm text-slate-300">Text used for analysis ({result.ocr_status})</summary>
      <p className="mt-2 whitespace-pre-wrap break-words text-sm text-slate-300" id="extracted-text">{result.extracted_text || 'No readable text.'}</p>
      <p className="mt-2 text-xs text-slate-500">Source: {result.ocr_source?.toLowerCase().includes('gemini') ? 'Text Extraction' : (result.ocr_source || 'Text Extraction')}</p>
    </details>
    <div className="border-t border-slate-700 pt-4">
      <p className="mb-2 text-sm text-slate-300">Correct this result for future training</p>
      <div className="flex flex-wrap gap-2">{['Non-Harmful', 'Harmful', 'Not a meme'].map(verdict => <button key={verdict} disabled={pending || !result.persisted}
        onClick={() => correct(verdict)} className="rounded-lg border border-slate-600 px-3 py-2 text-sm text-slate-200 hover:bg-slate-700 disabled:opacity-40">
        {verdict === 'Non-Harmful' ? 'Mark Safe' : `Mark ${verdict}`}
      </button>)}</div>
      {message && <p role="status" className="mt-2 text-sm text-emerald-300">{message}</p>}
      {error && <p role="alert" className="mt-2 text-sm text-red-300">{error}</p>}
    </div>
  </div>;
}
