"use client";
import Link from "next/link";
import { Suspense, useCallback, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Plus, FileText, MapPin, ArrowLeft, Trash2, Pencil, ShieldCheck } from "lucide-react";
import { api } from "@/services/api";
import { useSession } from "@/hooks/use-session";
import { processingLabels, reviewLabels, workflowLabels, type Project, type ProjectList, type ProjectInput } from "@/types/project";
import { useUI } from "@/stores/ui";
import { PageHeader, Card, LoadingState, EmptyState } from "./common";
import { Button } from "./ui/button";
import { ProjectForm } from "./project-form";
import { ProjectFilters } from "./project-filters";
import { ProjectActivity } from "./project-activity";

function useProjectPermissions() {
  const session = useSession();
  const role = session.data?.authenticated ? (session.data.local ? "owner" : session.data.account?.role) : undefined;
  return { loading: session.isPending, error: session.error, canEdit: role === "owner" || role === "admin" || role === "lawyer", canDelete: role === "owner" || role === "admin" };
}
function message(error: unknown, fallback: string) { return error instanceof Error ? error.message : fallback; }

export function Projects({ overview = false }: { overview?: boolean }) {
  return <Suspense fallback={<LoadingState text="Loading projects…" />}><ProjectLibrary overview={overview} /></Suspense>;
}

function ProjectLibrary({ overview }: { overview: boolean }) {
  const params = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const { canEdit } = useProjectPermissions();
  const serialized = params.toString();
  const search = (params.get("search") || "").trim().slice(0, 200);
  const rawStatus = params.get("status") || "";
  const rawReview = params.get("review_status") || "";
  const status = Object.hasOwn(workflowLabels, rawStatus) ? rawStatus : "";
  const reviewStatus = Object.hasOwn(reviewLabels, rawReview) ? rawReview : "";
  const rawPage = Number(params.get("page") || "1");
  const page = Number.isSafeInteger(rawPage) && rawPage > 0 && rawPage <= 1000000 ? rawPage : 1;
  const filtered = !!(search || status || reviewStatus);
  const changeFilters = useCallback((changes: Record<string, string>) => {
    const next = new URLSearchParams(serialized);
    for (const [key, value] of Object.entries(changes)) { if (value) next.set(key, value); else next.delete(key); }
    next.delete("page");
    router.replace(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false });
  }, [serialized, pathname, router]);
  function goToPage(value: number) {
    const next = new URLSearchParams(serialized);
    if (value === 1) next.delete("page"); else next.set("page", String(value));
    router.push(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false });
  }
  const query = useQuery({
    queryKey: ["projects", search, status, reviewStatus, page],
    queryFn: ({ signal }) => {
      const request = new URLSearchParams({ limit: "12", offset: String((page - 1) * 12) });
      if (search) request.set("search", search);
      if (status) request.set("status", status);
      if (reviewStatus) request.set("review_status", reviewStatus);
      return api<ProjectList>(`projects?${request}`, { signal });
    },
  });
  return (
    <>
      <PageHeader eyebrow={overview ? "Your legal process workspace" : "Workspace / Projects"} title={overview ? "A clearer starting point." : "Projects"}
        action={canEdit && <Button asChild><Link href="/dashboard/projects/new"><Plus size={17} /> New project</Link></Button>}>
        {overview ? "Bring the context for your next client explanation into one place." : "Organize and find the legal processes you want to explain."}
      </PageHeader>
      <ProjectFilters search={search} status={status} reviewStatus={reviewStatus} onChange={changeFilters} />
      <div className="section-title"><h2>{overview ? "Your projects" : "Project library"}</h2>
        {query.isSuccess && <span className="muted">{query.data.total} {query.data.total === 1 ? "project" : "projects"}</span>}
      </div>
      {query.isPending ? <LoadingState text="Loading projects…" /> : query.error ? (
        <Card><p role="alert">{query.error.message}</p><Button variant="outline" onClick={() => query.refetch()}>Try again</Button></Card>
      ) : query.data.items.length === 0 ? (
        <Card><EmptyState title={page > 1 ? "No projects on this page" : filtered ? "No matching projects" : "Your first explanation starts here"}
          action={!filtered && page === 1 && canEdit ? <Button asChild variant="outline"><Link href="/dashboard/projects/new"><Plus size={16} /> Create your first project</Link></Button> : undefined}>
          {page > 1 ? "Return to the previous page to view your projects." : filtered ? "Try a different search or clear the filters." : "Create a project to capture the process, jurisdiction, and context. Your saved projects will appear here."}
        </EmptyState></Card>
      ) : (
        <div className="project-grid">{query.data.items.map((project) => (
          <Link href={`/dashboard/projects/${project.id}`} key={project.id} className="project-card">
            <div className="project-card-top"><span className="project-icon"><FileText size={21} /></span><ArrowRight size={18} /></div>
            <span className="status-label">{reviewLabels[project.review_status]}</span>
            <h3>{project.name}</h3><p>{project.description || "No description added yet. Open this project to add context."}</p>
            <div className="project-statuses"><span>{workflowLabels[project.workflow_status]}</span><span>Processing: {processingLabels[project.processing_status]}</span></div>
            <div className="project-card-bottom"><span><MapPin size={14} />{project.jurisdiction || "Jurisdiction not recorded"}</span>
              <time dateTime={project.updated_at}>{new Date(project.updated_at).toLocaleDateString("en", { month: "short", day: "numeric" })}</time>
            </div>
          </Link>
        ))}</div>
      )}
      {(page > 1 || (query.data?.total ?? 0) > 12) && <nav className="pagination" aria-label="Project pages">
        <Button variant="outline" disabled={page === 1 || query.isPending} onClick={() => goToPage(page - 1)}>Previous</Button>
        <span>Page {page}</span><Button variant="outline" disabled={!query.isSuccess || page * 12 >= query.data.total} onClick={() => goToPage(page + 1)}>Next</Button>
      </nav>}
    </>
  );
}

