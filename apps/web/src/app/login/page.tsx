import { AuthPage } from "@/components/auth-page";
import { pageMetadata } from "@/lib/metadata";
export const metadata = pageMetadata(
  "Sign in",
  "Sign in to your ClientExplain AI legal process workspace.",
  "/login",
  true,
);
export const dynamic = "force-dynamic";
export default function Login() {
  return <AuthPage />;
}
