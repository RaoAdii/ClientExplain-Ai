import { AuthCallback } from "@/components/password-recovery";
import { pageMetadata } from "@/lib/metadata";
export const metadata = pageMetadata(
  "Confirm account",
  "Complete your ClientExplain AI account confirmation or recovery.",
  "/auth/callback",
  true,
);
export default function AuthCallbackPage() {
  return (
    <main id="main" className="auth-main container">
      <section className="auth-card">
        <h1>Confirm your account</h1>
        <AuthCallback />
      </section>
    </main>
  );
}
