"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import type { DocumentDetail, ProjectDocument } from "@/types/document";
import { activeDocument } from "@/types/document";
import { Button } from "./ui/button";
const statusLabels: Record<string, string> = { uploaded: "Uploaded; awaiting parsing", queued: "Queued for parsing", running: "Parsing", processing: "Parsing", completed: "Ready for analysis", failed: "Parsing failed", ocr_required: "OCR required; upload a text-readable copy" };
function DocumentInfo({ id }: { id: string }) {
  const query = useQuery({ queryKey: ["document", id], queryFn: ({ signal }) => api<DocumentDetail>(`documents/${id}`, { signal }), refetchInterval: (q) => !q.state.error && activeDocument(q.state.data?.status || "") ? 1500 : false });
  if (query.isPending) return <p role="status">Loading document details…</p>;
  if (query.error) return <div><p role="alert">{query.error.message}</p><Button variant="outline" onClick={() => query.refetch()}>Retry document details</Button></div>;
  return <div className="document-info"><p>{query.data.page_count === null ? "Page count unavailable" : `${query.data.page_count} page(s)`}</p>{query.data.parsing_error && <p role="alert">{query.data.parsing_error}</p>}{query.data.ocr_required && <p>OCR is required. Upload a text-readable copy; this document cannot be analyzed.</p>}</div>;
}
export function DocumentList({ documents, selected, onSelect, onDelete, onRetry, canEdit, disabled = false }: { documents: ProjectDocument[]; selected: string[]; onSelect: (id: string, checked: boolean) => void; onDelete: (id: string) => Promise<void>; onRetry: (id: string) => Promise<void>; canEdit: boolean; disabled?: boolean }) {
  const [details, setDetails] = useState<string[]>([]);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!documents.length) return <p>No documents uploaded yet. You can analyze process text without documents.</p>;
  const readyDocuments = documents.filter((document) => document.status === "completed");
  const allReadySelected = readyDocuments.length > 0 && readyDocuments.every((document) => selected.includes(document.id));
  return <>{error && <p role="alert">{error}</p>}{readyDocuments.length > 0 && <Button variant="outline" disabled={!canEdit || disabled} onClick={() => readyDocuments.forEach((document) => onSelect(document.id, !allReadySelected))}>{allReadySelected ? "Deselect all ready documents" : "Select all ready documents"}</Button>}<ul className="document-list" aria-label="Project documents">{documents.map((document) => <li key={document.id}>
    <div className="document-row"><label className="checkbox-label"><input type="checkbox" aria-label={`Select ${document.filename}`} checked={selected.includes(document.id)} disabled={!canEdit || disabled || document.status !== "completed"} onChange={(event) => onSelect(document.id, event.target.checked)} /><strong>{document.filename}</strong></label><span>{statusLabels[document.status] || document.status}</span><span className="muted">{(document.byte_size / 1024).toFixed(1)} KB</span></div>
    <div className="form-actions"><Button variant="ghost" onClick={() => setDetails((value) => value.includes(document.id) ? value.filter((id) => id !== document.id) : [...value, document.id])} aria-expanded={details.includes(document.id)}>Details for {document.filename}</Button>{canEdit && document.status === "failed" && <Button variant="outline" disabled={disabled || retrying === document.id} onClick={async () => { setError(null); setRetrying(document.id); try { await onRetry(document.id); } catch (failure) { setError(failure instanceof Error ? failure.message : "Retry failed. Try again."); } finally { setRetrying(null); } }}>{retrying === document.id ? "Retrying…" : `Retry processing ${document.filename}`}</Button>}{canEdit && <Button variant="outline" disabled={disabled} onClick={() => { setError(null); setDeleting(document.id); }}>Delete {document.filename}</Button>}</div>
    {details.includes(document.id) && <DocumentInfo id={document.id} />}
    {deleting === document.id && <div role="group" aria-label={`Confirm deletion of ${document.filename}`}><p>Delete this document? Stored stages and citations will also be cleared and dependent jobs cancelled.</p><div className="form-actions"><Button variant="outline" disabled={busy} onClick={() => setDeleting(null)}>Keep document</Button><Button variant="destructive" disabled={busy} onClick={async () => { setBusy(true); setError(null); try { await onDelete(document.id); setDeleting(null); } catch (failure) { setError(failure instanceof Error ? failure.message : "Deletion failed. Retry deletion."); } finally { setBusy(false); } }}>Confirm document deletion</Button></div></div>}
  </li>)}</ul></>;
}
