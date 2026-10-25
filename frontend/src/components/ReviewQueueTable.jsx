import React, { useCallback, useEffect, useState } from 'react';
import { getReviewQueue, submitVerdict, imageUrl } from '../api/client';
import { LABEL_CONFIG } from '../utils/constants';

export default function ReviewQueueTable() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [pendingIds, setPendingIds] = useState(new Set());
  const [missingImages, setMissingImages] = useState(new Set());
  const [scope, setScope] = useState('all');
  const fetchQueue = useCallback(async () => {
    try { setItems(await getReviewQueue(scope)); setError(''); }
    catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }, [scope]);
  useEffect(() => {
    const initial = setTimeout(fetchQueue, 0);
    const timer = setInterval(fetchQueue, 10000);
    return () => { clearTimeout(initial); clearInterval(timer); };
  }, [fetchQueue]);
  async function verdict(id, value) {
    setActionError(''); setPendingIds(prev => new Set(prev).add(id));
    try {
      await submitVerdict(id, value);
      setItems(prev => prev.filter(item => item.prediction_id !== id));
    } catch (err) { setActionError(err.message); }
    finally { setPendingIds(prev => { const next = new Set(prev); next.delete(id); return next; }); }
  }
  if (loading) return <p className="text-slate-400">Loading review queue...</p>;
  return <div className="space-y-4">
    <div className="flex items-center justify-between gap-3 text-sm">
      <select aria-label="Review filter" value={scope} onChange={e => setScope(e.target.value)} className="rounded bg-slate-800 p-2 text-slate-200">
        <option value="all">All unreviewed uploads</option><option value="flagged">Flagged / needs review</option>
      </select><button onClick={fetchQueue} className="text-violet-300">Refresh</button>
    </div>
    {(error || actionError) && <p role="alert" className="rounded-lg bg-red-500/15 p-3 text-sm text-red-200">{error || actionError}</p>}
    {!error && items.length === 0 && <p className="py-8 text-center text-slate-400">No uploads awaiting a human verdict.</p>}
    {!error && items.map(item => <article key={item.prediction_id} className="rounded-xl border border-slate-700 p-4" id={`queue-item-${item.prediction_id}`}>
      <div className="flex flex-col gap-4 sm:flex-row">
        {missingImages.has(item.prediction_id)
          ? <p className="w-56 shrink-0 rounded-lg bg-slate-900 p-4 text-xs text-amber-300">The original image is unavailable. This older upload must be restored or uploaded again before it can be reviewed.</p>
          : <a href={imageUrl(item.image_url)} target="_blank" rel="noreferrer" className="shrink-0"><img src={imageUrl(item.image_url)} alt="Image awaiting moderation"
            onError={() => setMissingImages(prev => new Set(prev).add(item.prediction_id))}
            className="h-44 w-56 rounded-lg bg-slate-900 object-contain" /></a>}
        <div className="min-w-0 flex-1 space-y-2">
          <p className="break-words text-sm text-slate-300">{item.filename}</p>
          <span className={`inline-block rounded-full px-2 py-1 text-xs ${(LABEL_CONFIG[item.label] || LABEL_CONFIG['Needs review']).pillClass}`}>{item.label}</span>
          <p className="text-sm text-slate-400">{item.reason}</p>
          <details className="text-xs text-slate-400"><summary>Read extracted text</summary><p className="mt-2 whitespace-pre-wrap">{item.extracted_text || 'No saved transcription.'}</p></details>
          <div className="flex flex-wrap gap-2">{['Non-Harmful', 'Harmful', 'Not a meme'].map(value => <button key={value} disabled={pendingIds.has(item.prediction_id) || missingImages.has(item.prediction_id)} onClick={() => verdict(item.prediction_id, value)}
            className="rounded-lg border border-slate-600 px-3 py-2 text-xs text-slate-200 hover:bg-slate-700 disabled:opacity-40">{value === 'Non-Harmful' ? 'Mark Safe' : `Mark ${value}`}</button>)}</div>
        </div>
      </div>
    </article>)}
  </div>;
}
