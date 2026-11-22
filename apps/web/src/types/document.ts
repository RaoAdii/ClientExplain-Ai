import type { Job } from "./analysis";
export type DocumentStatus = "uploaded" | "queued" | "running" | "processing" | "completed" | "failed" | "ocr_required";
export type ProjectDocument = { id: string; project_id: string; filename: string; media_type: string; byte_size: number; sha256: string; status: DocumentStatus; created_at: string; updated_at: string };
export type DocumentDetail = ProjectDocument & { page_count: number | null; parsing_error: string | null; ocr_required: boolean; download_url: string | null; download_url_expires_in: number | null };
export type UploadAccepted = { document: ProjectDocument; job: Job };
export const activeDocument = (status: string) => ["uploaded", "queued", "running", "processing"].includes(status);
