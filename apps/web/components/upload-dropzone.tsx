"use client";

import { useId, useState, type DragEvent } from "react";

interface UploadDropzoneProps {
  onFile: (file: File) => void;
  compact?: boolean;
}

export function UploadDropzone({ onFile, compact = false }: UploadDropzoneProps) {
  const inputId = useId();
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  function select(file: File | undefined) {
    if (!file) return;
    if (!/\.(mp3|wav|m4a|flac)$/i.test(file.name)) {
      setError("Choose an MP3, WAV, M4A, or FLAC audio file.");
      return;
    }
    setError(null);
    onFile(file);
  }

  function drop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    select(event.dataTransfer.files[0]);
  }

  return (
    <div
      className={`upload-dropzone${compact ? " upload-dropzone--compact" : ""}${dragging ? " is-dragging" : ""}`}
      data-testid="upload-dropzone"
      onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={drop}
    >
      <div className="upload-copy">
        <p className="upload-title">{compact ? "Start with another song" : "Drop a song onto the page"}</p>
        <p id={`${inputId}-hint`} className="muted">MP3, WAV, M4A or FLAC · one song at a time</p>
      </div>
      <div className="file-picker">
        <input
          id={inputId}
          type="file"
          accept=".mp3,.wav,.m4a,.flac"
          aria-describedby={`${inputId}-hint${error ? ` ${inputId}-error` : ""}`}
          onChange={(event) => {
            select(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
        <label className="button button--solid" htmlFor={inputId}>Choose a song <span aria-hidden="true">↗</span></label>
      </div>
      {error && <p id={`${inputId}-error`} role="alert" className="error-message">{error}</p>}
    </div>
  );
}
