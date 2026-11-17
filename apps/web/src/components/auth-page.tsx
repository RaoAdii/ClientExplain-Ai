import { Navbar, Footer } from "./navigation";
import { AuthForm } from "./auth-form";
import { ShieldCheck } from "lucide-react";
import { authMode } from "@/lib/supabase";

export function AuthPage({ registering = false }: { registering?: boolean }) {
  return (
    <>
      <Navbar />
      <main id="main" className="auth-main container">
        <aside className="auth-aside">
          <p className="eyebrow">The legal process workspace</p>
          <h2>Clear explanations start with organized thinking.</h2>
          <p>
            A dedicated place for the context, purpose, and jurisdiction behind
            each client explanation.
          </p>
          <div className="auth-review">
            <ShieldCheck size={24} />
            <p>
              Professional review is always required for AI-generated legal
              explanations.
            </p>
          </div>
        </aside>
        <section className="auth-card">
          <p className="eyebrow">ClientExplain AI</p>
          <h1>{registering ? "Create your workspace" : "Welcome back"}</h1>
          <p className="muted">
            {registering
              ? "Start organizing your legal process projects."
              : "Sign in to continue your project work."}
          </p>
          <AuthForm
            registering={registering}
            localEnabled={authMode === "development"}
          />
        </section>
      </main>
      <Footer />
    </>
  );
}
