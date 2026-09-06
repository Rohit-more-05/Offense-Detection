import React, { useEffect } from 'react';
import { CheckCircle, AlertTriangle, Clock } from 'lucide-react';
import { DECISIONS, DECISION_CONFIG } from '../utils/constants';

/**
 * ModerationBanner
 * Full-width banner that changes colour/icon/text based on moderation_decision.
 *
 * Props:
 *   decision - "AUTO_APPROVE" | "AUTO_FLAG" | "HUMAN_REVIEW"
 */
export default function ModerationBanner({ decision }) {
  useEffect(() => {
    console.log('[ModerationBanner] mounted — decision=%s', decision);
  }, [decision]);

  const cfg = DECISION_CONFIG[decision] || DECISION_CONFIG[DECISIONS.HUMAN_REVIEW];

  const IconMap = {
    [DECISIONS.AUTO_APPROVE]: CheckCircle,
    [DECISIONS.AUTO_FLAG]: AlertTriangle,
    [DECISIONS.HUMAN_REVIEW]: Clock,
  };
  const Icon = IconMap[decision] || Clock;

  return (
    <div
      id="moderation-banner"
      className={`flex items-start gap-4 rounded-xl border p-4 ${cfg.bgClass} animate-fade-in`}
    >
      <div className={`mt-0.5 shrink-0 ${cfg.textClass}`}>
        <Icon size={22} />
      </div>
      <div>
        <p className={`text-base font-semibold ${cfg.textClass}`}>{cfg.label}</p>
        <p className="mt-0.5 text-sm text-slate-400">{cfg.description}</p>
      </div>
    </div>
  );
}
