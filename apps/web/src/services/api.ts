import { supabase } from "@/lib/supabase";
export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}
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
    const message = response.status === 403
      ? "You no longer have permission to perform this action. Refresh your workspace or contact an administrator."
      : response.status === 404
        ? "This resource was not found or is no longer available in your workspace."
        : data?.error?.message || "The request could not be completed. Please try again.";
    throw new ApiError(message, response.status);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