export function NewProject() {
  const router = useRouter();
  const cache = useQueryClient();
  const notify = useUI((state) => state.notify);
  const permission = useProjectPermissions();
  const [error, setError] = useState<string | null>(null);
  async function create(data: ProjectInput) {
    setError(null);
    try {
      const project = await api<Project>("projects", { method: "POST", body: JSON.stringify(data) });
      await cache.invalidateQueries({ queryKey: ["projects"] });
      notify("Project created. You can now review and edit its details.");
      router.push(`/dashboard/projects/${project.id}`);
    } catch (failure) { const text = message(failure, "Project creation failed."); setError(text); notify(text, "error"); }
  }
  return <>
    <Link className="back-link" href="/dashboard/projects"><ArrowLeft size={16} /> All projects</Link>
    <PageHeader eyebrow="Workspace / Projects" title="Create a project">Capture the context for your client explanation.</PageHeader>
    {permission.loading ? <LoadingState text="Checking project permissions…" /> : !permission.canEdit ? <Card><p role="alert">{permission.error?.message || "You do not have permission to create projects in this workspace."}</p></Card> : <Card>
      {error && <p role="alert">{error}</p>}
      <ProjectForm onSubmit={create} onCancel={() => router.push("/dashboard/projects")} />
    </Card>}
  </>;
}

