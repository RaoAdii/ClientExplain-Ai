"use client";
import { ShieldCheck, Database, Palette } from "lucide-react";
import { useSession } from "@/hooks/use-session";
import { Card, PageHeader } from "./common";
import Link from "next/link";
import { VerificationResend } from "./password-recovery";

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
            {data?.authenticated && !data.local && (
              <>
                <dt>Email verification</dt>
                <dd>{data.verified ? "Verified" : "Awaiting verification"}</dd>
                <dt>Active firm</dt>
                <dd>{data.account?.firm.name || "Unavailable"}</dd>
                <dt>Role</dt>
                <dd>{data.account?.role || "Unavailable"}</dd>
              </>
            )}
            <dt>Professional review</dt>
            <dd>Required for all AI-generated explanations</dd>
          </dl>
          {data?.authenticated && !data.local && (
            <>
              <p>
                <Link href="/forgot-password">Change password</Link>
              </p>
              {!data.verified && data.email && (
                <VerificationResend email={data.email} />
              )}
            </>
          )}
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
            Firm administration and custom branding are planned for later
            releases.
          </p>
        </Card>
      </div>
    </>
  );
}
