"use client";
import { useQuery } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase";

export function useSession() {
  return useQuery({
    queryKey: ["session"],
    staleTime: 0,
    queryFn: async () => {
      if (supabase) {
        const { data, error } = await supabase.auth.getSession();
        if (error) throw error;
        return {
          authenticated: !!data.session,
          local: false,
          email: data.session?.user.email,
        };
      }
      const response = await fetch("/api/session", { cache: "no-store" });
      if (!response.ok)
        throw new Error("Unable to check your session. Reload to try again.");
      return (await response.json()) as {
        authenticated: boolean;
        local: boolean;
        email?: string;
      };
    },
  });
}
