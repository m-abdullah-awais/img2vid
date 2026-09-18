"use client";

import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { API_BASE, ENGINE_DOWN } from "@/lib/api";
import { Button } from "./Button";

/** The whole page, when nothing answers at the API address. */
export function EngineDown({ onRetry }: { onRetry: () => void | Promise<void> }) {
  const [trying, setTrying] = useState(false);
  return (
    <section className="flex min-h-[60vh] flex-col items-start justify-center gap-5 py-16">
      <div className="flex items-center gap-2 text-sm text-muted">
        <span aria-hidden className="h-2 w-2 rounded-full bg-build" />
        Nothing answers at {API_BASE}
      </div>
      <h1 className="heading text-3xl">
        {ENGINE_DOWN.split(/(?<=\.) /).map((sentence) => (
          <span key={sentence} className="block">
            {sentence}{" "}
          </span>
        ))}
      </h1>
      <p className="max-w-[60ch] text-muted">
        Run.bat starts the engine and this app together. Keep its window open while you work, then
        come back here and retry. If it is already open, close it and start it again.
      </p>
      <Button
        variant="primary"
        disabled={trying}
        onClick={async () => {
          setTrying(true);
          try {
            await onRetry();
          } finally {
            setTrying(false);
          }
        }}
      >
        <RefreshCw size={16} aria-hidden />
        {trying ? "Retrying" : "Retry"}
      </Button>
    </section>
  );
}
