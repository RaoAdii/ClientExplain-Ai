import { LegalPage } from "@/components/legal-page";
import { pageMetadata } from "@/lib/metadata";
export const metadata = pageMetadata(
  "Privacy Policy",
  "Draft privacy policy for the ClientExplain AI foundation release. Business and jurisdiction review required.",
  "/privacy",
);
export default function Page() {
  return (
    <LegalPage title="Privacy Policy">
      <h2>Purpose and scope</h2>
      <p>
        ClientExplain AI is an evaluation-stage workspace for organizing legal
        process projects. Do not enter confidential client information,
        privileged communications, or sensitive personal data in this release.
      </p>
      <h2>Information processed</h2>
      <p>
        The application stores project names, descriptions, jurisdiction
        details, timestamps, membership records, and audit events. When Supabase
        Auth is configured, it processes account credentials and authentication
        information. Passwords are not stored by the application API.
      </p>
      <h2>How information is used</h2>
      <p>
        Data is used to authenticate access, save and retrieve projects, isolate
        workspaces, diagnose operational failures, and record project changes.
        This foundation does not send project content to AI providers or offer
        document uploads.
      </p>
      <h2>Storage and service providers</h2>
      <p>
        Local development stores records in PostgreSQL on the development
        computer. Redis supports background work. A hosted deployment may use
        Supabase authentication, private storage, and database services. The
        operator must document actual hosting regions, subprocessors, and
        cross-border transfers before accepting real client data.
      </p>
      <h2>Sessions and cookies</h2>
      <p>
        Local development uses an HTTP-only session cookie, expiring after eight
        hours, to access the local workspace. Supabase sessions use its browser
        authentication storage when configured. No advertising trackers or
        analytics are included in this foundation.
      </p>
      <h2>Retention and deletion</h2>
      <p>
        Projects can be deleted from their details page. Associated project
        records are removed by database relationships. Minimal audit events can
        remain after deletion. Backup retention, account deletion procedures,
        and legally required retention periods must be defined before launch.
      </p>
      <h2>Requests and individual rights</h2>
      <p>
        Rights vary by jurisdiction. The operator must publish a verified
        privacy contact and a process for access, correction, deletion, and
        complaints before public deployment. No fictitious contact address is
        provided in this draft.
      </p>
      <h2>Security and policy changes</h2>
      <p>
        Authentication and workspace access controls reduce risk but do not
        guarantee confidentiality or legal compliance. Deployment security,
        backups, incident response, and this policy require review before
        production use. Material policy changes should be communicated to
        affected users.
      </p>
    </LegalPage>
  );
}
