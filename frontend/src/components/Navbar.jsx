import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, ShieldAlert, Zap } from 'lucide-react';

/**
 * Navbar
 * Global navigation bar with links to Dashboard and Moderator Queue.
 */
export default function Navbar() {
  console.log('[Navbar] mounted');

  const linkClass = ({ isActive }) =>
    `flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
      isActive
        ? 'bg-violet-600/30 text-violet-300 border border-violet-500/40'
        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
    }`;

  return (
    <nav className="sticky top-0 z-50 border-b border-slate-700/60 bg-slate-900/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-violet-600 to-indigo-600 shadow-lg shadow-violet-500/25">
            <Zap size={16} className="text-white" />
          </div>
          <span className="bg-gradient-to-r from-violet-300 to-indigo-300 bg-clip-text text-base font-bold tracking-tight text-transparent">
            MemeGuard
          </span>
          <span className="hidden rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-[10px] font-medium text-violet-400 sm:inline">
            Phase 1 — Mock
          </span>
        </div>

        {/* Nav links */}
        <div className="flex items-center gap-2">
          <NavLink to="/" className={linkClass} id="nav-dashboard">
            <LayoutDashboard size={16} />
            <span>Dashboard</span>
          </NavLink>
          <NavLink to="/moderator" className={linkClass} id="nav-moderator">
            <ShieldAlert size={16} />
            <span>Moderator Queue</span>
          </NavLink>
        </div>
      </div>
    </nav>
  );
}
