"use client";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { projectSchema, type ProjectInput } from "@/lib/validation";
import { Field } from "./common";
import { Button } from "./ui/button";

const contextFields = [
  { name: "jurisdiction", label: "Jurisdiction", limit: 120, hint: "Country, state, or court system that applies." },
  { name: "legal_area", label: "Legal area", limit: 120, hint: "For example, civil litigation or family law." },
  { name: "language", label: "Language", limit: 60, hint: "Language for the client explanation." },
  { name: "target_audience", label: "Target audience", limit: 120, hint: "Who will read the explanation?" },
  { name: "complexity", label: "Complexity", limit: 40, hint: "Describe the level of detail, or use unspecified." },
] as const;

export function ProjectForm({ initial, onSubmit, onCancel, submitLabel = "Create project" }: {
  initial?: ProjectInput;
  onSubmit: (data: ProjectInput) => Promise<void>;
  onCancel?: () => void;
  submitLabel?: string;
}) {
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<z.input<typeof projectSchema>, unknown, ProjectInput>({
    resolver: zodResolver(projectSchema),
    defaultValues: {
      name: initial?.name ?? "", description: initial?.description ?? "", jurisdiction: initial?.jurisdiction ?? "",
      legal_area: initial?.legal_area ?? "", language: initial?.language ?? "", target_audience: initial?.target_audience ?? "",
      complexity: initial?.complexity ?? "unspecified", workflow_status: initial?.workflow_status ?? "draft",
    },
  });
  return (
    <form className="project-form" onSubmit={handleSubmit(onSubmit)} noValidate>
      <Field label="Project name" id="name" error={errors.name?.message}>
        <input id="name" {...register("name")} maxLength={200} aria-invalid={!!errors.name} aria-describedby={errors.name ? "name-error" : undefined} />
      </Field>
      <div className="project-context-fields">
        {contextFields.map(({ name, label, limit, hint }) => (
          <Field key={name} label={label} id={name} error={errors[name]?.message} hint={hint}>
            <input id={name} {...register(name)} maxLength={limit} aria-invalid={!!errors[name]} aria-describedby={`${name}-hint${errors[name] ? ` ${name}-error` : ""}`} />
          </Field>
        ))}
        <Field label="Workflow status" id="workflow_status" error={errors.workflow_status?.message}>
          <select id="workflow_status" {...register("workflow_status")} aria-invalid={!!errors.workflow_status} aria-describedby={errors.workflow_status ? "workflow_status-error" : undefined}>
            <option value="draft">Draft</option><option value="active">Active</option><option value="archived">Archived</option>
          </select>
        </Field>
      </div>
      <Field label="Project description" id="description" error={errors.description?.message} hint="Describe the process and explanation you want to prepare. Avoid confidential client information.">
        <textarea id="description" rows={5} {...register("description")} maxLength={10000} aria-invalid={!!errors.description} aria-describedby={`description-hint${errors.description ? " description-error" : ""}`} />
      </Field>
      <div className="form-actions">
        {onCancel && <Button variant="outline" type="button" onClick={onCancel} disabled={isSubmitting}>Cancel</Button>}
        <Button disabled={isSubmitting}>{isSubmitting ? "Saving…" : submitLabel}</Button>
      </div>
    </form>
  );
}
