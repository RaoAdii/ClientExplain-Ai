"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  isAuthRetryableFetchError,
  isAuthSessionMissingError,
} from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";
import { useUI } from "@/stores/ui";

type Account = {
  profile: { id: string; display_name: string };
  firm: { id: string; name: string };
  role: "owner" | "admin" | "lawyer" | "reviewer";
};
type WorkspaceSession = {
  authenticated: boolean;
  local: boolean;
  email?: string;
  verified?: boolean;
  account?: Account;
};

export function useSession(guard = false) {
  const router = useRouter();
  const client = useQueryClient();
  const notify = useUI((state) => state.notify);
  const [sessionVersion, setSessionVersion] = useState(0);
  const currentUserId = useRef(
    client.getQueryData<WorkspaceSession>(["session", 0])?.account?.profile.id,
  );
  const query = useQuery<WorkspaceSession>({
    queryKey: ["session", sessionVersion],
    staleTime: 0,
    queryFn: async ({ signal }) => {
      if (supabase) {
        const { data, error } = await supabase.auth.getSession();
        if (error) throw error;
        if (!data.session) return { authenticated: false, local: false };
        if (!signal.aborted && currentUserId.current === undefined)
          currentUserId.current = data.session.user.id;
        const { data: identity, error: identityError } =
          await supabase.auth.getUser();
        if (identityError || !identity.user) {
          if (
            identityError &&
            (isAuthRetryableFetchError(identityError) ||
              (!isAuthSessionMissingError(identityError) &&
                identityError.status !== 401 &&
                identityError.status !== 403))
          )
            throw identityError;
          return { authenticated: false, local: false };
        }
        const response = await fetch("/api/backend/auth/me", {
          signal,
          cache: "no-store",
          headers: { Authorization: `Bearer ${data.session.access_token}` },
        });
        if (response.status === 401)
          return { authenticated: false, local: false };
        if (!response.ok)
          throw new Error(
            "Unable to load your account and workspace. Please retry.",
          );
        return {
          authenticated: true,
          local: false,
          email: identity.user.email,
          verified: !!identity.user.email_confirmed_at,
          account: (await response.json()) as Account,
        };
      }
      const response = await fetch("/api/session", {
        signal,
        cache: "no-store",
      });
      if (!response.ok)
        throw new Error("Unable to check your session. Reload to try again.");
      return (await response.json()) as WorkspaceSession;
    },
  });
  useEffect(() => {
    if (!guard || !supabase) return;
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "SIGNED_OUT" || (event === "INITIAL_SESSION" && !session)) {
        currentUserId.current = undefined;
        void client.cancelQueries();
        client.setQueryData<WorkspaceSession>(["session", sessionVersion], {
          authenticated: false,
          local: false,
        });
        client.clear();
        notify("Your session has ended. Sign in again to continue.", "error");
        router.replace("/login?reason=session-expired");
      } else if (
        session &&
        currentUserId.current !== undefined &&
        currentUserId.current !== session.user.id
      ) {
        currentUserId.current = session.user.id;
        void client.cancelQueries();
        client.clear();
        // Rebuild the observer after clearing, hiding the previous user's workspace
        // until the new account has loaded, outside the SDK callback's auth lock.
        setSessionVersion((version) => version + 1);
      } else if (
        event === "INITIAL_SESSION" ||
        event === "SIGNED_IN" ||
        event === "TOKEN_REFRESHED" ||
        event === "USER_UPDATED"
      ) {
        if (session) currentUserId.current = session.user.id;
        // Leave the SDK auth callback before another SDK request acquires its lock.
        setTimeout(() => {
          void client.invalidateQueries({ queryKey: ["session"] });
        }, 0);
      }
    });
    return () => subscription.unsubscribe();
  }, [client, guard, notify, router, sessionVersion]);
  useEffect(() => {
    if (!guard || !query.data || query.data.authenticated) return;
    client.clear();
    notify("Your session has ended. Sign in again to continue.", "error");
    router.replace("/login?reason=session-expired");
  }, [client, guard, notify, query.data, router]);
  return query;
}
