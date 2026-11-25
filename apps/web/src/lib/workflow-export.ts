import type { WorkflowGraph } from "@/types/workflow";

const NODE_WIDTH = 280;
const NODE_HEIGHT = 124;
const PADDING = 48;
const HEADER_HEIGHT = 76;
const FOOTER_HEIGHT = 48;
const MAX_DIAGRAM_SIDE = 5000;
const PDF_MARGIN = 42;
const PDF_LINE_HEIGHT = 15;

export type WorkflowDiagram = { svg: string; width: number; height: number };

function escapeXml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function titleLines(value: string, limit = 30) {
  const words = value.trim().split(/\s+/);
  const lines: string[] = [];
  let line = "";
  for (const word of words) {
    const next = line ? `${line} ${word}` : word;
    if (next.length > limit && line) {
      lines.push(line);
      line = word;
    } else {
      line = next;
    }
  }
  if (line) lines.push(line);
  if (lines.length > 2) {
    lines.length = 2;
    lines[1] = `${lines[1].slice(0, limit - 1)}…`;
  }
  return lines;
}

function stageText(lines: string[], x: number) {
  return lines
    .map(
      (line, index) =>
        `<tspan x="${x}" dy="${index === 0 ? 0 : 23}">${escapeXml(line)}</tspan>`,
    )
    .join("");
}

