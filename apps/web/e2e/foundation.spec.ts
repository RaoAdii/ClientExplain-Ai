import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

function generatedDocx() {
  const root = resolve(process.cwd(), "../..");
  const python = resolve(root, process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python");
  return execFileSync(python, ["-c", `
from io import BytesIO
from zipfile import ZipFile
import sys
b = BytesIO()
with ZipFile(b, 'w') as z:
 z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
 z.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
 z.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Generated non confidential process briefing. Review the filing documents.</w:t></w:r></w:p></w:body></w:document>')
sys.stdout.buffer.write(b.getvalue())
`]);
}
function generatedPdf() {
  const stream = "BT /F1 12 Tf 72 720 Td (Generated non confidential filing briefing.) Tj ET";
  const objects = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>", "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>", `<< /Length ${Buffer.byteLength(stream)} >>\nstream\n${stream}\nendstream`];
  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((object, index) => { offsets.push(Buffer.byteLength(pdf)); pdf += `${index + 1} 0 obj\n${object}\nendobj\n`; });
  const xref = Buffer.byteLength(pdf);
  pdf += `xref\n0 6\n0000000000 65535 f \n${offsets.slice(1).map((offset) => `${String(offset).padStart(10, "0")} 00000 n \n`).join("")}trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return Buffer.from(pdf);
}

test("public pages, navigation, metadata and responsive layout", async ({
  page,
  isMobile,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  for (const path of ["/", "/login", "/register", "/privacy", "/terms"]) {
    await page.goto(path);
    await expect(page.locator("h1")).toHaveCount(1);
    await expect(page).toHaveTitle(/ClientExplain AI/);
    await expect(page.locator('meta[name="description"]')).toHaveAttribute(
      "content",
      /.+/,
    );
    expect(
      new URL(
        (await page.locator('link[rel="canonical"]').getAttribute("href"))!,
      ).pathname,
    ).toBe(path);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    expect(
      (
        await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
  }
  await page.goto("/");
  if (isMobile) {
    await page.getByRole("button", { name: "Open menu", exact: true }).click();
    await page
      .getByRole("navigation", { name: "Mobile navigation" })
      .getByRole("link", { name: "Sign in", exact: true })
      .click();
    await expect(page).toHaveURL(/login/);
  }
  await page.goto("/");
  const links = await page
    .locator('a[href^="/"]')
    .evaluateAll((anchors) => [
      ...new Set(
        anchors.map((a) => a.getAttribute("href")!.split("#")[0] || "/"),
      ),
    ]);
  for (const href of links) {
    const response = await page.request.get(href);
    expect(response.status(), href).toBeLessThan(400);
  }
  await page.screenshot({
    path: `test-results/landing-${isMobile ? "mobile" : "desktop"}.png`,
    fullPage: true,
  });
  expect(errors).toEqual([]);
  const missing = await page.goto("/not-a-real-page");
  expect(missing?.status()).toBe(404);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "out of reach",
  );
});

test("real project, document processing, unavailable analysis, persistence and deletion", async ({
  page,
  isMobile,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/login/);
  await page.getByRole("button", { name: "Open local workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "A clearer starting point." }),
  ).toBeVisible();
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.getByRole("link", { name: "New project", exact: true }).click();
  await page
    .getByRole("button", { name: "Create project", exact: true })
    .click();
  await expect(page.getByText("Enter a project name.")).toBeVisible();
  const name = `Process briefing ${Date.now()}`;
  test.setTimeout(120000);
  await page.getByLabel("Project name", { exact: true }).fill(name);
  await page
    .getByLabel("Jurisdiction", { exact: true })
    .fill("England and Wales");
  await page
    .getByLabel("Project description", { exact: true })
    .fill("Prepare a non-confidential explanation of the review process.");
  await page.getByLabel("Legal area", { exact: true }).fill("Civil litigation");
  await page.getByLabel("Language", { exact: true }).fill("English");
  await page.getByLabel("Target audience", { exact: true }).fill("First-time client");
  await page.getByLabel("Complexity", { exact: true }).fill("standard");
  await page.getByLabel("Workflow status", { exact: true }).selectOption("active");
  await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Project created" })).toBeVisible();
  await expect(page).toHaveURL(/\/dashboard\/projects\/[0-9a-f-]+$/);
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(name);
  await expect(
    page.getByText("England and Wales", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Civil litigation", { exact: true })).toBeVisible();
  await expect(page.getByText("First-time client", { exact: true })).toBeVisible();
  const files = [
    { name: "brief.txt", mimeType: "text/plain", buffer: Buffer.from("Generated non confidential TXT filing notes.") },
    { name: "brief.docx", mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", buffer: generatedDocx() },
    { name: "brief.pdf", mimeType: "application/pdf", buffer: generatedPdf() },
  ];
  for (const file of files) {
    await page.getByLabel("Document file", { exact: true }).setInputFiles(file);
    await page.getByRole("button", { name: "Upload document", exact: true }).click();
    await expect(page.getByLabel(`Select ${file.name}`, { exact: true })).toBeEnabled({ timeout: 45000 });
  }
  await expect(page.locator("h1")).toHaveCount(1);
  await page.getByRole("link", { name: "Analysis", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#analysis$/);
  await page.getByLabel("Process text", { exact: true }).fill("Explain the filing and review process for a civil claim.");
  await page.getByLabel("Select brief.txt", { exact: true }).check();
  await expect(page.getByRole("button", { name: "Analyze process", exact: true })).toBeDisabled();
  await page.getByLabel("I authorize external processing of the selected documents.", { exact: true }).check();
  const providerResponse = page.waitForResponse((response) => response.url().endsWith("/analyze") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Analyze process", exact: true }).click();
  expect((await providerResponse).status()).toBe(503);
  await expect(page.getByRole("alert").filter({ hasText: /provider|processing|configured|disabled/i })).toBeVisible();
  await expect(page.getByLabel("Process text", { exact: true })).toHaveValue("Explain the filing and review process for a civil claim.");
  // The browser reports this deliberately exercised HTTP 503; all other console errors fail.
  const expectedProviderError = errors.findIndex((error) => /503/.test(error));
  if (expectedProviderError >= 0) errors.splice(expectedProviderError, 1);
  for (const width of [320, 375, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `Project overflow at ${width}px`).toBe(true);
  }
  expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations).toEqual([]);
  const projectUrl = page.url().split("#")[0];
  await page.goto("/dashboard/projects");
  await page.getByRole("link").filter({ has: page.getByRole("heading", { name, exact: true }) }).click();
  await expect(page).toHaveURL(projectUrl);
  for (const file of files) await expect(page.getByLabel(`Select ${file.name}`, { exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Delete brief.txt", exact: true }).click();
  await page.getByRole("button", { name: "Keep document", exact: true }).click();
  await page.getByRole("button", { name: "Delete brief.txt", exact: true }).click();
  await page.getByRole("button", { name: "Confirm document deletion", exact: true }).click();
  await expect(page.getByLabel("Select brief.txt", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Edit details" }).click();
  await page
    .getByLabel("Project name", { exact: true })
    .fill(`${name} revised`);
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    `${name} revised`,
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: `test-results/project-${isMobile ? "mobile" : "desktop"}.png`,
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Delete project", exact: true })
    .click();
  await page.getByRole("button", { name: "Keep project" }).click();
  await page
    .getByRole("button", { name: "Delete project", exact: true })
    .click();
  await page.getByRole("button", { name: "Confirm deletion" }).click();
  await expect(page).toHaveURL(/\/dashboard\/projects$/);
  await expect(
    page.getByRole("heading", { name: `${name} revised` }),
  ).toHaveCount(0);
  await page.goto("/dashboard/settings");
  await expect(
    page.getByRole("heading", { name: "Settings", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  if (isMobile)
    await page
      .getByRole("button", { name: "Open workspace navigation" })
      .click();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/login/);
  await page.goto("/dashboard/projects");
  await expect(page).toHaveURL(/login/);
  expect(errors).toEqual([]);
});

test("320px layout, keyboard entry and discovery files", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  for (const path of [
    "/",
    "/login",
    "/register",
    "/privacy",
    "/terms",
    "/missing-page",
  ]) {
    await page.goto(path);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  }
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#main$/);
  for (const path of [
    "/sitemap.xml",
    "/robots.txt",
    "/llms.txt",
    "/icon.svg",
  ]) {
    expect((await page.request.get(path)).status()).toBe(200);
  }
});

test("requested responsive widths stay within the viewport", async ({
  page,
}) => {
  for (const width of [375, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of ["/", "/login", "/privacy", "/terms"]) {
      await page.goto(path);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
        `${path} overflowed at ${width}px`,
      ).toBe(true);
    }
  }
  await page.goto("/login");
  await page.getByRole("button", { name: "Open local workspace" }).click();
  await expect(page).toHaveURL(/dashboard/);
  for (const width of [375, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of [
      "/dashboard",
      "/dashboard/projects",
      "/dashboard/settings",
    ]) {
      await page.goto(path);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
        `${path} overflowed at ${width}px`,
      ).toBe(true);
    }
  }
});

test("service errors are visible and local session rejects cross-origin requests", async ({
  page,
}) => {
  const rejected = await page.request.post("/api/dev-session", {
    headers: { Origin: "https://untrusted.invalid" },
  });
  expect(rejected.status()).toBe(403);
  await page.goto("/login");
  await page.getByRole("button", { name: "Open local workspace" }).click();
  await expect(page).toHaveURL(/dashboard/);
  const boundary = await page.evaluate(async () => {
    const created = await fetch("/api/backend/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "Escaped payload boundary",
        description: '"'.repeat(10000),
        jurisdiction: "",
      }),
    });
    const project = await created.json();
    const removed = await fetch(`/api/backend/projects/${project.id}`, {
      method: "DELETE",
    });
    return { createStatus: created.status, deleteStatus: removed.status };
  });
  expect(boundary.createStatus).toBe(201);
  expect(boundary.deleteStatus).toBe(204);
  const unavailableId = "00000000-0000-4000-8000-000000000001";
  await page.route(`**/api/backend/projects/${unavailableId}`, (route) =>
    route.fulfill({
      status: 503,
      json: { error: { message: "Project service temporarily unavailable." } },
    }),
  );
  await page.goto(`/dashboard/projects/${unavailableId}`);
  await expect(
    page.getByText("Project service temporarily unavailable."),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  await page.unroute(`**/api/backend/projects/${unavailableId}`);
  await page.route("**/api/backend/projects?*", (route) =>
    route.fulfill({
      status: 503,
      json: {
        error: {
          message: "Workspace connection interrupted. Please try again.",
        },
      },
    }),
  );
  await page.goto("/dashboard/projects");
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "Workspace connection interrupted" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
});
