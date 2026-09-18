import type { StepState, Tone } from "@/lib/types";

/** Status text colour. Amber for anything that wants attention, green once done. */
export const toneText: Record<Tone, string> = {
  ready: "text-ready",
  attention: "text-missing",
  missing: "text-missing",
  busy: "text-text",
  idle: "text-muted",
};

export const toneDot: Record<Tone, string> = {
  ready: "bg-ready",
  attention: "bg-missing",
  missing: "bg-missing",
  busy: "bg-text",
  idle: "bg-muted",
};

/** A step not started yet is quiet, not amber: a new project is not a warning. */
export const stepDot: Record<StepState, string> = {
  ready: "bg-ready",
  attention: "bg-missing",
  missing: "border border-muted bg-transparent",
  busy: "bg-text",
};

export const stepText: Record<StepState, string> = {
  ready: "text-text",
  attention: "text-missing",
  missing: "text-muted",
  busy: "text-text",
};
