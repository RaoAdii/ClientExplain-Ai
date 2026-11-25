import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import { WorkflowEditor } from "./workflow-editor";

vi.mock("@/lib/supabase", () => ({ supabase: null }));
beforeEach(() => {
  // jsdom has no layout observer; browser tests verify actual diagram layout.
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
});

test("adds and edits a manual stage, saves it, and restores persisted content", async () => {
  let saved = { version: 0, stages: [], edges: [], review_status: "requires_review" };
  vi.stubGlobal("fetch", async (_url: string, options?: RequestInit) => {
    if (options?.method === "PATCH") saved = { ...JSON.parse(options.body as string), version: 1, review_status: "requires_review" };
    return new Response(JSON.stringify(saved), { status: 200 });
  });
  const view = render(<WorkflowEditor projectId="p1" canEdit onSaved={() => {}} />);
  fireEvent.click(await screen.findByRole("button", { name: "Add stage" }));
  fireEvent.change(screen.getByLabelText("Stage title"), { target: { value: "Review the supplied record" } });
  fireEvent.change(screen.getByLabelText("Stage explanation"), { target: { value: "Ask your lawyer to review the record." } });
  fireEvent.click(screen.getByRole("button", { name: "Save workflow" }));
  await screen.findByText("Workflow saved.");
  view.unmount();
  render(<WorkflowEditor projectId="p1" canEdit onSaved={() => {}} />);
  await waitFor(() => expect(screen.getByRole("button", { name: /1. Review the supplied record/ })).toBeInTheDocument());
  fireEvent.click(screen.getByRole("button", { name: /1. Review the supplied record/ }));
  expect(screen.getByLabelText("Stage explanation")).toHaveValue("Ask your lawyer to review the record.");
});

test("shows load failure and allows retry without exposing edit actions", async () => {
  vi.stubGlobal("fetch", async () => new Response('{"error":{"message":"Unavailable"}}', { status: 503 }));
  render(<WorkflowEditor projectId="p1" canEdit={false} onSaved={() => {}} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Unavailable");
  expect(screen.queryByRole("button", { name: "Add stage" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reload workflow" })).toBeInTheDocument();
});
