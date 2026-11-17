import { Navbar, Footer } from "./navigation";
import type { ReactNode } from "react";
export function LegalPage({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <>
      <Navbar />
      <main id="main" className="container legal-page">
        <p className="eyebrow">Draft for evaluation · 17 November 2026</p>
        <h1>{title}</h1>
        <div className="policy-notice">
          <strong>
            This policy is a draft, not a statement of legal compliance.
          </strong>
          <p>
            Before public launch, the operator must confirm its legal identity,
            contact details, business location, applicable jurisdictions,
            retention periods, and provider arrangements with qualified legal
            counsel.
          </p>
        </div>
        {children}
      </main>
      <Footer />
    </>
  );
}
