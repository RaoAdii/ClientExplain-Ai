import { ForgotPassword } from "@/components/password-recovery";
import { pageMetadata } from "@/lib/metadata";
export const metadata = pageMetadata(
  "Forgot password",
  "Request a password reset link for your ClientExplain AI account.",
  "/forgot-password",
  true,
);
export default function ForgotPasswordPage() {
  return (
    <main id="main" className="auth-main container">
      <section className="auth-card">
        <h1>Forgot password</h1>
        <p>Enter your account email to request a reset link.</p>
        <ForgotPassword />
      </section>
    </main>
  );
}
