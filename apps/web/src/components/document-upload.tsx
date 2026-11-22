"use client";
import { useEffect, useRef, useState } from "react";
import { uploadDocument, validateDocument } from "@/services/uploads";
import type { UploadAccepted } from "@/types/document";
import { Button } from "./ui/button";
export function DocumentUpload({ projectId, onAccepted }: { projectId: string; onAccepted: (result: UploadAccepted) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const controller = useRef<AbortController | null>(null);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function upload() {
    if (!file) return;
    const request = new AbortController(); controller.current = request;
    setBusy(true); setError(null); setProgress(null);
    try {
      const result = await uploadDocument(projectId, file, setProgress, request.signal);
      if (!request.signal.aborted) { onAccepted(result); setFile(null); if (input.current) input.current.value = ""; }
    } catch (failure) { if (!request.signal.aborted) setError(failure instanceof Error ? failure.message : "Upload failed. Try again."); }
    finally { if (!request.signal.aborted) setBusy(false); }
  }
  return <div className="upload-panel">
    <p id="upload-help">Upload PDF, DOCX or UTF-8 TXT, up to 25 MB. Scanned pages need OCR before analysis. Use documents you are authorized to process.</p>
    <div className="field"><label htmlFor="document-file">Document file</label><input ref={input} id="document-file" type="file" accept=".pdf,.docx,.txt" aria-describedby="upload-help" disabled={busy} onChange={(event) => { const next = event.target.files?.[0] || null; setFile(next); setError(next ? validateDocument(next) : null); }} /></div>
    {error && <p role="alert">{error}</p>}
    {busy && <div role="status"><p>{progress === 100 ? "Bytes sent. Waiting for the server to accept the upload…" : progress === null ? "Uploading document…" : `Uploading document: ${progress}%`}</p><progress aria-label="Upload progress" max={100} value={progress ?? undefined} /></div>}
    <Button disabled={busy || !file || !!validateDocument(file)} onClick={upload}>{busy ? "Uploading…" : "Upload document"}</Button>
  </div>;
}
