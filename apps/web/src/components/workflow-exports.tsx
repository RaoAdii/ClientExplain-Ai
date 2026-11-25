"use client";

import { useMemo, useState } from "react";
import Image from "next/image";
import type { WorkflowGraph } from "@/types/workflow";
import {
  buildWorkflowDiagram,
  createWorkflowPdf,
  renderWorkflowPng,
  saveDownload,
  workflowFilename,
} from "@/lib/workflow-export";
import { Button } from "./ui/button";

export function WorkflowExports({
  graph,
  projectName,
  saved,
}: {
  graph: WorkflowGraph;
  projectName: string;
  saved: boolean;
}) {
  const [exporting, setExporting] = useState<"pdf" | "png" | null>(null);
  const [error, setError] = useState("");
  const diagram = useMemo(
    () =>
      graph.stages.length
        ? buildWorkflowDiagram(graph, projectName)
        : undefined,
    [graph, projectName],
  );
  const disabled = !saved || !diagram || !!exporting;

  async function download(format: "pdf" | "png") {
    if (!diagram || disabled) return;
    setError("");
    setExporting(format);
    try {
      const file =
        format === "png"
          ? await renderWorkflowPng(diagram.svg)
          : await createWorkflowPdf(graph, projectName);
      saveDownload(file, workflowFilename(projectName, format));
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : `The ${format.toUpperCase()} export failed. Try again.`,
      );
    } finally {
      setExporting(null);
    }
  }

  return (
    <section className="workflow-exports" aria-labelledby="workflow-export-title">
      <h3 id="workflow-export-title">Generated SVG diagram and exports</h3>
      <p>
        The diagram is generated locally from saved stage names and connections;
        it is not AI-generated or legally verified. The PDF contains the saved
        workflow details and review status.
      </p>
      {diagram && (
        <figure>
          <figcaption>Locally generated diagram preview</figcaption>
          <Image
            src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(diagram.svg)}`}
            alt={`Generated workflow diagram for ${projectName}`}
            width={diagram.width}
            height={diagram.height}
            unoptimized
          />
        </figure>
      )}
      {!graph.stages.length && (
        <p>Add and save at least one stage to enable workflow exports.</p>
      )}
      {graph.stages.length > 0 && !saved && (
        <p role="status">Save the workflow before exporting it.</p>
      )}
      <div className="editor-toolbar">
        <Button
          variant="outline"
          disabled={disabled}
          onClick={() => void download("png")}
        >
          {exporting === "png" ? "Creating PNG…" : "Download workflow PNG"}
        </Button>
        <Button
          variant="outline"
          disabled={disabled}
          onClick={() => void download("pdf")}
        >
          {exporting === "pdf" ? "Creating PDF…" : "Download workflow PDF"}
        </Button>
      </div>
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
