/**
 * utils/constants.js
 * ==================
 * Shared enums and display configuration for label colours, icons, and status strings.
 */

export const LABELS = {
  HARMFUL: 'Harmful',
  SAFE: 'Safe',
};

export const DECISIONS = {
  AUTO_APPROVE: 'AUTO_APPROVE',
  AUTO_FLAG: 'AUTO_FLAG',
  HUMAN_REVIEW: 'HUMAN_REVIEW',
};

export const DECISION_CONFIG = {
  [DECISIONS.AUTO_APPROVE]: {
    label: 'Auto-Approved',
    description: 'Content cleared automatically — confidence below harm threshold.',
    bgClass: 'bg-emerald-500/20 border-emerald-500/40',
    textClass: 'text-emerald-300',
    iconColor: '#10b981',
    icon: 'check-circle',
  },
  [DECISIONS.AUTO_FLAG]: {
    label: 'Auto-Flagged',
    description: 'Content automatically flagged — high confidence of harm.',
    bgClass: 'bg-red-500/20 border-red-500/40',
    textClass: 'text-red-300',
    iconColor: '#ef4444',
    icon: 'alert-triangle',
  },
  [DECISIONS.HUMAN_REVIEW]: {
    label: 'Escalated for Human Review',
    description: 'Ambiguous content — queued for moderator review.',
    bgClass: 'bg-amber-500/20 border-amber-500/40',
    textClass: 'text-amber-300',
    iconColor: '#f59e0b',
    icon: 'clock',
  },
};

export const LABEL_CONFIG = {
  [LABELS.HARMFUL]: {
    pillClass: 'bg-red-500/20 text-red-300 border border-red-500/40',
  },
  [LABELS.SAFE]: {
    pillClass: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40',
  },
};

export const ACCEPTED_MIME_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
export const MIN_LOADING_MS = 800; // Minimum fake inference wait for UX realism
