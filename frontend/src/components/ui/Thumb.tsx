"use client";

import { ImageOff } from "lucide-react";
import { useState } from "react";
import { apiUrl } from "@/lib/api";

type Props = {
  /** A path the API handed back, /api/projects/{id}/images/{name}/thumb?w=320&v=... */
  src: string;
  alt: string;
  className?: string;
  /** Load now rather than when scrolled near, for the few images above the fold. */
  eager?: boolean;
  fit?: "cover" | "contain";
};

/**
 * Every image in the app goes through this one element. Thumbnails come from
 * the local engine at runtime URLs, so a plain <img> is right here: next/image
 * would route them through the optimiser and need images.remotePatterns.
 */
export function Thumb({ src, alt, className = "", eager = false, fit = "cover" }: Props) {
  const [failed, setFailed] = useState<string | null>(null);

  if (failed === src) {
    return (
      <span
        role="img"
        aria-label={`${alt}, could not be shown`}
        className={`flex items-center justify-center bg-graphite text-muted ${className}`}
      >
        <ImageOff size={16} aria-hidden />
      </span>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element -- runtime URLs from the local engine; next/image would need images.remotePatterns in next.config
    <img
      src={apiUrl(src)}
      alt={alt}
      loading={eager ? "eager" : "lazy"}
      decoding="async"
      draggable={false}
      onError={() => setFailed(src)}
      className={`block bg-graphite ${fit === "cover" ? "object-cover" : "object-contain"} ${className}`}
    />
  );
}

/** The same thumbnail URL at another width, 80..640, keeping its version. */
export function thumbAt(thumb: string, width: number): string {
  const [path, query = ""] = thumb.split("?");
  const params = new URLSearchParams(query);
  params.set("w", String(Math.max(80, Math.min(640, Math.round(width)))));
  return `${path}?${params.toString()}`;
}
