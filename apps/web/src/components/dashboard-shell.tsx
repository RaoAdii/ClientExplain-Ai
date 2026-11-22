"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  LayoutDashboard,
  FolderOpen,
  Settings,
  LogOut,
  Menu,
  X,
  ShieldCheck,
  ArrowUpRight,
} from "lucide-react";
import { Logo, LoadingState } from "./common";
import { Button } from "./ui/button";
import { useSession } from "@/hooks/use-session";
import { supabase } from "@/lib/supabase";
import { useUI } from "@/stores/ui";

const links = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/projects", label: "Projects", icon: FolderOpen },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];
export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const session = useSession(true);
  const notify = useUI((s) => s.notify);
  async function signOut() {
    try {
      if (supabase) {
        const { error } = await supabase.auth.signOut();
        if (error) throw error;
      } else {
        const result = await fetch("/api/dev-session", { method: "DELETE" });
        if (!result.ok) throw new Error("Unable to sign out. Please retry.");
      }
      queryClient.clear();
      router.replace("/login");
      notify("You are signed out.");
    } catch (error) {
      notify(
        error instanceof Error ? error.message : "Sign-out failed.",
        "error",
      );
    }
  }
  if (session.error)
    return (
      <main id="main" className="container section">
        <h1>Workspace unavailable</h1>
        <p role="alert">{session.error.message}</p>
        <Button onClick={() => session.refetch()}>Try again</Button>
      </main>
    );
  if (!session.data?.authenticated)
    return (
      <main id="main">
        <LoadingState />
      </main>
    );
  return (
    <div className="app-layout">
      <div className="mobile-app-header">
        <Logo />
        <Button
          variant="ghost"
          aria-label={
            open ? "Close workspace navigation" : "Open workspace navigation"
          }
          aria-expanded={open}
          aria-controls="sidebar"
          onClick={() => setOpen(!open)}
        >
          {open ? <X /> : <Menu />}
        </Button>
      </div>
      <aside id="sidebar" className={`sidebar ${open ? "is-open" : ""}`}>
        <div className="sidebar-brand">
          <Logo />
        </div>
        <div className="workspace-label">
          <span className="workspace-avatar">CE</span>
          <div>
            <strong>
              {session.data.local
                ? "Local workspace"
                : session.data.account?.firm.name || "My workspace"}
            </strong>
            <span>Legal process studio</span>
          </div>
        </div>
        <p className="nav-group-label">Workspace</p>
        <nav aria-label="Workspace navigation">
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              onClick={() => setOpen(false)}
              className={
                pathname === href ||
                (href !== "/dashboard" && pathname.startsWith(href + "/"))
                  ? "active"
                  : ""
              }
              aria-current={pathname === href ? "page" : undefined}
            >
              <Icon size={19} />
              {label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="review-note">
            <ShieldCheck size={20} />
            <strong>Professional review first</strong>
            <p>AI explanations require a lawyer’s review before use.</p>
          </div>
          <Link className="sidebar-home" href="/">
            About ClientExplain AI <ArrowUpRight size={16} />
          </Link>
          <Button variant="ghost" onClick={signOut}>
            <LogOut size={17} /> Sign out
          </Button>
        </div>
      </aside>
      <div className="workspace-main">
        <header className="workspace-topbar">
          <span>
            Workspace <span className="breadcrumb-divider">/</span>{" "}
            {links.find((l) => l.href === pathname)?.label || "Project details"}
          </span>
          <span className="small-tag">
            {session.data.local ? "Local development" : "Foundation release"}
          </span>
        </header>
        <main id="main" className="workspace-content">
          {children}
        </main>
        <footer className="workspace-footer">
          <span>© {new Date().getFullYear()} ClientExplain AI</span>
          <div>
            <Link href="/privacy">Privacy</Link>
            <Link href="/terms">Terms</Link>
          </div>
        </footer>
      </div>
    </div>
  );
}
