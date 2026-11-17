"use client";
import { ShieldCheck, Database, Palette } from "lucide-react";
import { useSession } from "@/hooks/use-session";
import { Card, PageHeader } from "./common";

export function Settings() {
  const { data } = useSession();
  return (
    <>
      <PageHeader eyebrow="Workspace / Settings" title="Settings">
        Understand your workspace and account configuration.
      </PageHeader>
      <div className="settings-grid">
        <Card>
          <ShieldCheck className="setting-icon" />
          <h2>Account and access</h2>
          <dl className="project-details">
            <dt>Session</dt>
            <dd>
              {data?.local ? "Local development session" : "Supabase account"}
            </dd>
            <dt>Account</dt>
            <dd>
              {data?.email ? (
                <a href={`mailto:${data.email}`}>{data.email}</a>
              ) : (
                "No cloud account connected"
              )}
            </dd>
            <dt>Professional review</dt>
            <dd>Required for all AI-generated explanations</dd>
          </dl>
        </Card>
        <Card>
          <Database className="setting-icon" />
          <h2>Project data</h2>
          <p>
            Project changes are saved to the workspace database. You can edit or
            permanently delete each project from its details page.
          </p>
          <p className="field-hint">
            Use non-confidential test information while evaluating this
            foundation.
          </p>
        </Card>
        <Card>
          <Palette className="setting-icon" />
          <h2>Reading experience</h2>
          <p>
            The workspace uses a light appearance with readable contrast. Motion
            follows your device’s reduced-motion preference.
          </p>
          <p className="field-hint">
            Firm administration, custom branding, and account management are
            planned for later releases.
          </p>
        </Card>
      </div>
    </>
  );
}
