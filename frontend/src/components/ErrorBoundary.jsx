import React, { Component } from 'react';
import { AlertOctagon } from 'lucide-react';

/**
 * ErrorBoundary
 * Top-level React Error Boundary.
 * Catches render errors, logs full error + component stack to console,
 * and shows a visible fallback UI instead of a blank white screen.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, info: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary] ERROR caught:', error);
    console.error('[ErrorBoundary] Component stack:', info.componentStack);
    this.setState({ info });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, info: null });
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 p-8">
        <div className="w-full max-w-lg rounded-2xl border border-red-500/30 bg-red-500/10 p-8 text-center">
          <AlertOctagon size={48} className="mx-auto mb-4 text-red-400" />
          <h1 className="text-xl font-bold text-red-300">Something went wrong</h1>
          <p className="mt-2 text-sm text-slate-400">
            An unexpected error occurred. The full error has been logged to the browser console.
          </p>
          {import.meta.env.DEV && (
            <pre className="mt-4 overflow-auto rounded-lg bg-slate-900/80 p-4 text-left text-xs text-red-300 max-h-48">
              {this.state.error?.toString()}
              {'\n'}
              {this.state.info?.componentStack}
            </pre>
          )}
          <button
            id="btn-error-boundary-reset"
            onClick={this.handleReset}
            className="mt-6 rounded-lg bg-red-500/20 px-6 py-2.5 text-sm font-medium text-red-300 hover:bg-red-500/30 transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }
}
