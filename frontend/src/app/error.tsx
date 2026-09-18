"use client"; // Error boundaries must be Client Components.

import Link from "next/link";
import { useEffect } from "react";

export default function PageError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <section className="flex flex-col items-start gap-4 py-16">
      <p className="flex items-center gap-2 text-sm text-muted">
        <span aria-hidden className="h-2 w-2 rounded-full bg-build" />
        This page stopped working
      </p>
      <h1 className="heading text-3xl">Something on this page failed to show</h1>
      <p className="max-w-[60ch] text-muted">
        Your projects and files are not affected. Try again, and if it happens again, reload the page or
        go back to the projects list.
      </p>
      {error.message ? (
        <p className="timecode max-w-[80ch] rounded-[var(--radius-control)] border border-hairline bg-panel px-3 py-2 text-sm break-words">
          {error.message}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => retry()}
          className="inline-flex h-10 items-center rounded-[var(--radius-control)] bg-text px-4 text-sm font-semibold text-graphite hover:brightness-110"
        >
          Try again
        </button>
        <Link
          href="/"
          className="inline-flex h-10 items-center rounded-[var(--radius-control)] border border-hairline bg-panel px-4 text-sm hover:border-muted"
        >
          Go to projects
        </Link>
      </div>
    </section>
  );
}
