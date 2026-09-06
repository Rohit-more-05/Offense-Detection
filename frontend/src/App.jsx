import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import ModeratorQueue from './pages/ModeratorQueue';
import ErrorBoundary from './components/ErrorBoundary';

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <div className="min-h-screen bg-slate-950">
          <Navbar />
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/moderator" element={<ModeratorQueue />} />
          </Routes>
        </div>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
