import React, { useEffect } from 'react';
import { ScanSearch } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL?.replace('/api/v1', '') || 'http://localhost:8000';

/**
 * ExplainabilityPanel
 * Side-by-side: original image | attention heatmap stub.
 *
 * Props:
 *   originalPreviewUrl - blob URL of the uploaded image
 *   heatmapUrl         - relative URL from API (e.g. /static/heatmaps/placeholder.png)
 */
export default function ExplainabilityPanel({ originalPreviewUrl, heatmapUrl }) {
  useEffect(() => {
    console.log('[ExplainabilityPanel] mounted — heatmapUrl=%s', heatmapUrl);
  }, [heatmapUrl]);

  const fullHeatmapUrl = heatmapUrl
    ? `${API_BASE}${heatmapUrl}`
    : null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <ScanSearch size={16} className="text-violet-400" />
        <h3 className="text-sm font-semibold text-slate-300">Explainability View</h3>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {/* Original image */}
        <div className="overflow-hidden rounded-xl border border-slate-700/50 bg-slate-800/40">
          <div className="border-b border-slate-700/40 px-3 py-1.5">
            <span className="text-xs font-medium text-slate-400">Original Upload</span>
          </div>
          <div className="flex h-40 items-center justify-center bg-slate-900/30">
            {originalPreviewUrl ? (
              <img
                src={originalPreviewUrl}
                alt="Original meme"
                className="h-full w-full object-contain"
                id="explainability-original"
              />
            ) : (
              <span className="text-xs text-slate-600">No image</span>
            )}
          </div>
        </div>

        {/* Heatmap */}
        <div className="overflow-hidden rounded-xl border border-violet-500/20 bg-slate-800/40">
          <div className="border-b border-violet-500/20 px-3 py-1.5">
            <span className="text-xs font-medium text-violet-400">Attention Heatmap</span>
            <span className="ml-2 text-[10px] text-slate-500">(Phase 2 preview)</span>
          </div>
          <div className="flex h-40 items-center justify-center bg-slate-900/30">
            {fullHeatmapUrl ? (
              <img
                src={fullHeatmapUrl}
                alt="Attention heatmap"
                className="h-full w-full object-contain opacity-90"
                id="explainability-heatmap"
                onError={(e) => {
                  console.error('[ExplainabilityPanel] ERROR: heatmap image failed to load', fullHeatmapUrl);
                  e.target.style.display = 'none';
                }}
              />
            ) : (
              <span className="text-xs text-slate-600">No heatmap</span>
            )}
          </div>
        </div>
      </div>

      <p className="text-xs text-slate-600 italic">
        Grad-CAM / attention-rollout visualization will replace this stub in Phase 2.
      </p>
    </div>
  );
}
