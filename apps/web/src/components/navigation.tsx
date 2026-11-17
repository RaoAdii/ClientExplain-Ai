"use client";
import Link from "next/link";
import { useState } from "react";
import { Menu, X, ArrowUpRight } from "lucide-react";
import { Logo } from "./common";
import { Button } from "./ui/button";

export function Navbar() {
  const [open, setOpen] = useState(false);
  return (
    <header className="site-header">
      <div className="container nav-inner">
        <Logo />
        <nav className="desktop-nav" aria-label="Main navigation">
          <Link href="/#workflow">The workflow</Link>
          <Link href="/#principles">Built for review</Link>
        </nav>
        <div className="desktop-nav">
          <Link href="/login">Sign in</Link>
          <Button asChild size="sm">
            <Link href="/register">
              Create an account <ArrowUpRight size={15} />
            </Link>
          </Button>
        </div>
        <Button
          variant="ghost"
          className="mobile-toggle"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          aria-controls="mobile-nav"
          onClick={() => setOpen(!open)}
        >
          {open ? <X /> : <Menu />}
        </Button>
      </div>
      {open && (
        <nav
          id="mobile-nav"
          className="mobile-nav"
          aria-label="Mobile navigation"
          onClick={() => setOpen(false)}
        >
          <Link href="/#workflow">The workflow</Link>
          <Link href="/#principles">Built for review</Link>
          <Link href="/login">Sign in</Link>
          <Link href="/register">Create an account</Link>
        </nav>
      )}
    </header>
  );
}
export function Footer() {
  return (
    <footer className="site-footer">
      <div className="container footer-inner">
        <div>
          <Logo />
          <p>Clarity for clients. Oversight for lawyers.</p>
        </div>
        <nav aria-label="Footer navigation">
          <Link href="/privacy">Privacy Policy</Link>
          <Link href="/terms">Terms and Conditions</Link>
        </nav>
        <p>© {new Date().getFullYear()} ClientExplain AI</p>
      </div>
    </footer>
  );
}
