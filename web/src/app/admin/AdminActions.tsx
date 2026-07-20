"use client";

import { useState, useTransition } from "react";
import { BROWSER_API_BASE_URL } from "@/lib/api";

type Props = {
  endpoint: string;
  label: string;
  method?: "POST" | "GET";
  body?: Record<string, unknown>;
  compact?: boolean;
};

export function AdminAction({ endpoint, label, method = "POST", body, compact = false }: Props) {
  const [message, setMessage] = useState<string>("");
  const [isPending, startTransition] = useTransition();

  function run() {
    setMessage("");
    startTransition(async () => {
      try {
        const response = await fetch(`${BROWSER_API_BASE_URL}${endpoint}`, {
          method,
          headers: { "Content-Type": "application/json" },
          body: body ? JSON.stringify(body) : undefined,
        });
        if (!response.ok) {
          const text = await response.text();
          setMessage(`Failed ${response.status}: ${text.slice(0, 120)}`);
          return;
        }
        setMessage("Done. Refresh to see updated data.");
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Request failed");
      }
    });
  }

  return (
    <div className={compact ? "inline-flex flex-col gap-1" : "flex flex-col gap-1"}>
      <button
        type="button"
        onClick={run}
        disabled={isPending}
        className="rounded-md bg-brand-primary px-3 py-2 text-xs font-semibold text-white transition hover:bg-brand-primary-dark disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isPending ? "Working..." : label}
      </button>
      {message && <span className="max-w-xs text-xs text-slate-500">{message}</span>}
    </div>
  );
}
