import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query";
import { AuthApiError, AuthRetryableFetchError } from "@supabase/supabase-js";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { AuthForm } from "./auth-form";
import {
  AuthCallback,
  ForgotPassword,
  ResetPassword,
} from "./password-recovery";
import { DashboardShell } from "./dashboard-shell";
import { Settings } from "./settings";

const mocks = vi.hoisted(() => ({
  cloud: true,
  push: vi.fn(),
  replace: vi.fn(),
  auth: {
    signUp: vi.fn(),
    signInWithPassword: vi.fn(),
    resetPasswordForEmail: vi.fn(),
    exchangeCodeForSession: vi.fn(),
    updateUser: vi.fn(),
    resend: vi.fn(),
    getSession: vi.fn(),
    getUser: vi.fn(),
    onAuthStateChange: vi.fn(),
    signOut: vi.fn(),
  },
}));
vi.mock("@/lib/supabase", () => ({
  get supabase() {
    return mocks.cloud ? { auth: mocks.auth } : null;
  },
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push, replace: mocks.replace }),
  usePathname: () => "/dashboard/settings",
}));

function mount(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(<QueryClientProvider client={client}>{children}</QueryClientProvider>);
  return client;
}
const user = {
  id: "user-1",
  email: "lawyer@example.com",
  email_confirmed_at: "2026-01-01",
};
beforeEach(() => {
  vi.resetAllMocks();
  mocks.cloud = true;
  window.history.replaceState({}, "", "/");
  mocks.auth.getSession.mockResolvedValue({
    data: { session: { user, access_token: "test-token" } },
    error: null,
  });
  mocks.auth.getUser.mockResolvedValue({ data: { user }, error: null });
  mocks.auth.onAuthStateChange.mockReturnValue({
    data: { subscription: { unsubscribe: vi.fn() } },
  });
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          profile: { id: "user-1", display_name: "Lawyer" },
          firm: { id: "firm-1", name: "Example Legal" },
          role: "lawyer",
        }),
        { status: 200 },
      ),
    ),
  );
});

describe("Account recovery", () => {
  it("sends recovery to a fixed same-origin callback and shows a private success message", async () => {
    mocks.auth.resetPasswordForEmail.mockResolvedValue({
      data: {},
      error: null,
    });
    mount(<ForgotPassword />);
    await userEvent.type(
      screen.getByLabelText("Email address"),
      "lawyer@example.com",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Send reset link" }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      /if an account exists/i,
    );
    expect(mocks.auth.resetPasswordForEmail).toHaveBeenCalledWith(
      "lawyer@example.com",
      {
        redirectTo: `${window.location.origin}/auth/callback?next=/reset-password`,
      },
    );
  });
  it("shows recovery failure and permits retry", async () => {
    mocks.auth.resetPasswordForEmail.mockResolvedValue({
      data: {},
      error: new Error("Please try again later."),
    });
    mount(<ForgotPassword />);
    await userEvent.type(
      screen.getByLabelText("Email address"),
      "lawyer@example.com",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Send reset link" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Please try again later.",
    );
    expect(
      screen.getByRole("button", { name: "Send reset link" }),
    ).toBeEnabled();
  });
  it("does not update a password with mismatched confirmation", async () => {
    mount(<ResetPassword />);
    await userEvent.type(
      await screen.findByLabelText("New password"),
      "new-password",
    );
    await userEvent.type(
      screen.getByLabelText("Confirm new password"),
      "another-password",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Save new password" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(/match/i);
    expect(mocks.auth.updateUser).not.toHaveBeenCalled();
  });
  it("updates a matching password only after checking the session", async () => {
    mocks.auth.updateUser.mockResolvedValue({ data: { user }, error: null });
    mount(<ResetPassword />);
    await userEvent.type(
      await screen.findByLabelText("New password"),
      "new-password",
    );
    await userEvent.type(
      screen.getByLabelText("Confirm new password"),
      "new-password",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Save new password" }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      /password updated/i,
    );
    expect(mocks.auth.updateUser).toHaveBeenCalledWith({
      password: "new-password",
    });
  });
  it("rejects an expired reset session", async () => {
    mocks.auth.getUser.mockResolvedValue({
      data: { user: null },
      error: new Error("Expired"),
    });
    mount(<ResetPassword />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/expired/i);
    expect(
      screen.queryByRole("button", { name: "Save new password" }),
    ).not.toBeInTheDocument();
  });
});

describe("Confirmation callback", () => {
  it("shows an expired callback with recovery links", async () => {
    window.history.replaceState({}, "", "/auth/callback?code=expired");
    mocks.auth.exchangeCodeForSession.mockResolvedValue({
      data: { session: null },
      error: new Error("Expired"),
    });
    mount(<AuthCallback />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /expired|invalid/i,
    );
    expect(screen.getByRole("link", { name: /sign in/i })).toHaveAttribute(
      "href",
      "/login",
    );
    expect(mocks.replace).not.toHaveBeenCalled();
  });
  it.each([
    ["/reset-password", "/reset-password"],
    ["https://evil.test", "/dashboard"],
  ])("handles callback destination %s safely", async (next, expected) => {
    window.history.replaceState(
      {},
      "",
      `/auth/callback?code=valid&next=${encodeURIComponent(next)}`,
    );
    mocks.auth.exchangeCodeForSession.mockResolvedValue({
      data: { session: { user } },
      error: null,
    });
    mount(<AuthCallback />);
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith(expected));
    expect(mocks.auth.exchangeCodeForSession).toHaveBeenCalledWith("valid");
  });
});

