import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectWorkspace } from "./project-workspace";
import { uploadDocument } from "@/services/uploads";

const session = vi.hoisted(() => ({ role: "owner" }));
vi.mock("@/lib/supabase", () => ({ supabase: null }));
vi.mock("@/hooks/use-session", () => ({ useSession: () => ({ data: { authenticated: true, local: false, account: { role: session.role } } }) }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
const project = { id: "p1", name: "Claim", jurisdiction: "England and Wales", description: "", legal_area: "Civil", language: "English", target_audience: "Client", complexity: "standard", workflow_status: "draft", processing_status: "idle", review_status: "requires_review", owner_id: "u1", created_at: "2026-11-18", updated_at: "2026-11-18" };
const document = { id: "d1", project_id: "p1", filename: "brief.txt", media_type: "text/plain", byte_size: 20, sha256: "abc", status: "completed", created_at: "2026-11-18", updated_at: "2026-11-18" };
const job = { id: "j1", project_id: "p1", kind: "analysis", status: "queued", progress: 0, current_stage: "queued", retry_count: 0, error_code: null, error_message: null as string | null };
const stage = { id: "s1", project_id: "p1", position: 1, title: "Prepare claim", explanation: "Review the evidence.", responsible_party: "Lawyer", required_documents: ["Claim form"], estimated_duration: "Varies", source_backed: true, general_explanation: false, limitations: ["Check deadlines"], verification_status: "unverified" };
const citation = { id: "c1", stage_id: "s1", claim_text: "Review evidence", excerpt: "The claim must be reviewed.", source_type: "user_document", verification_status: "unverified", validation_status: "supported", source_filename: "brief.txt", page_number: 3, heading: "Filing", source_url: null };
function response(data: unknown, status = 200) { return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } }); }
let documents = [document];
let detail = { ...document, page_count: 1, parsing_error: null as string | null, ocr_required: false };
let currentJob = { ...job };
let process = { process_name: null as string | null, summary: null as string | null, stages: [] as typeof stage[], missing_information: [] as string[], limitations: [] as string[], review_required: true };
class UploadXHR {
  static latest: UploadXHR;
  upload = { onprogress: null as ((event: ProgressEvent) => void) | null };
  status = 202;
  responseText = "";
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  ontimeout: (() => void) | null = null;
  open = vi.fn(); setRequestHeader = vi.fn(); send = vi.fn(); abort = vi.fn();
  constructor() { UploadXHR.latest = this; }
  finish(data: unknown, status = 202) { this.status = status; this.responseText = JSON.stringify(data); this.onload?.(); }
}
function mount() { const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } }); const view = render(<QueryClientProvider client={client}><ProjectWorkspace id="p1" /></QueryClientProvider>); return { client, ...view }; }
async function fillAnalysis() { await userEvent.type(await screen.findByLabelText("Process text"), "Explain filing a civil claim."); }
beforeEach(() => {
  session.role = "owner"; sessionStorage.clear(); documents = [document]; detail = { ...document, page_count: 1, parsing_error: null, ocr_required: false }; currentJob = { ...job }; process = { process_name: null, summary: null, stages: [], missing_information: [], limitations: [], review_required: true };
  vi.stubGlobal("XMLHttpRequest", UploadXHR);
  vi.stubGlobal("fetch", vi.fn(async (input: string, options?: RequestInit) => {
    if (options?.method === "DELETE") return new Response(null, { status: 204 });
    if (input.endsWith("/documents")) return response(documents);
    if (input.includes("/documents/")) return response(detail);
    if (input.endsWith("/analyze")) return response(currentJob, 202);
    if (input.includes("/jobs/")) return response(currentJob);
    if (input.endsWith("/stages")) return response(process);
    if (input.endsWith("/citations")) return response([citation]);
    if (input.endsWith("/activity")) return response([]);
    return response(project);
  }));
});
describe("Document and analysis workspace", () => {
  it("keeps one heading and uses ordinary section links", async () => {
    mount(); await screen.findByLabelText("Process text");
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Documents" })).toHaveAttribute("href", "#documents");
    expect(screen.queryByRole("button", { name: /diagram|image/i })).not.toBeInTheDocument();
  });
  it("rejects unsupported, empty and oversized files before sending", async () => {
    mount(); const input = await screen.findByLabelText("Document file");
    for (const file of [new File(["x"], "image.png", { type: "image/png" }), new File([], "empty.txt", { type: "text/plain" }), new File([new Uint8Array(25 * 1024 * 1024 + 1)], "large.txt", { type: "text/plain" })]) {
      fireEvent.change(input, { target: { files: [file] } });
      expect(screen.getByRole("alert")).toHaveTextContent(/PDF|empty|25 MB/i);
      expect(screen.getByRole("button", { name: "Upload document" })).toBeDisabled();
    }
  });
  it("shows upload percentages only from XHR progress and tracks the accepted parse job", async () => {
    mount(); fireEvent.change(await screen.findByLabelText("Document file"), { target: { files: [new File(["legal text"], "new.txt", { type: "text/plain" })] } });
    await userEvent.click(screen.getByRole("button", { name: "Upload document" }));
    expect(screen.getByRole("progressbar", { name: "Upload progress" })).not.toHaveAttribute("value");
    act(() => UploadXHR.latest.upload.onprogress?.({ lengthComputable: true, loaded: 3, total: 10 } as ProgressEvent));
    expect(screen.getByRole("progressbar", { name: "Upload progress" })).toHaveAttribute("value", "30");
    act(() => UploadXHR.latest.finish({ document, job: { ...job, kind: "parse" } }));
    await waitFor(() => expect(screen.getByText(/Parse job: Queued/)).toBeVisible());
  });
  it.each([[409, "This document is already uploaded."], [415, "The file is not a DOCX document."]])("retains actionable upload errors (%s)", async (status, message) => {
    mount(); fireEvent.change(await screen.findByLabelText("Document file"), { target: { files: [new File(["x"], "new.txt", { type: "text/plain" })] } });
    await userEvent.click(screen.getByRole("button", { name: "Upload document" }));
    act(() => UploadXHR.latest.finish({ error: { message } }, status));
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.getByRole("button", { name: "Upload document" })).toBeEnabled();
  });
  it("disables processing, corrupt and OCR documents and displays the parser error", async () => {
    documents = [{ ...document, status: "running" }, { ...document, id: "d2", filename: "corrupt.pdf", status: "failed" }, { ...document, id: "d3", filename: "scan.pdf", status: "ocr_required" }];
    detail = { ...detail, status: "failed", parsing_error: "Corrupt document; upload a valid copy." };
    mount(); expect(await screen.findByLabelText("Select brief.txt")).toBeDisabled();
    expect(screen.getByLabelText("Select corrupt.pdf")).toBeDisabled(); expect(screen.getByLabelText("Select scan.pdf")).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Details for corrupt.pdf" }));
    expect(await screen.findByText("Corrupt document; upload a valid copy.")).toBeVisible();
    expect(screen.getByText(/OCR required/)).toBeVisible();
  });
  it("confirms document deletion and refreshes invalidated results", async () => {
    mount(); await userEvent.click(await screen.findByRole("button", { name: "Delete brief.txt" }));
    expect(fetch).not.toHaveBeenCalledWith("/api/backend/documents/d1", expect.objectContaining({ method: "DELETE" }));
    await userEvent.click(screen.getByRole("button", { name: "Keep document" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete brief.txt" }));
    documents = []; await userEvent.click(screen.getByRole("button", { name: "Confirm document deletion" }));
    await waitFor(() => expect(screen.queryByLabelText("Select brief.txt")).not.toBeInTheDocument());
    expect(fetch).toHaveBeenCalledWith("/api/backend/documents/d1", expect.objectContaining({ method: "DELETE" }));
  });
  it("requires process text, jurisdiction and disclosure acknowledgement for selected documents", async () => {
    mount(); const submit = await screen.findByRole("button", { name: "Analyze process" }); expect(submit).toBeDisabled();
    await fillAnalysis(); await userEvent.clear(screen.getByLabelText("Analysis jurisdiction")); expect(submit).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Analysis jurisdiction"), "England and Wales");
    await userEvent.click(screen.getByLabelText("Select brief.txt")); expect(submit).toBeDisabled();
    expect(screen.getByText(/sent to the external AI provider/)).toBeVisible();
    await userEvent.click(screen.getByLabelText(/I authorize external processing/)); await userEvent.click(submit);
    await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/backend/projects/p1/analyze", expect.objectContaining({ method: "POST", body: expect.stringContaining('"selected_document_ids":["d1"]') })));
  });
  it("retains form values when the provider is unavailable and allows retry", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => String(input).endsWith("/analyze") ? response({ error: { message: "AI processing is disabled or unavailable." } }, 503) : response(String(input).endsWith("/documents") ? documents : String(input).endsWith("/stages") ? process : String(input).endsWith("/citations") || String(input).endsWith("/activity") ? [] : project));
    mount(); await fillAnalysis(); await userEvent.click(screen.getByRole("button", { name: "Analyze process" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("AI processing is disabled or unavailable.");
    expect(screen.getByLabelText("Process text")).toHaveValue("Explain filing a civil claim."); expect(screen.getByRole("button", { name: "Analyze process" })).toBeEnabled();
  });
  it.each(["queued", "running", "failed", "completed", "cancelled"])("renders actual %s job state", async (status) => {
    currentJob = { ...job, status, progress: status === "completed" ? 100 : 37, current_stage: "retrieving", error_message: status === "failed" ? "Provider timed out. Retry analysis." : null };
    mount(); await fillAnalysis(); await userEvent.click(screen.getByRole("button", { name: "Analyze process" }));
    expect(await screen.findByText(`Analysis job: ${status[0].toUpperCase()}${status.slice(1)}`)).toBeVisible();
    expect(screen.getByRole("progressbar", { name: "Analysis job progress" })).toHaveAttribute("value", String(currentJob.progress));
    if (status === "failed") expect(screen.getByText("Provider timed out. Retry analysis.")).toBeVisible();
  });
  it("renders stored stages in order with review, provenance, excerpt and page details", async () => {
    process = { process_name: "Civil claim process", summary: "Stored summary only.", stages: [{ ...stage, id: "s2", position: 2, title: "File claim", source_backed: false, general_explanation: true }, stage], missing_information: ["Court not supplied"], limitations: ["Jurisdiction-specific advice needed"], review_required: true };
    mount(); expect(await screen.findByText("Stored summary only.")).toBeVisible();
    const stages = screen.getByRole("list", { name: "Process stages" });
    expect(within(stages).getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual(["1. Prepare claim", "2. File claim"]);
    expect(screen.getAllByText(/Professional review required/).length).toBeGreaterThan(0);
    expect(screen.getByText("User document")).toBeVisible(); expect(screen.getAllByText("Unverified").length).toBeGreaterThan(0);
    expect(screen.getByText("The claim must be reviewed.")).toBeVisible(); expect(screen.getByText(/Page 3/)).toBeVisible();
    expect(screen.getByText("Court not supplied")).toBeVisible(); expect(screen.getByText("General explanation")).toBeVisible();
  });
  it("hides editing actions from reviewers", async () => {
    session.role = "reviewer"; mount(); await screen.findByText("brief.txt");
    expect(screen.queryByLabelText("Document file")).not.toBeInTheDocument(); expect(screen.queryByRole("button", { name: "Analyze process" })).not.toBeInTheDocument();
  });
  it("polls active jobs and stops after the terminal response and unmount", async () => {
    const { client, unmount } = mount(); await fillAnalysis(); await userEvent.click(screen.getByRole("button", { name: "Analyze process" }));
    await screen.findByText("Analysis job: Queued"); currentJob = { ...job, status: "completed", progress: 100 };
    await waitFor(() => expect(screen.getByText("Analysis job: Completed")).toBeVisible(), { timeout: 4000 });
    vi.mocked(fetch).mockClear(); await new Promise((resolve) => setTimeout(resolve, 1700));
    expect(vi.mocked(fetch).mock.calls.filter(([input]) => String(input).includes("/jobs/"))).toHaveLength(0);
    unmount(); client.clear();
  });
});
describe("XHR upload service", () => {
  it("posts one multipart file to the BFF without a JSON content type", async () => {
    const file = new File(["text"], "brief.txt", { type: "text/plain" });
    const pending = uploadDocument("p1", file, vi.fn()); await waitFor(() => expect(UploadXHR.latest.send).toHaveBeenCalled());
    expect(UploadXHR.latest.open).toHaveBeenCalledWith("POST", "/api/backend/projects/p1/documents");
    const body = UploadXHR.latest.send.mock.calls[0][0] as FormData; expect(body.get("file")).toBe(file); expect([...body.keys()]).toEqual(["file"]);
    expect(UploadXHR.latest.setRequestHeader).not.toHaveBeenCalledWith("Content-Type", expect.anything());
    UploadXHR.latest.finish({ document, job }); await expect(pending).resolves.toMatchObject({ document });
  });
});


