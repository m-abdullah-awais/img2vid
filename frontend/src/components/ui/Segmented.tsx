"use client";

import type { ReactNode } from "react";

type Option<T extends string> = { value: T; label: ReactNode; title?: string };

type Props<T extends string> = {
  label: string;
  /** The id of a label already on screen, which then names the group instead. */
  labelledBy?: string;
  value: T;
  options: Option<T>[];
  onChange: (value: T) => void;
};

/** A pair or three of toggles where exactly one is on: filters and views. */
export function Segmented<T extends string>({ label, labelledBy, value, options, onChange }: Props<T>) {
  return (
    <div
      role="group"
      aria-label={labelledBy ? undefined : label}
      aria-labelledby={labelledBy}
      className="inline-flex rounded-[var(--radius-control)] border border-hairline p-0.5"
    >
      {options.map((option) => {
        const on = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={on}
            title={option.title}
            onClick={() => onChange(option.value)}
            className={`inline-flex h-7 items-center gap-1.5 rounded-[4px] px-2.5 text-sm ${
              on ? "bg-panel text-text shadow-[inset_0_0_0_1px_var(--color-hairline)]" : "text-muted hover:text-text"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
