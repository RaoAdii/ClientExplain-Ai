import { LegalPage } from "@/components/legal-page";
import { pageMetadata } from "@/lib/metadata";
export const metadata = pageMetadata(
  "Terms and Conditions",
  "Draft terms for evaluating ClientExplain AI, including professional review requirements and current feature limitations.",
  "/terms",
);
export default function Page() {
  return (
    <LegalPage title="Terms and Conditions">
      <h2>Evaluation release</h2>
      <p>
        ClientExplain AI currently provides project organization. AI analysis,
        document processing, illustrations, editable diagrams, approval
        workflows, version history, and exports are planned capabilities and are
        not offered by this release.
      </p>
      <h2>Professional responsibility</h2>
      <p>
        The application does not provide legal advice, establish an
        attorney-client relationship, or verify the accuracy of legal
        information. All future AI-generated explanations must be reviewed by a
        qualified legal professional before being used or shared. Users remain
        responsible for facts, sources, jurisdiction, and professional
        obligations.
      </p>
      <h2>Acceptable use</h2>
      <p>
        Use the evaluation with non-confidential information that you are
        authorized to provide. Do not upload unlawful content, interfere with
        the service, attempt unauthorized access, or present unreviewed
        generated material as verified legal advice.
      </p>
      <h2>Accounts and content</h2>
      <p>
        Keep account credentials secure. You retain your rights in the content
        you provide. The service processes that content only as needed to
        operate the requested features, subject to the final privacy policy and
        any separately agreed provider terms.
      </p>
      <h2>Availability and limitations</h2>
      <p>
        This foundation may change and may be interrupted. Do not rely on it for
        court deadlines, emergency matters, or a sole copy of important records.
        No guarantee of fitness, accuracy, or uninterrupted service is made by
        this draft. Any enforceable warranties, exclusions, and liability limits
        require jurisdiction-specific review.
      </p>
      <h2>Deletion and termination</h2>
      <p>
        You can delete projects from the workspace. Hosted account closure,
        suspension, data export, and post-termination retention processes must
        be finalized before general availability.
      </p>
      <h2>Terms requiring business and legal review</h2>
      <p>
        The operator must confirm its contracting entity, verified contact
        details, governing law, dispute resolution process, pricing and
        cancellation terms if applicable, minimum user age, and any required
        consumer protections. This draft does not select a jurisdiction or waive
        mandatory legal rights.
      </p>
    </LegalPage>
  );
}
