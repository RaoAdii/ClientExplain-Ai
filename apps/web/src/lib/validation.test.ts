import { describe, expect, it } from "vitest";
import { projectSchema, loginSchema, registrationSchema } from "./validation";

describe("Project input", () => {
  it("rejects empty, whitespace-only and oversized names", () => {
    for (const name of ["", "  ", "x".repeat(201)]) {
      expect(
        projectSchema.safeParse({ name, description: "", jurisdiction: "" })
          .success,
      ).toBe(false);
    }
  });
  it("normalizes names and preserves useful legal context", () => {
    expect(
      projectSchema.parse({
        name: " Civil process ",
        description: "Briefing",
        jurisdiction: "England and Wales",
      }).name,
    ).toBe("Civil process");
  });
});
describe("Authentication input", () => {
  it("requires strong registration passwords", () => {
    expect(
      registrationSchema.safeParse({ email: "invalid", password: "short" })
        .success,
    ).toBe(false);
  });
  it("allows an existing account to submit a non-empty legacy password", () => {
    expect(
      loginSchema.safeParse({ email: "lawyer@example.com", password: "short" })
        .success,
    ).toBe(true);
    expect(
      loginSchema.safeParse({ email: "lawyer@example.com", password: "" })
        .success,
    ).toBe(false);
  });
});
