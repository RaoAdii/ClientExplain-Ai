import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useSyncExternalStore, type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Projects, ProjectDetail, NewProject } from "./projects";
import { ProjectForm } from "./project-form";
import { ProjectFilters } from "./project-filters";
import { projectSchema } from "@/lib/validation";
import { useUI } from "@/stores/ui";

const session = vi.hoisted(() => ({ role: "owner", local: false }));
vi.mock("@/lib/supabase", () => ({ supabase: null }));
vi.mock("@/hooks/use-session", () => ({
  useSession: () => ({ data: { authenticated: true, local: session.local,
    account: { profile: { id: "owner-1", display_name: "Lawyer" },
      firm: { id: "firm-1", name: "Example Legal" }, role: session.role } } }),
}));
vi.mock("next/navigation", () => ({
  usePathname: () => window.location.pathname,
  useSearchParams: () => {
    const search = useSyncExternalStore(
      (listener) => { window.addEventListener("popstate", listener); return () => window.removeEventListener("popstate", listener); },
      () => window.location.search,
    );
    return new URLSearchParams(search);
  },
  useRouter: () => ({
    push: (url: string) => { window.history.pushState({}, "", url); window.dispatchEvent(new PopStateEvent("popstate")); },
    replace: (url: string) => { window.history.replaceState({}, "", url); window.dispatchEvent(new PopStateEvent("popstate")); },
  }),
}));

const project = {
  id: "project-1", name: "Civil claim", description: "Prepare a process explanation",
  jurisdiction: "England and Wales", legal_area: "Civil litigation", language: "English",
  target_audience: "First-time client", complexity: "Detailed", workflow_status: "active",
  processing_status: "idle", review_status: "requires_review", owner_id: "owner-1",
  created_at: "2026-11-18T10:00:00Z", updated_at: "2026-11-18T10:00:00Z",
};
const page = (items = [project], total = items.length, offset = 0) => ({ items, total, limit: 12, offset });
function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}
function mount(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
  return client;
}
beforeEach(() => {
  session.role = "owner";
  session.local = false;
  useUI.setState({ notice: null });
  window.history.replaceState({}, "", "/dashboard/projects");
  vi.stubGlobal("fetch", vi.fn(async (input: string) => response(input.endsWith("/activity") ? [] : input.includes("projects?") ? page() : project)));
});

describe("Project fields", () => {
  it("submits all editable context fields and workflow status with normalized input", async () => {
    const submit = vi.fn().mockResolvedValue(undefined);
    render(<ProjectForm onSubmit={submit} />);
    for (const [label, value] of [
      ["Project name", " Civil claim "], ["Jurisdiction", " England and Wales "],
      ["Project description", " Client briefing "], ["Legal area", " Civil litigation "],
      ["Language", " English "], ["Target audience", " First-time client "], ["Complexity", " Detailed "],
    ]) {
      await userEvent.clear(screen.getByLabelText(label));
      await userEvent.type(screen.getByLabelText(label), value);
    }
    await userEvent.selectOptions(screen.getByLabelText("Workflow status"), "active");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    await waitFor(() => expect(submit).toHaveBeenCalledWith({ name: "Civil claim", jurisdiction: "England and Wales",
      description: "Client briefing", legal_area: "Civil litigation", language: "English",
      target_audience: "First-time client", complexity: "Detailed", workflow_status: "active" }, expect.anything()));
  });
  it("rejects whitespace-only name and complexity, oversized fields and invalid workflow status", () => {
    const input = { name: "Claim", jurisdiction: "", description: "", legal_area: "", language: "", target_audience: "", complexity: "unspecified", workflow_status: "draft" };
    for (const invalid of [ { name: "   " }, { complexity: "   " }, { name: "x".repeat(201) },
      { description: "x".repeat(10001) }, { jurisdiction: "x".repeat(121) }, { legal_area: "x".repeat(121) },
      { language: "x".repeat(61) }, { target_audience: "x".repeat(121) }, { complexity: "x".repeat(41) }, { workflow_status: "unknown" },
    ]) expect(projectSchema.safeParse({ ...input, ...invalid }).success).toBe(false);
  });
  it("keeps an invalid form open with accessible errors", async () => {
    const submit = vi.fn();
    render(<ProjectForm onSubmit={submit} />);
    await userEvent.type(screen.getByLabelText("Project name"), "   ");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/project name/i);
    expect(submit).not.toHaveBeenCalled();
  });
});

