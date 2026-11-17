import { z } from "zod";

export const projectSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "Enter a project name.")
    .max(200, "Use 200 characters or fewer."),
  description: z.string().trim().max(10000, "Use 10,000 characters or fewer."),
  jurisdiction: z.string().trim().max(120, "Use 120 characters or fewer."),
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
