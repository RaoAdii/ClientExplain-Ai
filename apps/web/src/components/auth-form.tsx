"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, ShieldCheck } from "lucide-react";
import {
  loginSchema,
  registrationSchema,
  type AuthInput,
} from "@/lib/validation";
import { supabase } from "@/lib/supabase";
import { useUI } from "@/stores/ui";
import { Button } from "./ui/button";
import { Field } from "./common";
import { VerificationResend } from "./password-recovery";

export function AuthForm({
  registering,
  localEnabled,
}: {
  registering?: boolean;
  localEnabled: boolean;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const notify = useUI((s) => s.notify);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const [pendingEmail, setPendingEmail] = useState("");
  const {
    register,
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<AuthInput>({
    resolver: zodResolver(registering ? registrationSchema : loginSchema),
  });
  const email = useWatch({ control, name: "email", defaultValue: "" });
  async function submit(input: AuthInput) {
    setMessage("");
    setFailed(false);
    if (!supabase) {
      setMessage("Account sign-in is not configured for this installation.");
      return;
    }
    try {
      const result = registering
        ? await supabase.auth.signUp({
            ...input,
            options: {
              emailRedirectTo: `${window.location.origin}/auth/callback`,
            },
          })
        : await supabase.auth.signInWithPassword(input);
      if (result.error) throw result.error;
      if (registering && !result.data.session) {
        setPendingEmail(input.email);
        setMessage(
          "Check your email to confirm your account, then return to sign in.",
        );
        return;
      }
      notify(registering ? "Account created." : "You are signed in.");
      queryClient.clear();
      router.push("/dashboard");
    } catch (error) {
      setFailed(true);
      setMessage(
        error instanceof Error
          ? error.message
          : "Sign-in failed. Please try again.",
      );
    }
  }
  async function enterLocal() {
    setBusy(true);
    setMessage("");
    try {
      const result = await fetch("/api/dev-session", { method: "POST" });
      if (!result.ok)
        throw new Error(
          "Local sign-in is unavailable. Check the development configuration.",
        );
      notify("Local workspace opened. Use non-confidential test information.");
      queryClient.clear();
      router.push("/dashboard");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to open the local workspace.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-form-wrap">
      {supabase ? (
        <form onSubmit={handleSubmit(submit)} noValidate>
          <Field label="Email address" id="email" error={errors.email?.message}>
            <input
              id="email"
              type="email"
              autoComplete="email"
              {...register("email")}
              aria-invalid={!!errors.email}
              aria-describedby={errors.email ? "email-error" : undefined}
            />
          </Field>
          <Field
            label="Password"
            id="password"
            error={errors.password?.message}
            hint={registering ? "Use at least 8 characters." : undefined}
          >
            <input
              id="password"
              type="password"
              autoComplete={registering ? "new-password" : "current-password"}
              {...register("password")}
              aria-invalid={!!errors.password}
              aria-describedby={errors.password ? "password-error" : undefined}
            />
          </Field>
          <Button className="full-width" disabled={isSubmitting}>
            {isSubmitting
              ? "Please wait…"
              : registering
                ? "Create account"
                : "Sign in"}
            <ArrowRight size={16} />
          </Button>
        </form>
      ) : (
        <div className="info-box">
          <ShieldCheck size={21} />
          <div>
            <strong>Account access is not connected yet</strong>
            <p>
              Supabase account registration and sign-in will be available when
              authentication is configured for this installation.
            </p>
          </div>
        </div>
      )}
      {message && (
        <p className="form-message" role={failed ? "alert" : "status"}>
          {message}
        </p>
      )}
      {supabase && (!registering || pendingEmail) && (
        <>
          {!registering && (
            <p>
              <Link href="/forgot-password">Forgot password?</Link>
            </p>
          )}
          <VerificationResend email={pendingEmail || email} />
        </>
      )}
      {localEnabled && (
        <div className="local-access">
          <p className="eyebrow">Local development</p>
          <p>
            Explore a persistent workspace on this computer. This does not
            create an account. Use non-confidential test information only.
          </p>
          <Button
            variant="outline"
            className="full-width"
            onClick={enterLocal}
            disabled={busy}
          >
            {busy ? "Opening…" : "Open local workspace"}
            <ArrowRight size={16} />
          </Button>
        </div>
      )}
      <p className="auth-switch">
        {registering ? "Already have an account?" : "New to ClientExplain AI?"}{" "}
        <Link href={registering ? "/login" : "/register"}>
          {registering ? "Sign in" : "Create an account"}
        </Link>
      </p>
      <p className="fine-print">
        By using this workspace, you acknowledge the{" "}
        <Link href="/terms">draft Terms</Link> and{" "}
        <Link href="/privacy">draft Privacy Policy</Link>.
      </p>
    </div>
  );
}
