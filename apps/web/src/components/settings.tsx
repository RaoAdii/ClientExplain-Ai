"use client";
import { type FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, Palette, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useSession } from "@/hooks/use-session";
import { api } from "@/services/api";
import { useUI } from "@/stores/ui";
import { Card, PageHeader } from "./common";
import { VerificationResend } from "./password-recovery";

type Profile = { profile: { display_name: string } };

export function Settings() {
  const { data } = useSession();
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: ({ signal }) => api<Profile>("auth/me", { signal }),
    enabled: !!data?.authenticated,
  });
  return (
    <>
      <PageHeader eyebrow="Workspace / Settings" title="Settings">
        Understand your workspace and account configuration.
      </PageHeader>
      <div className="settings-grid">
        <Card>
          <ShieldCheck className="setting-icon" />
          <h2>Account and access</h2>
          {data?.authenticated && profile.isPending && (
            <p role="status">Loading profile…</p>
          )}
          {data?.authenticated && profile.error && (
            <p role="alert">{profile.error.message}</p>
          )}
          {data?.authenticated && profile.data && (
            <ProfileEditor
              key={profile.data.profile.display_name}
              initialName={profile.data.profile.display_name}
            />
          )}
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

function ProfileEditor({ initialName }: { initialName: string }) {
  const cache = useQueryClient();
  const notify = useUI((state) => state.notify);
  const [displayName, setDisplayName] = useState(initialName);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const updated = await api<Profile>("auth/me", {
        method: "PATCH",
        body: JSON.stringify({ display_name: displayName }),
      });
      cache.setQueryData(["profile"], updated);
      setDisplayName(updated.profile.display_name);
      notify("Profile updated.");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Profile update failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={saveProfile}>
      <label htmlFor="profile-display-name">Display name</label>
      <input
        id="profile-display-name"
        maxLength={120}
        minLength={1}
        required
        value={displayName}
        onChange={(event) => setDisplayName(event.target.value)}
      />
      {error && <p role="alert">{error}</p>}
      <button type="submit" disabled={saving}>
        {saving ? "Saving…" : "Save profile"}
      </button>
    </form>
  );
}
