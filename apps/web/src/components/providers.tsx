"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { CheckCircle2, AlertCircle, X } from "lucide-react";
import { useUI } from "@/stores/ui";
import { Button } from "./ui/button";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: 1, staleTime: 15000, refetchOnWindowFocus: false },
        },
      }),
  );
  const { notice, dismiss } = useUI();
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(dismiss, 7000);
    return () => clearTimeout(timer);
  }, [notice, dismiss]);
  return (
    <QueryClientProvider client={client}>
      {children}
      {notice && (
        <div
          className={`toast ${notice.kind}`}
          role={notice.kind === "error" ? "alert" : "status"}
        >
          {notice.kind === "error" ? (
            <AlertCircle size={20} />
          ) : (
            <CheckCircle2 size={20} />
          )}
          <span>{notice.message}</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={dismiss}
            aria-label="Dismiss notification"
          >
            <X size={16} />
          </Button>
        </div>
      )}
    </QueryClientProvider>
  );
}
