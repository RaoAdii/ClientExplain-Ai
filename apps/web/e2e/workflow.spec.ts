import { test, expect } from "@playwright/test";

test("manual workflow edits, dependencies and layout survive reload", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
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
    await page.getByRole("button", { name: "Add stage", exact: true }).click();
    await page.getByLabel("Stage title", { exact: true }).fill("Read the supplied document");
    await page.getByLabel("Stage explanation", { exact: true }).fill("Read the user's record and note questions for counsel.");
    await page.getByRole("button", { name: "Add stage", exact: true }).click();
    await page.getByLabel("Stage title", { exact: true }).fill("Discuss questions with counsel");
    await page.getByLabel("From stage", { exact: true }).selectOption({ label: "Read the supplied document" });
    await page.getByLabel("To stage", { exact: true }).selectOption({ label: "Discuss questions with counsel" });
    await page.getByRole("button", { name: "Connect stages", exact: true }).click();
    await page.getByRole("button", { name: "Save workflow", exact: true }).click();
    await expect(page.getByText("Workflow saved.", { exact: true })).toBeVisible();
    await page.reload();
    await page.getByRole("button", { name: "Open workflow editor" }).click();
    await expect(page.getByRole("button", { name: "1. Read the supplied document", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Remove connection", exact: true })).toBeVisible();
    await expect(page.locator(".react-flow__node")).toHaveCount(2);
    await expect(page.locator(".react-flow__edge")).toHaveCount(1);
    await page.getByRole("button", { name: "1. Read the supplied document", exact: true }).click();
    await expect(page.getByLabel("Stage explanation", { exact: true })).toHaveValue("Read the user's record and note questions for counsel.");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  } finally {
    const response = await page.request.delete(`/api/backend/projects/${project.id}`, { headers: { origin: new URL(page.url()).origin } });
    expect(response.status()).toBe(204);
  }
});