export function buildWorkflowDiagram(
  graph: WorkflowGraph,
  projectName: string,
): WorkflowDiagram {
  if (!graph.stages.length) {
    throw new Error("Add and save at least one stage before exporting.");
  }
  if (
    graph.stages.some(
      ({ position }) =>
        !Number.isFinite(position.x) || !Number.isFinite(position.y),
    )
  ) {
    throw new Error("The workflow contains an invalid stage position.");
  }

  const minX = Math.min(...graph.stages.map((stage) => stage.position.x));
  const minY = Math.min(...graph.stages.map((stage) => stage.position.y));
  const maxX = Math.max(...graph.stages.map((stage) => stage.position.x));
  const maxY = Math.max(...graph.stages.map((stage) => stage.position.y));
  const rawWidth = maxX - minX + NODE_WIDTH + PADDING * 2;
  const rawHeight =
    maxY - minY + NODE_HEIGHT + PADDING * 2 + HEADER_HEIGHT + FOOTER_HEIGHT;
  const scale = Math.min(1, MAX_DIAGRAM_SIDE / rawWidth, MAX_DIAGRAM_SIDE / rawHeight);
  const width = Math.ceil(rawWidth * scale);
  const height = Math.ceil(rawHeight * scale);
  const locations = new Map(
    graph.stages.map((stage) => [
      stage.id,
      {
        x: PADDING + stage.position.x - minX,
        y: PADDING + HEADER_HEIGHT + stage.position.y - minY,
      },
    ]),
  );
  const edges = graph.edges.flatMap((edge) => {
    const source = locations.get(edge.source);
    const target = locations.get(edge.target);
    if (!source || !target) return [];
    const startX = source.x + NODE_WIDTH;
    const startY = source.y + NODE_HEIGHT / 2;
    const endX = target.x;
    const endY = target.y + NODE_HEIGHT / 2;
    const curve = Math.max(36, Math.abs(endX - startX) / 2);
    return [
      `<path d="M ${startX} ${startY} C ${startX + curve} ${startY}, ${endX - curve} ${endY}, ${endX} ${endY}" fill="none" stroke="#71817b" stroke-width="2.5" marker-end="url(#arrow)" />`,
    ];
  });
  const nodes = graph.stages.map((stage, index) => {
    const { x, y } = locations.get(stage.id)!;
    const lines = titleLines(`${index + 1}. ${stage.title}`);
    return `<g>
      <rect x="${x}" y="${y}" width="${NODE_WIDTH}" height="${NODE_HEIGHT}" rx="10" fill="#ffffff" stroke="#185b52" stroke-width="2" />
      <text x="${x + 18}" y="${y + 34}" fill="#202d2b" font-family="Arial, Helvetica, sans-serif" font-size="18" font-weight="600">${stageText(lines, x + 18)}</text>
      <text x="${x + 18}" y="${y + NODE_HEIGHT - 20}" fill="#61706c" font-family="Arial, Helvetica, sans-serif" font-size="14">Status: ${escapeXml(stage.status.replace("_", " "))}</text>
    </g>`;
  });
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img">
    <title>${escapeXml(projectName)} workflow diagram</title>
    <desc>Locally generated from saved workflow stages and connections. Not AI-generated or legally verified.</desc>
    <rect width="100%" height="100%" fill="#f8f9f6" />
    <g transform="scale(${scale})">
      <defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#71817b" /></marker></defs>
      <text x="${PADDING}" y="42" fill="#202d2b" font-family="Arial, Helvetica, sans-serif" font-size="24" font-weight="700">${escapeXml(projectName)} — saved workflow</text>
      ${edges.join("")}
      ${nodes.join("")}
      <text x="${PADDING}" y="${rawHeight - 16}" fill="#61706c" font-family="Arial, Helvetica, sans-serif" font-size="14">Generated locally from saved workflow data. Not AI-generated or legally verified.</text>
    </g>
  </svg>`;
  return { svg, width, height };
}

export async function renderWorkflowPng(svg: string): Promise<Blob> {
  const objectUrl = URL.createObjectURL(
    new Blob([svg], { type: "image/svg+xml;charset=utf-8" }),
  );
  try {
    const image = new Image();
    const loaded = new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () =>
        reject(new Error("The workflow diagram could not be rendered."));
    });
    image.src = objectUrl;
    await loaded;

    const canvas = document.createElement("canvas");
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("PNG export is unavailable in this browser.");
    context.fillStyle = "#f8f9f6";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0);
    return await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (blob) =>
          blob
            ? resolve(blob)
            : reject(new Error("The browser could not create the PNG file.")),
        "image/png",
      );
    });
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

function assertPdfTextSupported(graph: WorkflowGraph, projectName: string) {
  const values = [
    projectName,
    ...graph.stages.flatMap((stage) => [
      stage.title,
      stage.explanation,
      stage.responsible_party || "",
      ...stage.required_documents,
      ...stage.actions,
      ...stage.preconditions,
      ...stage.outcomes,
      ...stage.limitations,
    ]),
  ];
  if (
    values.some(
      (value) =>
        /[^\u0000-\u00ff]/u.test(value) ||
        /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f]/u.test(value),
    )
  ) {
    throw new Error(
      "PDF export currently supports printable Latin-1 text. Remove unsupported characters or export the diagram as PNG.",
    );
  }
}

export async function createWorkflowPdf(
  graph: WorkflowGraph,
  projectName: string,
): Promise<Blob> {
  if (!graph.stages.length) {
    throw new Error("Add and save at least one stage before exporting.");
  }
  assertPdfTextSupported(graph, projectName);
  const { jsPDF } = await import("jspdf");
  const pdf = new jsPDF({ unit: "pt", format: "a4" });
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const contentWidth = pageWidth - PDF_MARGIN * 2;
  let y = PDF_MARGIN;

  function addParagraph(text: string, style: "title" | "heading" | "body" = "body") {
    const isTitle = style === "title";
    const isHeading = style === "heading";
    const fontSize = isTitle ? 20 : isHeading ? 13 : 10;
    const lineHeight = isTitle ? 25 : isHeading ? 18 : PDF_LINE_HEIGHT;
    pdf.setFont("helvetica", isTitle || isHeading ? "bold" : "normal");
    pdf.setFontSize(fontSize);
    const lines = pdf.splitTextToSize(text, contentWidth) as string[];
    if (isHeading && y + lineHeight * lines.length > pageHeight - PDF_MARGIN) {
      pdf.addPage();
      y = PDF_MARGIN;
    }
    for (const line of lines) {
      if (y + lineHeight > pageHeight - PDF_MARGIN) {
        pdf.addPage();
        y = PDF_MARGIN;
      }
      pdf.text(line, PDF_MARGIN, y);
      y += lineHeight;
    }
    y += isHeading ? 4 : 7;
  }

  const stageNames = new Map(graph.stages.map((stage) => [stage.id, stage.title]));
  addParagraph(projectName || "Workflow", "title");
  addParagraph("Saved workflow report", "heading");
  addParagraph(`Generated locally: ${new Date().toISOString()}`);
  addParagraph(`Saved workflow version: ${graph.version}`);
  addParagraph(`Review status: ${graph.review_status.replaceAll("_", " ")}`);
  addParagraph(
    "This file reflects saved workflow data only. Exporting does not verify its accuracy or legal effect; it is not legal advice.",
  );

  addParagraph("Connections", "heading");
  if (!graph.edges.length) {
    addParagraph("No explicit stage connections.");
  } else {
    for (const edge of graph.edges) {
      const source = stageNames.get(edge.source) || "Unknown stage";
      const target = stageNames.get(edge.target) || "Unknown stage";
      addParagraph(`${source} -> ${target}`);
    }
  }

  for (const [index, stage] of graph.stages.entries()) {
    addParagraph(`Stage ${index + 1}: ${stage.title}`, "heading");
    addParagraph(`Status: ${stage.status.replaceAll("_", " ")}`);
    addParagraph(`Explanation: ${stage.explanation}`);
    if (stage.responsible_party) {
      addParagraph(`Responsible party: ${stage.responsible_party}`);
    }
    for (const [label, items] of [
      ["Required documents", stage.required_documents],
      ["Actions", stage.actions],
      ["Preconditions", stage.preconditions],
      ["Possible outcomes", stage.outcomes],
      ["Limitations", stage.limitations],
    ] as const) {
      if (items.length) {
        addParagraph(`${label}: ${items.join("; ")}`);
      }
    }
  }

  const pageCount = pdf.getNumberOfPages();
  for (let page = 1; page <= pageCount; page++) {
    pdf.setPage(page);
    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(8);
    pdf.setTextColor(97, 112, 108);
    pdf.text(
      `ClientExplain AI | Workflow v${graph.version} | Page ${page} of ${pageCount}`,
      PDF_MARGIN,
      pageHeight - 18,
    );
  }
  pdf.setProperties({ title: `${projectName} workflow`, subject: "Saved workflow report" });
  return pdf.output("blob");
}

export function workflowFilename(projectName: string, extension: "pdf" | "png") {
  const slug =
    projectName
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 60) || "workflow";
  return `clientexplain-${slug}-workflow.${extension}`;
}

export function saveDownload(blob: Blob, filename: string) {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}
