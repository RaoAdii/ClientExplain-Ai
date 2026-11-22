import { describe, expect, it } from "vitest";
import {
  projectSchema,
  loginSchema,
  registrationSchema,
  recoverySchema,
  resetPasswordSchema,
} from "./validation";

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
  it("rejects malformed emails in all email flows", () => {
    for (const email of ["", "lawyer", "lawyer@", "lawyer@example.com extra"]) {
      expect(
        loginSchema.safeParse({ email, password: "password" }).success,
      ).toBe(false);
      expect(
        registrationSchema.safeParse({ email, password: "password" }).success,
      ).toBe(false);
      expect(recoverySchema.safeParse({ email }).success).toBe(false);
    }
  });
  it("requires a new password and matching confirmation for resets", () => {
    expect(
      resetPasswordSchema.safeParse({
        password: "short",
        confirmation: "short",
      }).success,
    ).toBe(false);
    expect(
      resetPasswordSchema.safeParse({
        password: "new-password",
        confirmation: "different",
      }).success,
    ).toBe(false);
    expect(
      resetPasswordSchema.safeParse({
        password: "new-password",
        confirmation: "new-password",
      }).success,
    ).toBe(true);
  });
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
