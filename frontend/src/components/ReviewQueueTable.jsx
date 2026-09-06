import React, { useCallback, useEffect, useState } from 'react';
import { RefreshCw, CheckCircle2, XCircle, ShieldCheck, Inbox } from 'lucide-react';
import { getReviewQueue, submitVerdict } from '../api/client';
import { LABEL_CONFIG } from '../utils/constants';

const API_BASE = import.meta.env.VITE_API_BASE_URL?.replace('/api/v1', '') || 'http://localhost:8000';
const POLL_INTERVAL_MS = 10_000;

/**
 * ReviewQueueTable
 * Fetches and displays the human review queue with action buttons.
 */
export default function ReviewQueueTable() {
  console.log('[ReviewQueueTable] mounted');

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pendingIds, setPendingIds] = useState(new Set());

  const fetchQueue = useCallback(async () => {
    console.log('[ReviewQueueTable] state: fetching queue');
    try {
      const data = await getReviewQueue();
      setItems(data);
      setError(null);
      console.log('[ReviewQueueTable] state: queue loaded — %d items', data.length);
    } catch (err) {
      console.error('[ReviewQueueTable] ERROR:', err);
      setError(err.message || 'Failed to load review queue');
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch + polling
  useEffect(() => {
    fetchQueue();
    const interval = setInterval(fetchQueue, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchQueue]);

  const handleVerdict = useCallback(async (itemId, verdict) => {
    console.log('[ReviewQueueTable] state: submitting verdict — id=%s verdict=%s', itemId, verdict);
    setPendingIds((prev) => new Set(prev).add(itemId));

    // Optimistic update: remove from local list immediately
    setItems((prev) => prev.filter((i) => i.prediction_id !== itemId));

    try {
      await submitVerdict(itemId, verdict);
      console.log('[ReviewQueueTable] state: verdict accepted — id=%s', itemId);
    } catch (err) {
      console.error('[ReviewQueueTable] ERROR: verdict failed — id=%s', itemId, err);
      // Re-fetch to restore state on failure
      fetchQueue();
    } finally {
      setPendingIds((prev) => {
        const next = new Set(prev);
        next.delete(itemId);
        return next;
      });
    }
  }, [fetchQueue]);

  if (loading) {
    return (
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-20 animate-pulse rounded-xl bg-slate-800/50" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-6 text-center">
        <XCircle size={32} className="mx-auto mb-2 text-red-400" />
        <p className="text-sm font-medium text-red-300">Failed to load queue</p>
        <p className="mt-1 text-xs text-slate-400">{error}</p>
        <button
          id="btn-retry-queue"
          onClick={fetchQueue}
          className="mt-3 rounded-lg bg-red-500/20 px-4 py-2 text-xs font-medium text-red-300 hover:bg-red-500/30 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-700/40 bg-slate-800/30 py-16">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500/10 border border-emerald-500/20">
          <Inbox size={28} className="text-emerald-400" />
        </div>
        <p className="text-base font-semibold text-slate-300">No items pending review</p>
        <p className="mt-1 text-sm text-slate-500">All memes have been moderated. Queue is clear.</p>
        <button
          id="btn-refresh-queue-empty"
          onClick={fetchQueue}
          className="mt-4 flex items-center gap-2 rounded-lg bg-slate-700/50 px-4 py-2 text-xs font-medium text-slate-400 hover:bg-slate-700 hover:text-slate-300 transition-colors"
        >
          <RefreshCw size={12} />
          Refresh
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-400">
          <span className="font-semibold text-slate-200">{items.length}</span> item{items.length !== 1 ? 's' : ''} pending review
        </p>
        <button
          id="btn-refresh-queue"
          onClick={fetchQueue}
          className="flex items-center gap-1.5 rounded-lg bg-slate-700/50 px-3 py-1.5 text-xs font-medium text-slate-400 hover:bg-slate-700 hover:text-slate-300 transition-colors"
        >
          <RefreshCw size={12} />
          Refresh
        </button>
      </div>

      {/* Queue items */}
      {items.map((item) => {
        const isPending = pendingIds.has(item.prediction_id);
        const labelCfg = LABEL_CONFIG[item.label] || LABEL_CONFIG['Safe'];
        const thumbnailUrl = `${API_BASE}/static/uploads/${item.filename}`;
        const submittedAt = new Date(item.created_at).toLocaleString();
        const pct = Math.round(item.confidence * 100);

        return (
          <div
            key={item.prediction_id}
            className={`flex items-center gap-4 rounded-xl border border-slate-700/40 bg-slate-800/40 p-4 transition-all duration-300 ${
              isPending ? 'opacity-50 scale-95' : 'hover:border-slate-600/60 hover:bg-slate-800/60'
            }`}
            id={`queue-item-${item.prediction_id}`}
          >
            {/* Thumbnail */}
            <div className="h-14 w-14 shrink-0 overflow-hidden rounded-lg border border-slate-700/50 bg-slate-900/50">
              <img
                src={thumbnailUrl}
                alt={item.filename}
                className="h-full w-full object-cover"
                onError={(e) => { e.target.style.display = 'none'; }}
              />
            </div>

            {/* Info */}
            <div className="flex-1 min-w-0">
              <p className="truncate text-sm font-medium text-slate-300">{item.filename}</p>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${labelCfg.pillClass}`}>
                  {item.label}
                </span>
                <span className="text-xs text-slate-500">{pct}% confidence</span>
                <span className="text-xs text-slate-600">{submittedAt}</span>
              </div>
            </div>

            {/* Action buttons */}
            <div className="flex shrink-0 gap-2">
              <button
                id={`btn-safe-${item.prediction_id}`}
                onClick={() => handleVerdict(item.prediction_id, 'Non-Harmful')}
                disabled={isPending}
                className="flex items-center gap-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs font-medium text-emerald-300 hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
              >
                <CheckCircle2 size={13} />
                Mark Safe
              </button>
              <button
                id={`btn-harmful-${item.prediction_id}`}
                onClick={() => handleVerdict(item.prediction_id, 'Harmful')}
                disabled={isPending}
                className="flex items-center gap-1.5 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs font-medium text-red-300 hover:bg-red-500/20 transition-colors disabled:opacity-50"
              >
                <XCircle size={13} />
                Mark Harmful
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
