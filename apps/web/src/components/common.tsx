import Link from "next/link";
import { Scale, FolderOpen, LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";

export function Logo() {
  return (
    <Link href="/" className="logo" aria-label="ClientExplain AI home">
      <span className="logo-mark">
        <Scale size={22} strokeWidth={1.7} />
      </span>
      <span>
        ClientExplain<span className="logo-ai"> AI</span>
      </span>
    </Link>
  );
}
export function PageHeader({
  eyebrow,
  title,
  children,
  action,
}: {
  eyebrow?: string;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {children && <p className="muted">{children}</p>}
      </div>
      {action}
    </header>
  );
}
export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`card ${className}`}>{children}</div>;
}
export function LoadingState({
  text = "Loading your workspace…",
}: {
  text?: string;
}) {
  return (
    <div className="loading-state" role="status">
      <LoaderCircle className="spinner" size={20} />
      {text}
    </div>
  );
}
export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <FolderOpen size={30} strokeWidth={1.5} />
      </span>
      <h2>{title}</h2>
      <p className="muted">{children}</p>
      {action}
    </div>
  );
}
export function Field({
  label,
  id,
  error,
  hint,
  children,
}: {
  label: string;
  id: string;
  error?: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children}
      {hint && (
        <p className="field-hint" id={`${id}-hint`}>
          {hint}
        </p>
      )}
      {error && (
        <p className="field-error" id={`${id}-error`} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
