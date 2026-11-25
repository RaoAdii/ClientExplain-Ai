export type EditorStage = {
  id: string; title: string; explanation: string; responsible_party: string | null;
  required_documents: string[]; limitations: string[]; position: { x: number; y: number };
  actions: string[]; preconditions: string[]; outcomes: string[];
  status: "pending" | "in_progress" | "completed";
};
export type WorkflowGraph = { version: number; stages: EditorStage[]; edges: { source: string; target: string }[]; review_status: string };
