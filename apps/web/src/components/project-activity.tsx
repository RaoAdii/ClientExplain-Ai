"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import type { ProjectActivity as Activity } from "@/types/project";
import { Card, LoadingState } from "./common";
import { Button } from "./ui/button";

const actionLabels: Record<string, string> = {
  "project.created": "Project created", "project.updated": "Project details updated", "project.review_changed": "Review status changed",
  "document.uploaded": "Document uploaded", "document.deleted": "Document deleted",
  "analysis.requested": "Analysis requested", "analysis.completed": "Analysis completed", "analysis.failed": "Analysis failed",
};

export function ProjectActivity({ projectId }: { projectId: string }) {
  const query = useQuery({ queryKey: ["project-activity", projectId], queryFn: ({ signal }) => api<Activity[]>(`projects/${projectId}/activity`, { signal }) });
  return (
    <section className="project-activity" aria-labelledby="activity-heading">
      <h2 id="activity-heading">Activity</h2>
      <Card>
        {query.isPending ? <LoadingState text="Loading activity…" /> : query.error ? <><p role="alert">{query.error.message}</p><Button variant="outline" onClick={() => query.refetch()}>Retry activity</Button></> : query.data.length === 0 ? <p className="muted">No activity recorded yet.</p> : (
          <ol className="activity-list">
            {query.data.map((event) => <li key={event.id}><strong>{actionLabels[event.action] || event.action}</strong><time dateTime={event.created_at}>{new Date(event.created_at).toLocaleString()}</time></li>)}
          </ol>
        )}
      </Card>
    </section>
  );
}
