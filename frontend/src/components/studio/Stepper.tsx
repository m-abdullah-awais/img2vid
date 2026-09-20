"use client";

import { Check } from "lucide-react";
import { memo } from "react";
import type { Marker, MarkerState, StepNumber } from "@/lib/stage";

type Props = {
  markers: Marker[];
  /** The step whose panel is on screen. */
  shown: StepNumber;
  /** The step the project is really on. Nothing past it can be opened. */
  here: StepNumber;
  onSelect: (step: StepNumber) => void;
};

const square: Record<MarkerState, string> = {
  done: "bg-ready text-ink",
  attention: "bg-missing text-ink",
  current: "bg-text text-graphite",
  ahead: "border border-hairline text-muted",
};

const titleTone: Record<MarkerState, string> = {
  done: "text-text",
  attention: "text-text",
  current: "text-text",
  ahead: "text-muted",
};

const stateWords: Record<MarkerState, string> = {
  done: "done",
  attention: "needs attention",
  current: "the step this project is on",
  ahead: "not ready yet",
};

/**
 * The four steps as four squares on a strip. Squares, at the same 2px corner
 * as every thumbnail and clip here, so the path reads as shots in order
 * rather than as a wizard. All four are always visible: the whole path is
 * worth seeing even though only the one you are on can be used.
 */
export const Stepper = memo(function Stepper({ markers, shown, here, onSelect }: Props) {
  const showing = markers.find((marker) => marker.step === shown) ?? markers[0];

  return (
    <nav aria-label="Steps" className="flex flex-col gap-3">
      {/* Capped, so the four squares read as one strip instead of four
          corners of a wide page. */}
      <ol className="grid max-w-[880px] grid-cols-4 gap-x-2 sm:gap-x-3">
        {markers.map((marker, index) => {
          const open = marker.step <= here;
          const isShown = marker.step === shown;
          const filled = marker.step < here;
          return (
            <li
              key={marker.step}
              className="relative min-w-0"
              aria-current={marker.step === here ? "step" : undefined}
            >
              {index < markers.length - 1 ? (
                <span
                  aria-hidden
                  className={`absolute top-3 -right-2 left-7 h-px sm:top-[14px] sm:-right-3 sm:left-9 ${
                    filled ? (marker.state === "attention" ? "bg-missing" : "bg-ready") : "bg-hairline"
                  }`}
                />
              ) : null}
              <button
                type="button"
                aria-disabled={open ? undefined : true}
                aria-label={`Step ${marker.step}, ${marker.title}, ${stateWords[marker.state]}.${
                  !open ? "" : isShown ? " Showing." : marker.step < here ? " Go back to it." : " Show it."
                }`}
                onClick={open ? () => onSelect(marker.step) : undefined}
                className={`group flex w-full min-w-0 flex-col items-start gap-1.5 rounded-[var(--radius-control)] text-left ${
                  open ? "cursor-pointer" : "cursor-default"
                }`}
              >
                <span
                  className={`timecode flex h-6 w-6 shrink-0 items-center justify-center rounded-[var(--radius-frame)] text-sm sm:h-7 sm:w-7 sm:text-base ${
                    square[marker.state]
                  } ${isShown && shown !== here ? "ring-1 ring-text ring-offset-2 ring-offset-graphite" : ""}`}
                >
                  {marker.state === "done" ? (
                    <Check size={15} strokeWidth={3} aria-hidden />
                  ) : (
                    <span aria-hidden>{marker.step}</span>
                  )}
                </span>
                <span className="hidden min-w-0 flex-col sm:flex">
                  <span
                    className={`truncate text-sm font-semibold ${titleTone[marker.state]} ${
                      open ? "group-hover:underline group-hover:decoration-hairline group-hover:underline-offset-4" : ""
                    }`}
                  >
                    {marker.title}
                  </span>
                  {marker.summary ? (
                    <span className="truncate text-sm text-muted" title={marker.summary}>
                      {marker.summary}
                    </span>
                  ) : null}
                  {marker.meta ? (
                    <span
                      className={`timecode truncate text-xs ${
                        marker.state === "attention" ? "text-missing" : "text-muted"
                      }`}
                      title={marker.meta}
                    >
                      {marker.meta}
                    </span>
                  ) : null}
                </span>
              </button>
            </li>
          );
        })}
      </ol>

      {/* At phone width only the step on screen keeps its words, so the row
          of squares never wraps or scrolls. */}
      <p className="flex flex-wrap items-baseline gap-x-2 sm:hidden">
        <span className="text-sm font-semibold">{showing.title}</span>
        {showing.summary ? <span className="text-sm text-muted">{showing.summary}</span> : null}
        {showing.meta ? (
          <span className={`timecode text-xs ${showing.state === "attention" ? "text-missing" : "text-muted"}`}>
            {showing.meta}
          </span>
        ) : null}
      </p>
    </nav>
  );
});
