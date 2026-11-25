import { expect, test } from "vitest";
import type { WorkflowGraph } from "@/types/workflow";
import {
  buildWorkflowDiagram,
  createWorkflowPdf,
  workflowFilename,
} from "./workflow-export";

const graph: WorkflowGraph = {
  version: 3,
  review_status: "requires_review",
  stages: [
    {
      id: "stage-1",
      title: "Submit <fictional> request",
      explanation: "Send the made-up form.",
      responsible_party: "Participant",
      required_documents: ["Request form"],
      limitations: ["Fictional only"],
      position: { x: -40, y: 0 },
      actions: ["Submit"],
      preconditions: [],
      outcomes: ["Acknowledgement"],
      status: "pending",
    },
    {
      id: "stage-2",
      title: "Review & respond",
      explanation: "Check the fictional request.",
      responsible_party: "Coordinator",
      required_documents: [],
      limitations: [],
      position: { x: 360, y: 180 },
      actions: [],
      preconditions: [],
      outcomes: [],
      status: "in_progress",
    },
  ],
  edges: [{ source: "stage-1", target: "stage-2" }],
};

test("builds a locally labeled SVG and escapes project and stage text", () => {
  const diagram = buildWorkflowDiagram(graph, "Example <project>");

  expect(diagram.svg).toContain("Generated locally from saved workflow data");
  expect(diagram.svg).toContain("Not AI-generated or legally verified.");
  expect(diagram.svg).toContain("Example &lt;project&gt;");
  expect(diagram.svg).toContain("Submit &lt;fictional&gt; request");
  expect(diagram.svg).toContain("marker-end");
  expect(diagram.svg).not.toContain("<fictional>");
  expect(diagram.width).toBeGreaterThan(0);
  expect(diagram.height).toBeGreaterThan(0);
});

test("uses a safe deterministic filename", () => {
  expect(workflowFilename("Fictional Venue / Demo!", "pdf")).toBe(
    "clientexplain-fictional-venue-demo-workflow.pdf",
  );
  expect(workflowFilename("!!!", "png")).toBe(
    "clientexplain-workflow-workflow.png",
  );
});

test("exports printable Latin-1 text and rejects WinAnsi control characters", async () => {
  const latin1Graph = {
    ...graph,
    stages: [{ ...graph.stages[0], title: "R\u00e9sum\u00e9" }],
  };
  const pdf = await createWorkflowPdf(latin1Graph, "Fici\u00f3n d\u00e9j\u00e0 vu");
  const bytes = new Uint8Array(await pdf.arrayBuffer());
  const pdfText = Array.from(bytes, (byte) => String.fromCharCode(byte)).join("");

  expect(pdfText).toContain("Fici\u00f3n d\u00e9j\u00e0 vu");
  await expect(
    createWorkflowPdf(graph, `Invalid ${String.fromCharCode(0x80)}`),
  ).rejects.toThrow("printable Latin-1 text");
});
