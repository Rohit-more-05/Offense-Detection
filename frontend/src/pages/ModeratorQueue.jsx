import React, { useEffect } from 'react';
import { ShieldAlert } from 'lucide-react';
import ReviewQueueTable from '../components/ReviewQueueTable';

/**
 * ModeratorQueue page ("/moderator")
 * Displays pending human-review items.
 */
export default function ModeratorQueue() {
  useEffect(() => {
    console.log('[ModeratorQueue] mounted');
  }, []);

  return (
    <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      {/* Page header */}
      <div className="mb-8">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/15 border border-amber-500/25">
            <ShieldAlert size={20} className="text-amber-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-100">Moderator Queue</h1>
            <p className="text-sm text-slate-400">
              Review memes flagged for human moderation. Auto-refreshes every 10 seconds.
            </p>
          </div>
        </div>
      </div>

      {/* Queue table */}
      <div className="rounded-2xl border border-slate-700/50 bg-slate-800/30 p-6 shadow-xl shadow-black/20 backdrop-blur-sm">
        <ReviewQueueTable />
      </div>
    </main>
  );
}
