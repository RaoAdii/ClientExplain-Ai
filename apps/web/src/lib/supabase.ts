import { createClient } from "@supabase/supabase-js";
export const authMode = process.env.NEXT_PUBLIC_AUTH_MODE || "development";
const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
export const supabase =
  authMode === "supabase" && url && key
    ? createClient(url, key, {
        auth: { flowType: "pkce", detectSessionInUrl: false },
      })
    : null;
