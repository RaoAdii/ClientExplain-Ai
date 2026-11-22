import type { ProjectInput } from "@/lib/validation";
export type { ProjectInput } from "@/lib/validation";

export type WorkflowStatus = "draft" | "active" | "archived";
export type ReviewStatus = "requires_review" | "in_review" | "approved";
export type ProcessingStatus = "idle" | "queued" | "running" | "completed" | "failed" | "cancelled";

export type Project = ProjectInput & {
  id: string;
  review_status: ReviewStatus;
  processing_status: ProcessingStatus;
  owner_id: string;
  created_at: string;
  updated_at: string;
};

export type ProjectList = { items: Project[]; total: number; limit: number; offset: number };
export type ProjectActivity = { id: string; action: string; actor_id: string | null; resource_id: string; created_at: string };

export const workflowLabels: Record<WorkflowStatus, string> = { draft: "Draft", active: "Active", archived: "Archived" };
export const reviewLabels: Record<ReviewStatus, string> = { requires_review: "Requires professional review", in_review: "In review", approved: "Approved" };
export const processingLabels: Record<ProcessingStatus, string> = { idle: "Idle", queued: "Queued", running: "Running", completed: "Completed", failed: "Failed", cancelled: "Cancelled" };
