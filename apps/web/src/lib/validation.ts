import { z } from "zod";

export const projectSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "Enter a project name.")
    .max(200, "Use 200 characters or fewer."),
  description: z.string().trim().max(10000, "Use 10,000 characters or fewer."),
  jurisdiction: z.string().trim().max(120, "Use 120 characters or fewer."),
  legal_area: z.string().trim().max(120, "Use 120 characters or fewer.").default(""),
  language: z.string().trim().max(60, "Use 60 characters or fewer.").default(""),
  target_audience: z.string().trim().max(120, "Use 120 characters or fewer.").default(""),
  complexity: z.string().trim().min(1, "Enter a complexity or use unspecified.").max(40, "Use 40 characters or fewer.").default("unspecified"),
  workflow_status: z.enum(["draft", "active", "archived"]).default("draft"),
});
export type ProjectInput = z.infer<typeof projectSchema>;
const authEmail = z.email("Enter a valid email address.");
export const loginSchema = z.object({
  email: authEmail,
  password: z
    .string()
    .min(1, "Enter your password.")
    .max(128, "Use 128 characters or fewer."),
});
export const registrationSchema = z.object({
  email: authEmail,
  password: z
    .string()
    .min(8, "Use at least 8 characters.")
    .max(128, "Use 128 characters or fewer."),
});
export type AuthInput = z.infer<typeof loginSchema>;
export const recoverySchema = z.object({ email: authEmail });
export const resetPasswordSchema = z
  .object({
    password: registrationSchema.shape.password,
    confirmation: z.string(),
  })
  .refine((input) => input.password === input.confirmation, {
    message: "Passwords must match.",
    path: ["confirmation"],
  });
