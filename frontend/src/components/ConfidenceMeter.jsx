import React, { useEffect } from 'react';

/**
 * ConfidenceMeter
 * Animated horizontal progress bar showing confidence %.
 *
 * Props:
 *   confidence - float 0.0 – 1.0
 *   label      - "Harmful" | "Safe"
 */
export default function ConfidenceMeter({ confidence, label }) {
  useEffect(() => {
    console.log('[ConfidenceMeter] mounted — confidence=%f label=%s', confidence, label);
  }, [confidence, label]);

  const pct = Math.round(confidence * 100);

  const barColor =
    confidence > 0.9
      ? 'from-red-600 to-red-400'
      : confidence < 0.1
      ? 'from-emerald-600 to-emerald-400'
      : 'from-amber-600 to-amber-400';

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-400 font-medium">Confidence Score</span>
        <span className="font-bold text-slate-200 tabular-nums">{pct}%</span>
      </div>
      <div className="relative h-3 w-full overflow-hidden rounded-full bg-slate-700/60">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${barColor} transition-all duration-700 ease-out`}
          style={{ width: `${pct}%` }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Confidence: ${pct}%`}
          id="confidence-bar"
        />
        {/* Shimmer effect */}
        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent animate-shimmer pointer-events-none" />
      </div>
      <div className="flex justify-between text-xs text-slate-600">
        <span>Safe ←</span>
        <span>→ Harmful</span>
      </div>
    </div>
  );
}
