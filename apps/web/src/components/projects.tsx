"use client";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Plus,
  FileText,
  MapPin,
  ArrowLeft,
  Trash2,
  Pencil,
  ShieldCheck,
} from "lucide-react";
import { api } from "@/services/api";
import type { Project } from "@/types/project";
import type { ProjectInput } from "@/lib/validation";
import { useUI } from "@/stores/ui";
import { PageHeader, Card, LoadingState, EmptyState } from "./common";
import { Button } from "./ui/button";
import { ProjectForm } from "./project-form";

export function Projects({ overview = false }: { overview?: boolean }) {
  const [creating, setCreating] = useState(false);
  const [page, setPage] = useState(0);
  const queryClient = useQueryClient();
  const notify = useUI((s) => s.notify);
  const query = useQuery({
    queryKey: ["projects", page],
    queryFn: () => api<Project[]>(`projects?limit=12&offset=${page * 12}`),
  });
  async function create(data: ProjectInput) {
    try {
      await api<Project>("projects", {
        method: "POST",
        body: JSON.stringify(data),
      });
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      setCreating(false);
      setPage(0);
      notify("Project created. You can now review and edit its details.");
    } catch (error) {
      notify(
        error instanceof Error ? error.message : "Project creation failed.",
        "error",
      );
    }
  }
  return (
    <>
      <PageHeader
        eyebrow={
          overview ? "Your legal process workspace" : "Workspace / Projects"
        }
        title={overview ? "A clearer starting point." : "Projects"}
        action={
          !creating && (
            <Button onClick={() => setCreating(true)}>
              <Plus size={17} /> New project
            </Button>
          )
        }
      >
        {overview
          ? "Bring the context for your next client explanation into one place."
          : "Organize the legal processes you want to explain."}
      </PageHeader>
      {overview && (
        <div className="workspace-callout">
          <ShieldCheck size={24} />
          <div>
            <strong>Built around professional review</strong>
            <p>
              Start with project details today. Document analysis, visual
              generation, and exports are planned for future releases.
            </p>
          </div>
          <span className="small-tag">Foundation release</span>
        </div>
      )}
      {creating && (
        <Card className="create-card">
          <div className="section-title">
            <h2>Create a project</h2>
            <span className="muted">Start with the context</span>
          </div>
          <ProjectForm onSubmit={create} onCancel={() => setCreating(false)} />
        </Card>
      )}
      <div className="section-title">
        <h2>{overview ? "Your projects" : "Project library"}</h2>
        <span className="muted">Saved in your workspace</span>
      </div>
      {query.isPending ? (
        <LoadingState text="Loading projects…" />
      ) : query.error ? (
        <Card>
          <p role="alert">{query.error.message}</p>
          <Button variant="outline" onClick={() => query.refetch()}>
            Try again
          </Button>
        </Card>
      ) : query.data.length === 0 ? (
        <Card>
          <EmptyState
            title={
              page === 0
                ? "Your first explanation starts here"
                : "No more projects"
            }
            action={
              page === 0 && !creating ? (
                <Button variant="outline" onClick={() => setCreating(true)}>
                  <Plus size={16} /> Create your first project
                </Button>
              ) : undefined
            }
          >
            {page === 0
              ? "Create a project to capture the process, jurisdiction, and context. Your saved projects will appear here."
              : "Return to the previous page to view your projects."}
          </EmptyState>
        </Card>
      ) : (
        <div className="project-grid">
          {query.data.map((project) => (
            <Link
              href={`/dashboard/projects/${project.id}`}
              key={project.id}
              className="project-card"
            >
              <div className="project-card-top">
                <span className="project-icon">
                  <FileText size={21} />
                </span>
                <ArrowRight size={18} />
              </div>
              <span className="status-label">Requires professional review</span>
              <h3>{project.name}</h3>
              <p>
                {project.description ||
                  "No description added yet. Open this project to add context."}
              </p>
              <div className="project-card-bottom">
                <span>
                  <MapPin size={14} />
                  {project.jurisdiction || "Jurisdiction not recorded"}
                </span>
                <time dateTime={project.updated_at}>
                  {new Date(project.updated_at).toLocaleDateString("en", {
                    month: "short",
                    day: "numeric",
                  })}
                </time>
              </div>
            </Link>
          ))}
        </div>
      )}
      {(page > 0 || query.data?.length === 12) && (
        <div className="pagination">
          <Button
            variant="outline"
            disabled={page === 0}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <span>Page {page + 1}</span>
          <Button
            variant="outline"
            disabled={query.data?.length !== 12}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
      {overview && (
        <div className="next-release">
          <span className="eyebrow">What comes next</span>
          <p>
            From source material to editable visual workflows. Generation and
            review tools will be added in later releases.
          </p>
          <Link href="/#workflow" className="text-link">
            See the planned workflow <ArrowRight size={16} />
          </Link>
        </div>
      )}
    </>
  );
}

export function ProjectDetail({ id }: { id: string }) {
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [busy, setBusy] = useState(false);
  const router = useRouter();
  const cache = useQueryClient();
  const notify = useUI((s) => s.notify);
  const query = useQuery({
    queryKey: ["project", id],
    queryFn: () => api<Project>(`projects/${id}`),
  });
  async function save(data: ProjectInput) {
    try {
      await api(`projects/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      });
      await cache.invalidateQueries({ queryKey: ["project", id] });
      await cache.invalidateQueries({ queryKey: ["projects"] });
      setEditing(false);
      notify("Project details saved.");
    } catch (error) {
      notify(
        error instanceof Error ? error.message : "Unable to save.",
        "error",
      );
    }
  }
  async function remove() {
    setBusy(true);
    try {
      await api(`projects/${id}`, { method: "DELETE" });
      await cache.invalidateQueries({ queryKey: ["projects"] });
      router.push("/dashboard/projects");
      notify("Project deleted.");
    } catch (error) {
      notify(
        error instanceof Error ? error.message : "Unable to delete.",
        "error",
      );
    } finally {
      setBusy(false);
    }
  }
  if (query.isPending) return <LoadingState text="Loading project…" />;
  if (query.error)
    return (
      <>
        <PageHeader title="Project unavailable">
          {query.error.message}
        </PageHeader>
        <div className="form-actions error-actions">
          <Button variant="outline" onClick={() => query.refetch()}>
            Try again
          </Button>
          <Button asChild variant="ghost">
            <Link href="/dashboard/projects">Return to projects</Link>
          </Button>
        </div>
      </>
    );
  const project = query.data;
  return (
    <>
      <Link className="back-link" href="/dashboard/projects">
        <ArrowLeft size={16} /> All projects
      </Link>
      <PageHeader
        eyebrow="Project details"
        title={project.name}
        action={
          !editing && (
            <Button variant="outline" onClick={() => setEditing(true)}>
              <Pencil size={16} /> Edit details
            </Button>
          )
        }
      >
        Capture the context for a future client explanation.
      </PageHeader>
      <Card>
        {editing ? (
          <ProjectForm
            initial={project}
            onSubmit={save}
            onCancel={() => setEditing(false)}
            submitLabel="Save changes"
          />
        ) : (
          <>
            <span className="status-label">Requires professional review</span>
            <dl className="project-details">
              <dt>Jurisdiction</dt>
              <dd>{project.jurisdiction || "Not recorded"}</dd>
              <dt>Description</dt>
              <dd className="preserve-whitespace">
                {project.description || "No description added yet."}
              </dd>
              <dt>Last updated</dt>
              <dd>{new Date(project.updated_at).toLocaleString()}</dd>
            </dl>
          </>
        )}
      </Card>
      <div className="info-box project-info">
        <ShieldCheck size={22} />
        <div>
          <strong>Your project is ready for the next stage</strong>
          <p>
            Document processing, AI analysis, editable diagrams, and exports are
            not available in this release. No legal explanation has been
            generated.
          </p>
        </div>
      </div>
      <section className="danger-zone">
        <h2>Delete project</h2>
        <p>This permanently removes the project and its associated records.</p>
        {deleting ? (
          <div role="group" aria-label="Confirm project deletion">
            <p>
              <strong>Delete “{project.name}”?</strong> This cannot be undone.
            </p>
            <div className="form-actions">
              <Button
                variant="outline"
                disabled={busy}
                onClick={() => setDeleting(false)}
              >
                Keep project
              </Button>
              <Button variant="destructive" disabled={busy} onClick={remove}>
                {busy ? "Deleting…" : "Confirm deletion"}
              </Button>
            </div>
          </div>
        ) : (
          <Button variant="outline" onClick={() => setDeleting(true)}>
            <Trash2 size={16} /> Delete project
          </Button>
        )}
      </section>
    </>
  );
}
