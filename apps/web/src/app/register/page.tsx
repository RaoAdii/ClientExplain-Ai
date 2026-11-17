import { AuthPage } from "@/components/auth-page";
import { pageMetadata } from "@/lib/metadata";
export const metadata = pageMetadata(
  "Create an account",
  "Create a ClientExplain AI account to organize legal process projects.",
  "/register",
  true,
);
export const dynamic = "force-dynamic";
export default function Register() {
  return <AuthPage registering />;
}
