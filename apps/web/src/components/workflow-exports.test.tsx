import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import type { WorkflowGraph } from "@/types/workflow";
import { WorkflowExports } from "./workflow-exports";

const graph: WorkflowGraph = {
  version: 1,
  review_status: "requires_review",
  stages: [
    {
      id: "stage-1",
      title: "Fictional request",
      explanation: "A non-legal demo step.",
      responsible_party: null,
      required_documents: [],
      limitations: [],
      position: { x: 40, y: 0 },
      actions: [],
      preconditions: [],
      outcomes: [],
      status: "pending",
    },
  ],
  edges: [],
};

test("requires saved workflow data before enabling export", () => {
  render(
    <WorkflowExports
      graph={graph}
      projectName="Fictional demo"
      saved={false}
    />,
  );

  expect(screen.getByRole("status")).toHaveTextContent(
    "Save the workflow before exporting it.",
  );
  expect(
    screen.getByRole("button", { name: "Download workflow PNG" }),
  ).toBeDisabled();
  expect(
    screen.getByRole("button", { name: "Download workflow PDF" }),
  ).toBeDisabled();
  expect(
    screen.getByRole("img", { name: "Generated workflow diagram for Fictional demo" }),
  ).toBeInTheDocument();
});

test("enables PDF and PNG downloads for a saved workflow", () => {
  render(
    <WorkflowExports graph={graph} projectName="Fictional demo" saved />,
  );

  expect(
    screen.getByRole("button", { name: "Download workflow PNG" }),
  ).toBeEnabled();
  expect(
    screen.getByRole("button", { name: "Download workflow PDF" }),
  ).toBeEnabled();
});