describe("Project library", () => {
  it("links to the dedicated creation route and displays server statuses and real totals", async () => {
    vi.mocked(fetch).mockResolvedValue(response(page([project], 13)));
    mount(<Projects />);
    expect(screen.getByRole("link", { name: "New project" })).toHaveAttribute("href", "/dashboard/projects/new");
    expect(await screen.findByText("Civil claim")).toBeVisible();
    expect(within(screen.getByRole("link", { name: /Civil claim/ })).getByText("Active")).toBeVisible();
    expect(screen.getByText("Processing: Idle")).toBeVisible();
    expect(screen.getByText("13 projects")).toBeVisible();
    expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();
  });
  it("restores shareable filters and pagination from the URL", async () => {
    window.history.replaceState({}, "", "/dashboard/projects?search=Civil%20%26%20claims&status=active&review_status=in_review&page=2");
    mount(<Projects />);
    expect(await screen.findByRole("searchbox", { name: "Search projects" })).toHaveValue("Civil & claims");
    expect(screen.getByLabelText("Workflow status filter")).toHaveValue("active");
    expect(screen.getByLabelText("Review status filter")).toHaveValue("in_review");
    await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/backend/projects?limit=12&offset=12&search=Civil+%26+claims&status=active&review_status=in_review", expect.anything()));
  });
  it("debounces search and resets pagination while preserving other filters", async () => {
    window.history.replaceState({}, "", "/dashboard/projects?status=active&page=3");
    mount(<Projects />);
    await screen.findByText("Civil claim");
    vi.mocked(fetch).mockClear();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Civil" } });
    expect(fetch).not.toHaveBeenCalled();
    expect(window.location.search).toContain("page=3");
    await waitFor(() => expect(new URLSearchParams(window.location.search).get("search")).toBe("Civil"));
    expect(new URLSearchParams(window.location.search).get("status")).toBe("active");
    expect(new URLSearchParams(window.location.search).has("page")).toBe(false);
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    expect(fetch).toHaveBeenCalledWith("/api/backend/projects?limit=12&offset=0&search=Civil&status=active", expect.anything());
  });
  it("applies status filters immediately and restores search on browser navigation", async () => {
    mount(<Projects />);
    await screen.findByText("Civil claim");
    await userEvent.selectOptions(screen.getByLabelText("Workflow status filter"), "archived");
    expect(new URLSearchParams(window.location.search).get("status")).toBe("archived");
    act(() => { window.history.pushState({}, "", "/dashboard/projects?search=Returned&review_status=approved"); window.dispatchEvent(new PopStateEvent("popstate")); });
    expect(screen.getByRole("searchbox")).toHaveValue("Returned");
    expect(screen.getByLabelText("Review status filter")).toHaveValue("approved");
  });
  it("keeps the search input focused and preserves its draft after debounce commits", async () => {
    mount(<Projects />);
    await screen.findByText("Civil claim");
    const input = screen.getByRole("searchbox");
    await userEvent.type(input, " Civil ");
    await waitFor(() => expect(new URLSearchParams(window.location.search).get("search")).toBe("Civil"));
    expect(screen.getByRole("searchbox")).toBe(input);
    expect(input).toHaveFocus();
    expect(input).toHaveValue(" Civil ");
    await userEvent.type(input, "claims ");
    await waitFor(() => expect(new URLSearchParams(window.location.search).get("search")).toBe("Civil claims"));
    expect(input).toHaveFocus();
    expect(input).toHaveValue(" Civil claims ");
  });
  it("preserves newer typing when a submitted search arrives and synchronizes external search changes", async () => {
    const onChange = vi.fn();
    const { rerender } = render(<ProjectFilters search="" status="" reviewStatus="" onChange={onChange} />);
    const input = screen.getByRole("searchbox");
    await userEvent.type(input, "Civil");
    await waitFor(() => expect(onChange).toHaveBeenCalledWith({ search: "Civil" }));
    fireEvent.change(input, { target: { value: "Civil claims " } });
    rerender(<ProjectFilters search="Civil" status="" reviewStatus="" onChange={onChange} />);
    expect(input).toHaveFocus();
    expect(input).toHaveValue("Civil claims ");
    rerender(<ProjectFilters search="Returned" status="" reviewStatus="" onChange={onChange} />);
    expect(screen.getByRole("searchbox")).toBe(input);
    expect(input).toHaveFocus();
    expect(input).toHaveValue("Returned");
  });
  it("shows pending, empty, filtered empty and retryable error states without invented data", async () => {
    vi.mocked(fetch).mockImplementationOnce(() => new Promise(() => {}));
    const client = mount(<Projects />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading projects");
    act(() => client.setQueryData(["projects", "", "", "", 1], page([])));
    expect(await screen.findByText("Your first explanation starts here")).toBeVisible();
    expect(screen.queryByText("Civil claim")).not.toBeInTheDocument();
  });
  it("distinguishes a filtered empty result from a new workspace", async () => {
    window.history.replaceState({}, "", "/dashboard/projects?search=Missing");
    vi.mocked(fetch).mockResolvedValue(response(page([])));
    mount(<Projects />);
    expect(await screen.findByText("No matching projects")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(window.location.search).toBe("");
  });
  it("retries failed reads and does not show a fabricated total", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(response({ error: { message: "Database unavailable" } }, 503));
    mount(<Projects />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Database unavailable");
    expect(screen.queryByText("0 projects")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Civil claim")).toBeVisible();
  });
});

describe("Project creation and permissions", () => {
  it("creates on the dedicated page, invalidates the library and notifies before navigating", async () => {
    mount(<NewProject />);
    await userEvent.type(screen.getByLabelText("Project name"), "Civil claim");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    await waitFor(() => expect(window.location.pathname).toBe("/dashboard/projects/project-1"));
    expect(fetch).toHaveBeenCalledWith("/api/backend/projects", expect.objectContaining({ method: "POST", body: JSON.stringify({ name: "Civil claim", description: "", jurisdiction: "", legal_area: "", language: "", target_audience: "", complexity: "unspecified", workflow_status: "draft" }) }));
    expect(useUI.getState().notice?.message).toMatch(/created/i);
  });
  it("keeps submitted creation values and reports stale permissions", async () => {
    vi.mocked(fetch).mockResolvedValue(response({ error: { message: "Your role does not permit this operation." } }, 403));
    mount(<NewProject />);
    await userEvent.type(screen.getByLabelText("Project name"), "Civil claim");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/permission/i);
    expect(screen.getByLabelText("Project name")).toHaveValue("Civil claim");
    expect(useUI.getState().notice?.kind).toBe("error");
  });
  it("hides creation from reviewers, including direct navigation", async () => {
    session.role = "reviewer";
    mount(<Projects />);
    await screen.findByText("Civil claim");
    expect(screen.queryByRole("link", { name: "New project" })).not.toBeInTheDocument();
  });
  it("rejects the create form for reviewers", () => {
    session.role = "reviewer";
    mount(<NewProject />);
    expect(screen.queryByLabelText("Project name")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/permission/i);
  });
});

describe("Project details and activity", () => {
  it("renders all real context and server activity without synthetic counts", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => response(String(input).endsWith("/activity") ? [{ id: "event-1", action: "project.created", actor_id: "owner-1", resource_id: project.id, created_at: project.created_at }] : project));
    mount(<ProjectDetail id="project-1" />);
    expect(await screen.findByText("Civil litigation")).toBeVisible();
    expect(screen.getByText("First-time client")).toBeVisible();
    expect(screen.getByText("English")).toBeVisible();
    expect(screen.getByText("Detailed")).toBeVisible();
    expect(screen.getByText("owner-1")).toBeVisible();
    expect(await screen.findByText("Project created")).toBeVisible();
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
  });
  it("shows an honest empty activity feed", async () => {
    mount(<ProjectDetail id="project-1" />);
    expect(await screen.findByText("No activity recorded yet.")).toBeVisible();
  });
  it("isolates activity loading and failures from the project", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => String(input).endsWith("/activity") ? response({ error: { message: "Activity unavailable" } }, 503) : response(project));
    mount(<ProjectDetail id="project-1" />);
    expect(await screen.findByRole("heading", { name: "Civil claim" })).toBeVisible();
    expect(await screen.findByRole("alert")).toHaveTextContent("Activity unavailable");
    expect(screen.getByRole("button", { name: "Retry activity" })).toBeEnabled();
  });
  it.each(["owner", "admin", "lawyer", "reviewer"])("shows only authorized actions to %s", async (role) => {
    session.role = role;
    mount(<ProjectDetail id="project-1" />);
    await screen.findByRole("heading", { name: "Civil claim" });
    expect(!!screen.queryByRole("button", { name: "Edit details" })).toBe(role !== "reviewer");
    expect(!!screen.queryByRole("button", { name: "Delete project" })).toBe(["owner", "admin"].includes(role));
  });
  it("saves all context, refreshes activity and reports success", async () => {
    mount(<ProjectDetail id="project-1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Edit details" }));
    expect(screen.getByLabelText("Legal area")).toHaveValue("Civil litigation");
    await userEvent.clear(screen.getByLabelText("Target audience"));
    await userEvent.type(screen.getByLabelText("Target audience"), "Business client");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(useUI.getState().notice?.message).toMatch(/saved/i));
    expect(fetch).toHaveBeenCalledWith("/api/backend/projects/project-1", expect.objectContaining({ method: "PATCH", body: expect.stringContaining('"target_audience":"Business client"') }));
    expect(screen.queryByLabelText("Target audience")).not.toBeInTheDocument();
  });
  it("requires confirmation, deletes, and reports success", async () => {
    mount(<ProjectDetail id="project-1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete project" }));
    expect(fetch).not.toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ method: "DELETE" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm deletion" }));
    await waitFor(() => expect(window.location.pathname).toBe("/dashboard/projects"));
    expect(useUI.getState().notice?.message).toMatch(/deleted/i);
  });
  it("does not refetch a project after deleting it", async () => {
    vi.mocked(fetch).mockImplementation(async (input, options) => {
      if (options?.method === "DELETE") return new Response(null, { status: 204 });
      return response(String(input).endsWith("/activity") ? [] : project);
    });
    mount(<ProjectDetail id="project-1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete project" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm deletion" }));
    await waitFor(() => expect(window.location.pathname).toBe("/dashboard/projects"));
    await waitFor(() => {
      const projectReads = vi.mocked(fetch).mock.calls.filter(([input, options]) =>
        String(input).endsWith("/projects/project-1") && (!options?.method || options.method === "GET"));
      expect(projectReads).toHaveLength(1);
    });
  });
  it.each([403, 404])("reports stale %s mutation errors while preserving the editor", async (status) => {
    vi.mocked(fetch).mockImplementation(async (input, options) => response(options?.method === "PATCH" ? { error: { message: "Request failed" } } : String(input).endsWith("/activity") ? [] : project, options?.method === "PATCH" ? status : 200));
    mount(<ProjectDetail id="project-1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Edit details" }));
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(status === 403 ? /permission/i : /not found|no longer available/i);
    expect(screen.getByLabelText("Project name")).toHaveValue("Civil claim");
    expect(useUI.getState().notice?.kind).toBe("error");
  });
});
