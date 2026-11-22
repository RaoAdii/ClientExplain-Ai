import { supabase } from "@/lib/supabase";
import { ApiError } from "./api";
import type { UploadAccepted } from "@/types/document";
export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
export function validateDocument(file: File): string | null {
  const types: Record<string, string> = { pdf: "application/pdf", docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", txt: "text/plain" };
  const extension = file.name.split(".").pop()?.toLowerCase() || "";
  if (!types[extension] || (file.type && file.type !== types[extension])) return "Choose a PDF, DOCX or UTF-8 TXT file with a matching file type.";
  if (!file.size) return "The document is empty. Choose a file containing text.";
  if (file.size > MAX_UPLOAD_BYTES) return "Choose a document no larger than 25 MB.";
  if (file.name.length > 255 || /[\x00-\x1f]/.test(file.name)) return "Provide a valid filename of at most 255 characters.";
  return null;
}
export async function uploadDocument(projectId: string, file: File, onProgress: (progress: number | null) => void, signal?: AbortSignal): Promise<UploadAccepted> {
  const validation = validateDocument(file);
  if (validation) throw new Error(validation);
  const session = supabase ? (await supabase.auth.getSession()).data.session : null;
  if (signal?.aborted) throw new DOMException("Upload cancelled.", "AbortError");
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/backend/projects/${encodeURIComponent(projectId)}/documents`);
    xhr.timeout = 120000;
    if (session) xhr.setRequestHeader("Authorization", `Bearer ${session.access_token}`);
    const abort = () => xhr.abort();
    const cleanup = () => signal?.removeEventListener("abort", abort);
    signal?.addEventListener("abort", abort, { once: true });
    xhr.upload.onprogress = (event) => onProgress(event.lengthComputable ? Math.round(event.loaded * 100 / event.total) : null);
    xhr.onload = () => {
      cleanup();
      let body;
      try { body = JSON.parse(xhr.responseText); } catch { reject(new Error("The upload response could not be read. Refresh documents before retrying.")); return; }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as UploadAccepted);
      else reject(new ApiError(xhr.status === 409 ? "This document is already uploaded. Select the existing document, or delete it before uploading a replacement." : body?.error?.message || "Upload failed. Check your connection and try again.", xhr.status));
    };
    xhr.onerror = () => { cleanup(); reject(new Error("Upload connection interrupted. Refresh documents before retrying.")); };
    xhr.ontimeout = () => { cleanup(); reject(new Error("Upload timed out. Refresh documents before retrying.")); };
    xhr.onabort = () => { cleanup(); reject(new DOMException("Upload cancelled.", "AbortError")); };
    const form = new FormData();
    // Some operating systems do not supply a MIME type for DOCX/TXT files.
    const media = { pdf: "application/pdf", docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", txt: "text/plain" };
    form.append("file", file.type ? file : new File([file], file.name, { type: media[file.name.split(".").pop()!.toLowerCase() as keyof typeof media] }));
    xhr.send(form);
  });
}
