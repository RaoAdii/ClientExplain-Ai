import Link from "next/link";
import { Navbar, Footer } from "@/components/navigation";
import { Button } from "@/components/ui/button";
import { pageMetadata } from "@/lib/metadata";
export const metadata = pageMetadata(
  "Page not found",
  "This page could not be found. Return to the ClientExplain AI workspace.",
  "/404",
  true,
);
export default function NotFound() {
  return (
    <>
      <Navbar />
      <main id="main" className="container not-found">
        <p className="eyebrow">404 / Page not found</p>
        <h1>This page is out of reach.</h1>
        <p>The link may have changed, or this page may no longer exist.</p>
        <Button asChild>
          <Link href="/">Return to ClientExplain AI</Link>
        </Button>
      </main>
      <Footer />
    </>
  );
}
