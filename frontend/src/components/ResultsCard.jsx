import React, { useEffect } from 'react';
import { Tag, Timer } from 'lucide-react';
import ConfidenceMeter from './ConfidenceMeter';
import ModerationBanner from './ModerationBanner';
import ExplainabilityPanel from './ExplainabilityPanel';
import { LABEL_CONFIG } from '../utils/constants';

/**
 * ResultsCard
 * Displays the full prediction result after the API returns.
 *
 * Props:
 *   result          - PredictResponse object from API
 *   originalPreview - blob URL of the uploaded file for explainability panel
 */
export default function ResultsCard({ result, originalPreview }) {
  useEffect(() => {
    console.log('[ResultsCard] mounted — result:', result);
  }, [result]);

  const labelCfg = LABEL_CONFIG[result.label] || LABEL_CONFIG['Safe'];

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header row: label pill + execution time */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Tag size={16} className="text-slate-400" />
          <span className="text-sm font-medium text-slate-400">Classification</span>
          <span
            id="result-label-pill"
            className={`rounded-full px-3 py-1 text-sm font-bold ${labelCfg.pillClass}`}
          >
            {result.label}
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <Timer size={12} />
          <span id="result-execution-time">{result.execution_time_ms}ms</span>
        </div>
      </div>

      {/* Confidence meter */}
      <ConfidenceMeter confidence={result.confidence} label={result.label} />

      {/* Moderation banner */}
      <ModerationBanner decision={result.moderation_decision} />

      {/* Explainability panel */}
      <ExplainabilityPanel
        originalPreviewUrl={originalPreview}
        heatmapUrl={result.heatmap_url}
      />

      {/* Prediction ID (for debugging) */}
      <p className="text-[10px] text-slate-700 font-mono">
        ID: {result.prediction_id}
      </p>
    </div>
  );
}
