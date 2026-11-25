import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

test("manual workflow edits, dependencies, React Flow interactions, undo/redo, conflict and layout survive reload", async ({ page, isMobile }) => {
  test.setTimeout(120000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().includes("409")) errors.push(message.text());
  });
  await page.goto("/login");
  await page.getByRole("button", { name: "Open local workspace" }).click();
  await expect(page).toHaveURL(/dashboard/);
  const projectName = `Manual workflow acceptance ${Date.now()}`;
  const project = await page.evaluate(async (name) => {
    const response = await fetch("/api/backend/projects", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) });
    if (!response.ok) throw new Error("Project creation failed");
    return response.json() as Promise<{ id: string }>;
  }, projectName);
  try {
    await page.goto(`/dashboard/projects/${project.id}`);
    const sampleName = "demo-fictitious-community-venue-process.txt";
    await page.getByLabel("Document file", { exact: true }).setInputFiles({
      name: sampleName,
      mimeType: "text/plain",
      buffer: await readFile(
        resolve(process.cwd(), "../..", "samples", sampleName),
      ),
    });
    await page.getByRole("button", { name: "Upload document", exact: true }).click();
    await expect(page.getByLabel(`Select ${sampleName}`, { exact: true })).toBeEnabled({ timeout: 45000 });
    await page.getByRole("button", { name: "Open workflow editor" }).click();

    // Add two stages and edit titles/explanations
    await page.getByRole("button", { name: "Add stage", exact: true }).click();
    await page.getByLabel("Stage title", { exact: true }).fill("Read the supplied document");
    await page.getByLabel("Stage explanation", { exact: true }).fill("Read the user's record and note questions for counsel.");
    await page.getByRole("button", { name: "Add stage", exact: true }).click();
    await page.getByLabel("Stage title", { exact: true }).fill("Discuss questions with counsel");

    // Connect stages
    await page.getByLabel("From stage", { exact: true }).selectOption({ label: "Read the supplied document" });
    await page.getByLabel("To stage", { exact: true }).selectOption({ label: "Discuss questions with counsel" });
    await page.getByRole("button", { name: "Connect stages", exact: true }).click();
    await expect(page.locator(".react-flow__edge")).toHaveCount(1);

    // Undo / Redo check
    await page.getByRole("button", { name: "Undo", exact: true }).click();
    await expect(page.locator(".react-flow__edge")).toHaveCount(0);
    await page.getByRole("button", { name: "Redo", exact: true }).click();
    await expect(page.locator(".react-flow__edge")).toHaveCount(1);

    // Unsaved changes indicator and Reload confirmation cancel
    await expect(page.getByText("Unsaved changes", { exact: true })).toBeVisible();
    page.once("dialog", (dialog) => dialog.dismiss());
    await page.getByRole("button", { name: "Reload workflow", exact: true }).click();
    await expect(page.locator(".react-flow__node")).toHaveCount(2);

    // Save workflow
    await page.getByRole("button", { name: "Save workflow", exact: true }).click();
    await expect(page.getByText("Workflow saved.", { exact: true })).toBeVisible();
    await expect(page.getByRole("img", { name: `Generated workflow diagram for ${projectName}` })).toBeVisible();

    const pngDownloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download workflow PNG", exact: true }).click();
    const pngDownload = await pngDownloadPromise;
    const pngPath = await pngDownload.path();
    if (!pngPath) throw new Error("PNG export did not create a downloadable file.");
    const pngBytes = await readFile(pngPath);
    expect(pngBytes.subarray(0, 8).toString("hex")).toBe("89504e470d0a1a0a");
    expect(pngBytes.readUInt32BE(16)).toBeGreaterThan(0);
    expect(pngBytes.readUInt32BE(20)).toBeGreaterThan(0);
    expect(pngBytes.byteLength).toBeGreaterThan(1000);

    const pdfDownloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download workflow PDF", exact: true }).click();
    const pdfDownload = await pdfDownloadPromise;
    const pdfPath = await pdfDownload.path();
    if (!pdfPath) throw new Error("PDF export did not create a downloadable file.");
    const pdfBytes = await readFile(pdfPath);
    expect(pdfBytes.toString("utf8", 0, 5)).toBe("%PDF-");
    expect(pdfBytes.byteLength).toBeGreaterThan(500);
    const pdfText = pdfBytes.toString("latin1");
    expect(pdfText).toContain("Saved workflow report");
    expect(pdfText).toContain("Read the supplied document");
    expect(pdfText).toContain("Discuss questions with counsel");

    // React Flow canvas interactions: zoom controls, fit view, node click & drag on desktop
    await page.getByRole("button", { name: "Zoom Out" }).click();
    await page.getByRole("button", { name: "Zoom In" }).click();
    await page.getByRole("button", { name: "Fit View" }).click();
    if (!isMobile) {
      const firstNode = page.locator(".react-flow__node").first();
      const box = await firstNode.boundingBox();
      expect(box).not.toBeNull();
      if (box) {
        const startX = box.x + box.width / 2;
        const startY = box.y + box.height / 2;
        await page.mouse.move(startX, startY);
        await page.mouse.down();
        await page.mouse.move(startX + 80, startY + 20, { steps: 5 });
        await page.mouse.up();
        await expect(page.getByText("Unsaved changes", { exact: true })).toBeVisible();
        await page.getByRole("button", { name: "Save workflow", exact: true }).click();
        await expect(page.getByText("Workflow saved.", { exact: true })).toBeVisible();
      }
    }

    // Reload and verify persistence
    await page.reload();
    await page.getByRole("button", { name: "Open workflow editor" }).click();
    await expect(page.getByRole("button", { name: "1. Read the supplied document", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Remove connection", exact: true })).toBeVisible();
    await expect(page.locator(".react-flow__node")).toHaveCount(2);
    await expect(page.locator(".react-flow__edge")).toHaveCount(1);
    await page.getByRole("button", { name: "1. Read the supplied document", exact: true }).click();
    await expect(page.getByLabel("Stage explanation", { exact: true })).toHaveValue("Read the user's record and note questions for counsel.");

    // Reorder stage 2 earlier, remove connection, delete a stage, and save
    await page.getByRole("button", { name: "2. Discuss questions with counsel", exact: true }).click();
    await page.getByRole("button", { name: "Move earlier", exact: true }).click();
    await expect(page.getByRole("button", { name: "1. Discuss questions with counsel", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Remove connection", exact: true }).click();
    await expect(page.locator(".react-flow__edge")).toHaveCount(0);
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "Delete stage", exact: true }).click();
    await expect(page.locator(".react-flow__node")).toHaveCount(1);
    await page.getByRole("button", { name: "Save workflow", exact: true }).click();
    await expect(page.getByText("Workflow saved.", { exact: true })).toBeVisible();

    // Version conflict handling: bump version out-of-band, then attempt save
    await page.evaluate(async (id) => {
      const current = await fetch(`/api/backend/projects/${id}/workflow`).then((r) => r.json());
      await fetch(`/api/backend/projects/${id}/workflow`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ version: current.version, stages: current.stages, edges: current.edges }),
      });
    }, project.id);
    await page.getByRole("button", { name: "Add stage", exact: true }).click();
    await expect(page.getByRole("button", { name: "Download workflow PNG", exact: true })).toBeDisabled();
    await page.getByRole("button", { name: "Save workflow", exact: true }).click();
    await expect(page.getByText("The workflow changed. Reload before saving your changes.")).toBeVisible();

    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  } finally {
    const origin = new URL(page.url()).origin;
    const documentsResponse = await page.request.get(`/api/backend/projects/${project.id}/documents`, { headers: { origin } });
    expect(documentsResponse.status()).toBe(200);
    const documents = await documentsResponse.json() as { id: string }[];
    for (const document of documents) {
      const deleted = await page.request.delete(`/api/backend/documents/${document.id}`, { headers: { origin } });
      expect(deleted.status()).toBe(204);
    }
    const response = await page.request.delete(`/api/backend/projects/${project.id}`, { headers: { origin } });
    expect(response.status()).toBe(204);
  }
});
