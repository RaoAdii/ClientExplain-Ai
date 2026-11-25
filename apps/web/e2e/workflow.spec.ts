import { test, expect } from "@playwright/test";

test("manual workflow edits, dependencies, React Flow interactions, undo/redo, conflict and layout survive reload", async ({ page, isMobile }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().includes("409")) errors.push(message.text());
  });
  await page.goto("/login");
  await page.getByRole("button", { name: "Open local workspace" }).click();
  await expect(page).toHaveURL(/dashboard/);
  const project = await page.evaluate(async () => {
    const response = await fetch("/api/backend/projects", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: "Manual workflow acceptance" }) });
    if (!response.ok) throw new Error("Project creation failed");
    return response.json() as Promise<{ id: string }>;
  });
  try {
    await page.goto(`/dashboard/projects/${project.id}`);
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
    await page.getByRole("button", { name: "Save workflow", exact: true }).click();
    await expect(page.getByText("The workflow changed. Reload before saving your changes.")).toBeVisible();

    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  } finally {
    const response = await page.request.delete(`/api/backend/projects/${project.id}`, { headers: { origin: new URL(page.url()).origin } });
    expect(response.status()).toBe(204);
  }
});
