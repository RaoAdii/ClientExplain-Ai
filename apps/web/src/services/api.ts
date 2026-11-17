import { supabase } from "@/lib/supabase";
export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const session = supabase
    ? (await supabase.auth.getSession()).data.session
    : null;
  const response = await fetch(`/api/backend/${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(session ? { Authorization: `Bearer ${session.access_token}` } : {}),
      ...options?.headers,
    },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(
      data?.error?.message ||
        "The request could not be completed. Please try again.",
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
