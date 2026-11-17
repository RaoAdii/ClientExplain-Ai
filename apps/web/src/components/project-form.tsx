"use client";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { projectSchema, type ProjectInput } from "@/lib/validation";
import { Field } from "./common";
import { Button } from "./ui/button";

export function ProjectForm({
  initial,
  onSubmit,
  onCancel,
  submitLabel = "Create project",
}: {
  initial?: ProjectInput;
  onSubmit: (data: ProjectInput) => Promise<void>;
  onCancel?: () => void;
  submitLabel?: string;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ProjectInput>({
    resolver: zodResolver(projectSchema),
    defaultValues: initial || { name: "", description: "", jurisdiction: "" },
  });
  return (
    <form className="project-form" onSubmit={handleSubmit(onSubmit)} noValidate>
      <Field label="Project name" id="name" error={errors.name?.message}>
        <input
          id="name"
          {...register("name")}
          maxLength={200}
          aria-invalid={!!errors.name}
          aria-describedby={errors.name ? "name-error" : undefined}
        />
      </Field>
      <Field
        label="Jurisdiction"
        id="jurisdiction"
        error={errors.jurisdiction?.message}
        hint="Optional. Record the country, state, or court system that applies."
      >
        <input
          id="jurisdiction"
          {...register("jurisdiction")}
          maxLength={120}
          aria-describedby="jurisdiction-hint"
        />
      </Field>
      <Field
        label="Project description"
        id="description"
        error={errors.description?.message}
        hint="Describe the process and the explanation you want to prepare. Do not include confidential client information."
      >
        <textarea
          id="description"
          rows={5}
          {...register("description")}
          maxLength={10000}
          aria-describedby="description-hint"
        />
      </Field>
      <div className="form-actions">
        {onCancel && (
          <Button
            variant="outline"
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
        )}
        <Button disabled={isSubmitting}>
          {isSubmitting ? "Saving…" : submitLabel}
        </Button>
      </div>
    </form>
  );
}
