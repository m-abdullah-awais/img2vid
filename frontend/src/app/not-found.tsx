import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Not found",
};

export default function NotFound() {
  return (
    <section className="flex flex-col items-start gap-4 py-16">
      <h1 className="heading text-3xl">There is no page at this address</h1>
      <p className="max-w-[60ch] text-muted">
        The link may be old, or the address mistyped. Everything in img2vid starts from the projects list.
      </p>
      <Link
        href="/"
        className="inline-flex h-10 items-center rounded-[var(--radius-control)] bg-text px-4 text-sm font-semibold text-graphite hover:brightness-110"
      >
        Go to projects
      </Link>
    </section>
  );
}
