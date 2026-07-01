"use client";

import { useCallback, useRef, useState } from "react";

interface UploadPanelProps {
  onUpload: (file: File) => void;
  disabled: boolean;
}

export function UploadPanel({ onUpload, disabled }: UploadPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);

  const handleFile = useCallback(
    (file: File) => {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        alert("Only PDF files are supported.");
        return;
      }
      setFileName(file.name);
      onUpload(file);
    },
    [onUpload],
  );

  return (
    <div
      className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
        dragOver
          ? "border-blue-500 bg-blue-50"
          : "border-gray-300 hover:border-gray-400"
      } ${disabled ? "opacity-50 pointer-events-none" : "cursor-pointer"}`}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
        }}
      />

      <div className="text-gray-500">
        {fileName ? (
          <p className="font-medium text-gray-700">{fileName}</p>
        ) : (
          <>
            <p className="text-lg font-medium">Drop a CMC submission PDF here</p>
            <p className="mt-1 text-sm">or click to browse</p>
          </>
        )}
      </div>
    </div>
  );
}
