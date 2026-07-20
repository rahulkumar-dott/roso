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

export function CreateCountryForm() {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  function submit() {
    const trimmedName = name.trim();
    if (!trimmedName) {
      setMessage("Country name is required.");
      return;
    }
    setMessage("");
    startTransition(async () => {
      try {
        const response = await fetch(`${BROWSER_API_BASE_URL}/admin/countries`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: trimmedName,
            description: description.trim() || undefined,
          }),
        });
        if (!response.ok) {
          const text = await response.text();
          setMessage(`Failed ${response.status}: ${text.slice(0, 140)}`);
          return;
        }
        setName("");
        setDescription("");
        setMessage("Country created. Refresh to see it in the list.");
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Request failed");
      }
    });
  }

  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
      <div className="grid gap-3 md:grid-cols-[minmax(160px,1fr)_minmax(220px,2fr)_auto]">
        <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">
          Country
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Austria"
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-normal text-brand-navy outline-none focus:border-brand-primary"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-semibold text-slate-600">
          Internal note
          <input
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Optional taxonomy note"
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-normal text-brand-navy outline-none focus:border-brand-primary"
          />
        </label>
        <button
          type="button"
          onClick={submit}
          disabled={isPending}
          className="self-end rounded-md bg-brand-primary px-3 py-2 text-xs font-semibold text-white transition hover:bg-brand-primary-dark disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isPending ? "Creating..." : "Create country"}
        </button>
      </div>
      {message && <p className="mt-2 text-xs text-slate-500">{message}</p>}
    </div>
  );
}
