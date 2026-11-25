"use client";
import { useCallback, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession } from "@/hooks/use-session";
import { api } from "@/services/api";
import type { Project } from "@/types/project";
import { activeDocument, type ProjectDocument, type UploadAccepted } from "@/types/document";
import { activeJob, type Citation, type Job, type ProcessResult } from "@/types/analysis";
import { ProjectDetail } from "./projects";
import { DocumentUpload } from "./document-upload";
import { DocumentList } from "./document-list";
import { AnalysisForm } from "./analysis-form";
import { JobProgress } from "./job-progress";
import { ProcessResults } from "./process-results";
import { Card } from "./common";
import { Button } from "./ui/button";
import { WorkflowEditor } from "./workflow-editor";
type TrackedJob = { id: string; kind: "parse" | "analysis" };
function readJobs(id: string): TrackedJob[] {
  try { const value: unknown = JSON.parse(sessionStorage.getItem(`project-jobs:${id}`) || "[]"); return Array.isArray(value) ? value.filter((job) => typeof job?.id === "string" && ["parse", "analysis"].includes(job.kind)).slice(-50) : []; } catch { return []; }
}
export function ProjectWorkspace({ id }: { id: string }) {
  const query = useQuery({ queryKey: ["project", id], queryFn: ({ signal }) => api<Project>(`projects/${id}`, { signal }) });
  return <><ProjectDetail id={id} />{query.isSuccess && <WorkspaceSections key={id} project={query.data} />}</>;
}
function WorkspaceSections({ project }: { project: Project }) {
  const id = project.id;
  const session = useSession();
  const role = session.data?.authenticated ? session.data.local ? "owner" : session.data.account?.role : undefined;
  const canEdit = ["owner", "admin", "lawyer"].includes(role || "");
  const cache = useQueryClient();
  const [selected, setSelected] = useState<string[]>([]);
  const [editorOpen, setEditorOpen] = useState(false);
  const [jobs, setJobs] = useState<TrackedJob[]>(() => readJobs(id));
  const [jobStates, setJobStates] = useState<Record<string, Job>>({});
  const terminalSeen = useRef(new Set<string>());
  const documents = useQuery({ queryKey: ["documents", id], queryFn: ({ signal }) => api<ProjectDocument[]>(`projects/${id}/documents`, { signal }), refetchInterval: (query) => !query.state.error && query.state.data?.some((document) => activeDocument(document.status)) ? 1500 : false });
  const result = useQuery({ queryKey: ["stages", id], queryFn: ({ signal }) => api<ProcessResult>(`projects/${id}/stages`, { signal }) });
  const citations = useQuery({ queryKey: ["citations", id], queryFn: ({ signal }) => api<Citation[]>(`projects/${id}/citations`, { signal }) });
  const refresh = useCallback(async () => { await Promise.all(["documents", "stages", "citations", "project", "project-activity", "projects"].map((key) => cache.invalidateQueries({ queryKey: key === "projects" ? [key] : [key, id] }))); }, [cache, id]);
  const onJobChange = useCallback((job: Job) => {
    setJobStates((previous) => previous[job.id] === job ? previous : { ...previous, [job.id]: job });
    if (!activeJob(job) && !terminalSeen.current.has(job.id)) { terminalSeen.current.add(job.id); void refresh(); }
  }, [refresh]);
  function track(job: Job, kind: TrackedJob["kind"]) {
    cache.setQueryData(["job", job.id], job); setJobStates((value) => ({ ...value, [job.id]: job }));
    setJobs((value) => { const next = [...value.filter((item) => item.id !== job.id && (kind === "parse" || item.kind !== "analysis")), { id: job.id, kind }].slice(-50); try { sessionStorage.setItem(`project-jobs:${id}`, JSON.stringify(next)); } catch { /* Tracking remains available for this visit if browser storage is disabled. */ } return next; });
    void refresh();
  }
  const activeAnalysis = jobs.some((job) => job.kind === "analysis" && (!jobStates[job.id] || activeJob(jobStates[job.id])));
  const selectionReady = documents.isSuccess && selected.every((selectedId) => documents.data.some((document) => document.id === selectedId && document.status === "completed"));
  return <div className="project-workspace">
    <section aria-labelledby="workflow-editor-title"><h2 id="workflow-editor-title">Visual workflow</h2><Card>
      {editorOpen ? <WorkflowEditor projectId={id} canEdit={canEdit} onSaved={() => void refresh()} /> : <><p>Build or edit a saved workflow. Manual editing works without an AI provider.</p><Button onClick={() => setEditorOpen(true)}>Open workflow editor</Button></>}
    </Card></section>
    <nav className="workspace-sections" aria-label="Project sections"><a href="#documents">Documents</a><a href="#analysis">Analysis</a><a href="#results">Stages and citations</a></nav>
    <section id="documents" aria-labelledby="documents-title"><h2 id="documents-title">Documents</h2><Card>
      {canEdit && <DocumentUpload projectId={id} onAccepted={(accepted: UploadAccepted) => track(accepted.job, "parse")} />}
      {documents.isPending ? <p role="status">Loading documents…</p> : documents.error ? <div><p role="alert">{documents.error.message}</p><Button variant="outline" onClick={() => documents.refetch()}>Retry documents</Button></div> : <DocumentList documents={documents.data} selected={selected} canEdit={canEdit} disabled={activeAnalysis} onSelect={(documentId, checked) => setSelected((value) => checked ? [...new Set([...value, documentId])] : value.filter((item) => item !== documentId))} onRetry={async (documentId) => { const accepted = await api<UploadAccepted>(`documents/${documentId}/retry`, { method: "POST" }); track(accepted.job, "parse"); }} onDelete={async (documentId) => { await api(`documents/${documentId}`, { method: "DELETE" }); setSelected((value) => value.filter((item) => item !== documentId)); await refresh(); }} />}
      {jobs.filter((job) => job.kind === "parse").map((job) => <JobProgress key={job.id} id={job.id} kind="parse" onChange={onJobChange} />)}
    </Card></section>
    <section id="analysis" aria-labelledby="analysis-title"><h2 id="analysis-title">Analysis</h2><Card>{canEdit ? <AnalysisForm project={project} selected={selected} selectionReady={selectionReady} disabled={activeAnalysis} onSubmitted={(job) => track(job, "analysis")} /> : <p>Your role can view documents and stored analysis. An owner, administrator or lawyer can submit an analysis.</p>}{jobs.filter((job) => job.kind === "analysis").map((job) => <JobProgress key={job.id} id={job.id} kind="analysis" onChange={onJobChange} />)}</Card></section>
    <section id="results" aria-labelledby="results-title"><h2 id="results-title">Stages and citations</h2><Card>
      {result.isPending || citations.isPending ? <p role="status">Loading stored analysis…</p> : result.error || citations.error ? <div><p role="alert">{result.error?.message || citations.error?.message}</p><Button variant="outline" onClick={() => { void result.refetch(); void citations.refetch(); }}>Retry results</Button></div> : <ProcessResults result={result.data} citations={citations.data} />}
    </Card></section>
  </div>;
}
