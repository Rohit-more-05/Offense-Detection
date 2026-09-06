import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Upload, ImageIcon, X } from 'lucide-react';
import { ACCEPTED_MIME_TYPES } from '../utils/constants';

/**
 * UploadZone
 * Drag-and-drop / click-to-browse meme upload area.
 *
 * Props:
 *   onFileSelected(file, previewUrl) - called when a valid file is chosen
 *   selectedFile     - currently selected File object (or null)
 *   previewUrl       - blob URL for the selected image
 *   onClear()        - clears selection
 *   disabled         - disable interactions during loading
 */
export default function UploadZone({ onFileSelected, selectedFile, previewUrl, onClear, disabled }) {
  console.log('[UploadZone] mounted');
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef(null);

  const handleFile = useCallback((file) => {
    console.log('[UploadZone] state: file selected —', file.name, file.type, file.size);
    if (!ACCEPTED_MIME_TYPES.includes(file.type)) {
      console.error('[UploadZone] ERROR: rejected file type', file.type);
      alert(`Invalid file type: ${file.type}. Please upload a JPG, PNG, or WEBP.`);
      return;
    }
    const url = URL.createObjectURL(file);
    onFileSelected(file, url);
  }, [onFileSelected]);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    if (disabled) return;
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [disabled, handleFile]);

  const onDragOver = (e) => { e.preventDefault(); if (!disabled) setIsDragging(true); };
  const onDragLeave = () => setIsDragging(false);

  const onInputChange = (e) => {
    const file = e.target.files[0];
    if (file) handleFile(file);
  };

  // Cleanup blob URLs on unmount
  useEffect(() => {
    return () => { if (previewUrl) URL.revokeObjectURL(previewUrl); };
  }, [previewUrl]);

  if (previewUrl && selectedFile) {
    return (
      <div className="relative overflow-hidden rounded-2xl border border-slate-600/50 bg-slate-800/50">
        <img
          src={previewUrl}
          alt="Selected meme preview"
          className="h-72 w-full object-contain bg-slate-900/50"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-slate-900/80 to-transparent" />
        <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ImageIcon size={14} className="text-slate-300" />
            <span className="truncate text-sm text-slate-300 max-w-[200px]">{selectedFile.name}</span>
            <span className="text-xs text-slate-400">({(selectedFile.size / 1024).toFixed(1)} KB)</span>
          </div>
          {!disabled && (
            <button
              id="btn-clear-file"
              onClick={onClear}
              className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-700/80 text-slate-400 hover:bg-red-500/30 hover:text-red-300 transition-colors"
            >
              <X size={14} />
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onClick={() => !disabled && inputRef.current?.click()}
      className={`relative flex h-72 cursor-pointer flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed transition-all duration-300 ${
        isDragging
          ? 'border-violet-400 bg-violet-500/10 scale-[1.01]'
          : 'border-slate-600/60 bg-slate-800/30 hover:border-violet-500/60 hover:bg-violet-500/5'
      } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".jpg,.jpeg,.png,.webp"
        className="hidden"
        onChange={onInputChange}
        disabled={disabled}
        id="input-file-upload"
      />

      <div className={`flex h-16 w-16 items-center justify-center rounded-2xl transition-all duration-300 ${
        isDragging ? 'bg-violet-600/30 text-violet-300' : 'bg-slate-700/60 text-slate-400'
      }`}>
        <Upload size={28} />
      </div>

      <div className="text-center">
        <p className="text-base font-medium text-slate-300">
          {isDragging ? 'Drop your meme here' : 'Drag & drop a meme here'}
        </p>
        <p className="mt-1 text-sm text-slate-500">or click to browse — JPG, PNG, WEBP</p>
      </div>

      {isDragging && (
        <div className="absolute inset-0 rounded-2xl bg-violet-500/5 animate-pulse pointer-events-none" />
      )}
    </div>
  );
}
