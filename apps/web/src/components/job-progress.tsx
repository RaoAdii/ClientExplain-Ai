"use client";
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { activeJob, type Job } from "@/types/analysis";
import { processingLabels } from "@/types/project";
import { Button } from "./ui/button";
export function JobProgress({ id, kind, onChange }: { id: string; kind: "parse" | "analysis"; onChange: (job: Job) => void }) {
  const query = useQuery({ queryKey: ["job", id], queryFn: ({ signal }) => api<Job>(`jobs/${id}`, { signal }), retry: false, refetchInterval: (q) => !q.state.error && activeJob(q.state.data) ? 1500 : false });
  useEffect(() => { if (query.data) onChange(query.data); }, [query.data, onChange]);
  const label = kind === "parse" ? "Parse" : "Analysis";
  if (query.isPending) return <p role="status">Loading {label.toLowerCase()} job…</p>;
  if (query.error) return <div><p role="alert">{query.error.message}</p><Button variant="outline" onClick={() => query.refetch()}>Retry {label.toLowerCase()} status</Button></div>;
  const job = query.data;
  return <div className="job-progress" role="status"><strong>{label} job: {processingLabels[job.status]}</strong><p>{job.current_stage || "Waiting for status"} · {job.progress}% · Retries: {job.retry_count}</p><progress aria-label={`${label} job progress`} value={job.progress} max={100} />{job.error_message && <p>{job.error_message}</p>}{job.error_code && <p>Error code: {job.error_code}</p>}{job.status === "failed" && <p>{kind === "analysis" ? "Review the error and submit the analysis form to retry." : "Upload a corrected copy, or delete the failed document before uploading the same file again."}</p>}{job.status === "cancelled" && <p>This job was cancelled. Review your documents before submitting again.</p>}</div>;
}