describe("Registration and verification", () => {
  it("resends verification for a pending registration", async () => {
    mocks.auth.signUp.mockResolvedValue({
      data: { user, session: null },
      error: null,
    });
    mocks.auth.resend.mockResolvedValue({
      data: { user: null, session: null },
      error: null,
    });
    mount(<AuthForm registering localEnabled={false} />);
    await userEvent.type(
      screen.getByLabelText("Email address"),
      "lawyer@example.com",
    );
    await userEvent.type(screen.getByLabelText("Password"), "new-password");
    await userEvent.click(
      screen.getByRole("button", { name: /create account/i }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: /resend verification/i }),
    );
    expect(await screen.findByText(/verification email sent/i)).toHaveAttribute(
      "role",
      "status",
    );
    expect(mocks.auth.resend).toHaveBeenCalledWith({
      type: "signup",
      email: "lawyer@example.com",
      options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
    });
  });
  it("offers recovery and verification resend from sign-in", () => {
    mount(<AuthForm localEnabled={false} />);
    expect(
      screen.getByRole("link", { name: /forgot password/i }),
    ).toHaveAttribute("href", "/forgot-password");
    expect(
      screen.getByRole("button", { name: /resend verification/i }),
    ).toBeInTheDocument();
  });
});

describe("Workspace session", () => {
  it.each([
    ["offline", new AuthRetryableFetchError("Network unavailable", 0)],
    ["network failure", new TypeError("Failed to fetch")],
    [
      "rate limit",
      new AuthApiError("Too many requests", 429, "over_request_rate_limit"),
    ],
    ["server failure", new AuthRetryableFetchError("Service unavailable", 503)],
  ])("keeps the session and permits retry after %s", async (_, error) => {
    const client = mount(<DashboardShell>Private workspace</DashboardShell>);
    await screen.findByText("Private workspace");
    client.setQueryData(["projects"], [{ name: "Private case" }]);
    mocks.auth.getUser.mockResolvedValueOnce({
      data: { user: null },
      error,
    });
    await act(async () => {
      await client.invalidateQueries({ queryKey: ["session"] });
    });
    expect(await screen.findByRole("alert")).toHaveTextContent(error.message);
    expect(mocks.replace).not.toHaveBeenCalled();
    expect(client.getQueryData(["projects"])).toEqual([
      { name: "Private case" },
    ]);
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          profile: { id: "user-1", display_name: "Lawyer" },
          firm: { id: "firm-1", name: "Example Legal" },
          role: "lawyer",
        }),
        { status: 200 },
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Private workspace")).toBeInTheDocument();
    expect(mocks.replace).not.toHaveBeenCalled();
  });
  it("expires the session after a definitive identity rejection", async () => {
    mocks.auth.getUser.mockResolvedValue({
      data: { user: null },
      error: new AuthApiError("Invalid JWT", 401, "bad_jwt"),
    });
    const client = mount(<DashboardShell>Private workspace</DashboardShell>);
    client.setQueryData(["projects"], [{ name: "Private case" }]);
    await waitFor(() =>
      expect(mocks.replace).toHaveBeenCalledWith(
        "/login?reason=session-expired",
      ),
    );
    expect(client.getQueryData(["projects"])).toBeUndefined();
    expect(screen.queryByText("Private workspace")).not.toBeInTheDocument();
  });
  it.each(["SIGNED_IN", "INITIAL_SESSION", "TOKEN_REFRESHED", "USER_UPDATED"])(
    "cancels old requests and removes private cache before a different user loads on %s",
    async (event) => {
      function PrivateProjects() {
        const projects = useQuery({
          queryKey: ["projects"],
          staleTime: Infinity,
          queryFn: async () => [{ name: "New user's case" }],
        });
        return <p>{projects.data?.[0]?.name}</p>;
      }
      const client = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });
      client.setQueryData(["projects"], [{ name: "Old user's case" }]);
      render(
        <QueryClientProvider client={client}>
          <DashboardShell>
            <PrivateProjects />
          </DashboardShell>
        </QueryClientProvider>,
      );
      await screen.findByText("Old user's case");
      let oldSignal: AbortSignal | undefined;
      let finishOldRequest!: (value: string) => void;
      const oldRequest = client
        .fetchQuery({
          queryKey: ["private-document"],
          queryFn: ({ signal }) => {
            oldSignal = signal;
            return new Promise<string>((resolve) => {
              finishOldRequest = resolve;
            });
          },
        })
        .catch(() => undefined);
      const nextUser = { ...user, id: "user-2", email: "other@example.com" };
      mocks.auth.getSession.mockResolvedValue({
        data: { session: { user: nextUser, access_token: "next-token" } },
        error: null,
      });
      let finishIdentity!: (value: unknown) => void;
      mocks.auth.getUser.mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finishIdentity = resolve;
          }),
      );
      vi.mocked(fetch).mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            profile: { id: "user-2", display_name: "Other lawyer" },
            firm: { id: "firm-2", name: "Other Firm" },
            role: "lawyer",
          }),
          { status: 200 },
        ),
      );
      const callback = mocks.auth.onAuthStateChange.mock.calls.at(-1)![0];
      await act(async () => callback(event, { user: nextUser }));
      await waitFor(() => expect(oldSignal?.aborted).toBe(true));
      expect(client.getQueryData(["projects"])).toBeUndefined();
      expect(screen.queryByText("Old user's case")).not.toBeInTheDocument();
      await act(async () => {
        finishIdentity({ data: { user: nextUser }, error: null });
        finishOldRequest("Old private document");
        await oldRequest;
      });
      expect(await screen.findByText("Other Firm")).toBeInTheDocument();
      expect(await screen.findByText("New user's case")).toBeInTheDocument();
      expect(client.getQueryData(["private-document"])).toBeUndefined();
      expect(mocks.replace).not.toHaveBeenCalled();
    },
  );
  it("preserves private cache when a token refresh keeps the same user", async () => {
    const client = mount(<DashboardShell>Private workspace</DashboardShell>);
    await screen.findByText("Private workspace");
    client.setQueryData(["projects"], [{ name: "Private case" }]);
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          profile: { id: "user-1", display_name: "Lawyer" },
          firm: { id: "firm-1", name: "Updated Legal" },
          role: "lawyer",
        }),
        { status: 200 },
      ),
    );
    const callback = mocks.auth.onAuthStateChange.mock.calls.at(-1)![0];
    await act(async () => callback("TOKEN_REFRESHED", { user }));
    expect(await screen.findByText("Updated Legal")).toBeInTheDocument();
    expect(client.getQueryData(["projects"])).toEqual([
      { name: "Private case" },
    ]);
    expect(mocks.replace).not.toHaveBeenCalled();
  });
  it("shows verified account, firm and role", async () => {
    mount(<Settings />);
    expect(await screen.findByText("Example Legal")).toBeInTheDocument();
    expect(screen.getByText("lawyer@example.com")).toBeInTheDocument();
    expect(screen.getByText("Verified")).toBeInTheDocument();
    expect(screen.getByText("lawyer")).toBeInTheDocument();
  });
  it("clears private cached data and redirects when the SDK expires the session", async () => {
    const client = mount(<DashboardShell>Private workspace</DashboardShell>);
    client.setQueryData(["projects"], [{ name: "Private case" }]);
    await screen.findByText("Private workspace");
    const callback = mocks.auth.onAuthStateChange.mock.calls[0][0];
    await act(async () => callback("SIGNED_OUT", null));
    await waitFor(() =>
      expect(mocks.replace).toHaveBeenCalledWith(
        "/login?reason=session-expired",
      ),
    );
    expect(client.getQueryData(["projects"])).toBeUndefined();
    expect(screen.queryByText("Private workspace")).not.toBeInTheDocument();
  });
  it("hides cloud controls in local mode", async () => {
    mocks.cloud = false;
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ authenticated: true, local: true }), {
        status: 200,
      }),
    );
    mount(
      <>
        <AuthForm localEnabled />
        <ForgotPassword />
        <Settings />
      </>,
    );
    await screen.findByText("Local development session");
    expect(
      screen.queryByRole("button", {
        name: /send reset link|resend verification/i,
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /forgot password|change password/i }),
    ).not.toBeInTheDocument();
  });
});
