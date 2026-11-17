"use client";
import { Button } from "@/components/ui/button";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <section>
      <h1>We couldn’t load this workspace</h1>
      <p>Please try again. Your saved projects are still in the database.</p>
      <Button onClick={reset}>Try again</Button>
    </section>
  );
}
