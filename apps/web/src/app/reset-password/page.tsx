import { ResetPassword } from "@/components/password-recovery";
import { pageMetadata } from "@/lib/metadata";
export const metadata = pageMetadata(
  "Reset password",
  "Choose a new password for your ClientExplain AI account.",
  "/reset-password",
  true,
);
export default function ResetPasswordPage() {
  return (
    <main id="main" className="auth-main container">
      <section className="auth-card">
        <h1>Reset password</h1>
        <p>Choose and confirm your new account password.</p>
        <ResetPassword />
      </section>
    </main>
  );
}