export function ProjectDetail({ id }: { id: string }) {
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const cache = useQueryClient();
  const notify = useUI((state) => state.notify);
  const { canEdit, canDelete } = useProjectPermissions();
  const query = useQuery({ queryKey: ["project", id], queryFn: ({ signal }) => api<Project>(`projects/${id}`, { signal }) });
  async function save(data: ProjectInput) {
    setError(null);
    try {
      await api(`projects/${id}`, { method: "PATCH", body: JSON.stringify(data) });
      await Promise.all([cache.invalidateQueries({ queryKey: ["project", id] }), cache.invalidateQueries({ queryKey: ["projects"] }), cache.invalidateQueries({ queryKey: ["project-activity", id] })]);
      setEditing(false);
      notify("Project details saved.");
    } catch (failure) { const text = message(failure, "Unable to save."); setError(text); notify(text, "error"); }
  }
  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await api(`projects/${id}`, { method: "DELETE" });
      await cache.invalidateQueries({ queryKey: ["projects"] });
      await Promise.all([
        cache.invalidateQueries({ queryKey: ["project", id], refetchType: "none" }),
        cache.invalidateQueries({ queryKey: ["project-activity", id], refetchType: "none" }),
      ]);
      notify("Project deleted.");
      router.push("/dashboard/projects");
    } catch (failure) { const text = message(failure, "Unable to delete."); setError(text); notify(text, "error"); }
    finally { setBusy(false); }
  }
  if (query.isPending) return <LoadingState text="Loading project…" />;
  if (query.error) return <>
    <PageHeader title="Project unavailable">Return to your workspace or retry loading this project.</PageHeader>
    <p role="alert">{query.error.message}</p>
    <div className="form-actions error-actions"><Button variant="outline" onClick={() => query.refetch()}>Try again</Button><Button asChild variant="ghost"><Link href="/dashboard/projects">Return to projects</Link></Button></div>
  </>;
  const project = query.data;
  return <>
    <Link className="back-link" href="/dashboard/projects"><ArrowLeft size={16} /> All projects</Link>
    <PageHeader eyebrow="Project details" title={project.name} action={!editing && canEdit && <Button variant="outline" onClick={() => { setError(null); setEditing(true); }}><Pencil size={16} /> Edit details</Button>}>
      Context and recorded activity for your client explanation.
    </PageHeader>
    {error && <p role="alert">{error}</p>}
    <Card>
      {editing && canEdit ? <ProjectForm initial={project} onSubmit={save} onCancel={() => { setError(null); setEditing(false); }} submitLabel="Save changes" /> : <>
        <span className="status-label">{reviewLabels[project.review_status]}</span>
        <dl className="project-details">
          <dt>Workflow status</dt><dd>{workflowLabels[project.workflow_status]}</dd>
          <dt>Processing status</dt><dd>{processingLabels[project.processing_status]}</dd>
          <dt>Jurisdiction</dt><dd>{project.jurisdiction || "Not recorded"}</dd>
          <dt>Legal area</dt><dd>{project.legal_area || "Not recorded"}</dd>
          <dt>Language</dt><dd>{project.language || "Not recorded"}</dd>
          <dt>Target audience</dt><dd>{project.target_audience || "Not recorded"}</dd>
          <dt>Complexity</dt><dd>{project.complexity}</dd>
          <dt>Owner ID</dt><dd>{project.owner_id}</dd>
          <dt>Description</dt><dd className="preserve-whitespace">{project.description || "No description added yet."}</dd>
          <dt>Last updated</dt><dd><time dateTime={project.updated_at}>{new Date(project.updated_at).toLocaleString()}</time></dd>
        </dl>
      </>}
    </Card>
    <div className="info-box project-info"><ShieldCheck size={22} /><div><strong>Professional review required</strong><p>AI-generated explanations require a lawyer’s review before use.</p></div></div>
    <ProjectActivity projectId={id} />
    {canDelete && <section className="danger-zone"><h2>Delete project</h2><p>This permanently removes the project and its associated records.</p>
      {deleting ? <div role="group" aria-label="Confirm project deletion"><p><strong>Delete “{project.name}”?</strong> This cannot be undone.</p><div className="form-actions">
        <Button variant="outline" disabled={busy} onClick={() => { setError(null); setDeleting(false); }}>Keep project</Button><Button variant="destructive" disabled={busy} onClick={remove}>{busy ? "Deleting…" : "Confirm deletion"}</Button>
      </div></div> : <Button variant="outline" onClick={() => { setError(null); setDeleting(true); }}><Trash2 size={16} /> Delete project</Button>}
    </section>}
  </>;
}
