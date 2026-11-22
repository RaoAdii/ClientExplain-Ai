"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { supabase } from "@/lib/supabase";
import { recoverySchema, resetPasswordSchema } from "@/lib/validation";
import { Field } from "./common";
import { Button } from "./ui/button";

function errorMessage(error: unknown) {
  return error instanceof Error
    ? error.message
    : "The request failed. Please try again.";
}
function SignInLink() {
  return (
    <p>
      <Link href="/login">Back to sign in</Link>
    </p>
  );
}
function Unavailable() {
  return (
    <>
      <p role="status">Account recovery is unavailable in this installation.</p>
      <SignInLink />
    </>
  );
}

export function VerificationResend({ email }: { email: string }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);
  if (!supabase) return null;
  async function resend() {
    setMessage("");
    setFailed(false);
    const parsed = recoverySchema.safeParse({ email });
    if (!parsed.success) {
      setFailed(true);
      setMessage("Enter a valid email address above to resend verification.");
      return;
    }
    setBusy(true);
    try {
      const { error } = await supabase!.auth.resend({
        type: "signup",
        email: parsed.data.email,
        options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
      });
      if (error) throw error;
      setMessage(
        "Verification email sent if your account needs confirmation. Check your inbox.",
      );
    } catch (error) {
      setFailed(true);
      setMessage(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <Button type="button" variant="ghost" disabled={busy} onClick={resend}>
        {busy ? "Sending…" : "Resend verification email"}
      </Button>
      {message && <p role={failed ? "alert" : "status"}>{message}</p>}
    </div>
  );
}

export function ForgotPassword() {
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof recoverySchema>>({
    resolver: zodResolver(recoverySchema),
  });
  if (!supabase) return <Unavailable />;
  async function submit({ email }: z.infer<typeof recoverySchema>) {
    setMessage("");
    setFailed(false);
    try {
      const { error } = await supabase!.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/auth/callback?next=/reset-password`,
      });
      if (error) throw error;
      setMessage(
        "If an account exists for this email, a password reset link is on its way. Check your inbox.",
      );
    } catch (error) {
      setFailed(true);
      setMessage(errorMessage(error));
    }
  }
  return (
    <>
      <form onSubmit={handleSubmit(submit)} noValidate>
        <Field
          label="Email address"
          id="recovery-email"
          error={errors.email?.message}
        >
          <input
            id="recovery-email"
            type="email"
            autoComplete="email"
            {...register("email")}
            aria-invalid={!!errors.email}
            aria-describedby={errors.email ? "recovery-email-error" : undefined}
          />
        </Field>
        <Button disabled={isSubmitting}>
          {isSubmitting ? "Sending…" : "Send reset link"}
        </Button>
      </form>
      {message && <p role={failed ? "alert" : "status"}>{message}</p>}
      <SignInLink />
    </>
  );
}

export function ResetPassword() {
  const [access, setAccess] = useState<"checking" | "ready" | "expired">(
    "checking",
  );
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);
  const [complete, setComplete] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof resetPasswordSchema>>({
    resolver: zodResolver(resetPasswordSchema),
  });
  useEffect(() => {
    if (!supabase) return;
    let active = true;
    void supabase.auth
      .getUser()
      .then(({ data, error }) => {
        if (active) setAccess(!error && data.user ? "ready" : "expired");
      })
      .catch(() => {
        if (active) setAccess("expired");
      });
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "SIGNED_OUT" || !session) setAccess("expired");
    });
    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, []);
  if (!supabase) return <Unavailable />;
  async function submit({ password }: z.infer<typeof resetPasswordSchema>) {
    setMessage("");
    setFailed(false);
    try {
      const { data, error: sessionError } = await supabase!.auth.getUser();
      if (sessionError || !data.user) {
        setAccess("expired");
        return;
      }
      const { error } = await supabase!.auth.updateUser({ password });
      if (error) throw error;
      setComplete(true);
      setMessage(
        "Password updated. You can return to sign in with your new password.",
      );
    } catch (error) {
      setFailed(true);
      setMessage(errorMessage(error));
    }
  }
  return (
    <>
      {access === "checking" && <p role="status">Checking your reset link…</p>}
      {access === "expired" && (
        <p role="alert">
          Your reset link is invalid or expired.{" "}
          <Link href="/forgot-password">Request a new reset link</Link>.
        </p>
      )}
      {access === "ready" && !complete && (
        <form onSubmit={handleSubmit(submit)} noValidate>
          <Field
            label="New password"
            id="new-password"
            error={errors.password?.message}
            hint="Use at least 8 characters."
          >
            <input
              id="new-password"
              type="password"
              autoComplete="new-password"
              {...register("password")}
              aria-invalid={!!errors.password}
              aria-describedby={
                errors.password ? "new-password-error" : "new-password-hint"
              }
            />
          </Field>
          <Field
            label="Confirm new password"
            id="confirmation"
            error={errors.confirmation?.message}
          >
            <input
              id="confirmation"
              type="password"
              autoComplete="new-password"
              {...register("confirmation")}
              aria-invalid={!!errors.confirmation}
              aria-describedby={
                errors.confirmation ? "confirmation-error" : undefined
              }
            />
          </Field>
          <Button disabled={isSubmitting}>
            {isSubmitting ? "Saving…" : "Save new password"}
          </Button>
        </form>
      )}
      {message && <p role={failed ? "alert" : "status"}>{message}</p>}
      <SignInLink />
    </>
  );
}

export function AuthCallback() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [failed, setFailed] = useState(false);
  const exchange = useRef<Promise<void> | null>(null);
  useEffect(() => {
    // Reuse the exchange when React replays effects; a PKCE code is single-use.
    exchange.current ??= (async () => {
      const params = new URLSearchParams(window.location.search);
      const code = params.get("code");
      if (!supabase || !code || params.has("error"))
        throw new Error("Invalid callback");
      const { data, error } = await supabase.auth.exchangeCodeForSession(code);
      if (error || !data.session) throw new Error("Expired callback");
      queryClient.clear();
      router.replace(
        params.get("next") === "/reset-password"
          ? "/reset-password"
          : "/dashboard",
      );
    })();
    let active = true;
    void exchange.current.catch(() => {
      if (active) setFailed(true);
    });
    return () => {
      active = false;
    };
  }, [queryClient, router]);
  return (
    <>
      {failed ? (
        <p role="alert">
          This confirmation link is invalid or expired. Request another
          verification email from sign-in, or{" "}
          <Link href="/forgot-password">request a new password reset link</Link>
          .
        </p>
      ) : (
        <p role="status">Confirming your account link…</p>
      )}
      <SignInLink />
    </>
  );
}
