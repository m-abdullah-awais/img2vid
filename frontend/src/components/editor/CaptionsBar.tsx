"use client";

import { useId, type ReactNode } from "react";
import { MAX_DISTANCE, distanceText } from "@/lib/captions";
import type { CaptionLook, CaptionPlace, CaptionSize } from "@/lib/types";
import { Segmented } from "../ui/Segmented";
import type { CaptionControl } from "./useCaptions";

type Props = Pick<CaptionControl, "captions" | "change" | "commit">;

const PLACES: { value: CaptionPlace; label: ReactNode }[] = [
  { value: "top", label: "Top" },
  { value: "middle", label: "Middle" },
  { value: "bottom", label: "Bottom" },
];

const LOOKS: { value: CaptionLook; label: ReactNode }[] = [
  { value: "outline", label: "Outline" },
  { value: "band", label: "Band" },
];

const TEXT_SIZES: { value: CaptionSize; label: ReactNode; title: string }[] = [
  { value: "small", label: "S", title: "Small" },
  { value: "medium", label: "M", title: "Medium" },
  { value: "large", label: "L", title: "Large" },
];

/**
 * The captions switch and the four things about them worth changing, on one
 * row above the preview. Everything here shows on the preview as it is
 * pressed, so the row stays quiet: the picture below it is the answer.
 */
export function CaptionsBar({ captions, change, commit }: Props) {
  const note = useId();
  const middle = captions.place === "middle";

  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-hairline px-3 py-2 sm:px-4">
      <Switch
        on={captions.on}
        label="Captions"
        onChange={(on) => change({ on })}
      />

      {captions.on ? (
        <>
          <Pick
            label="Place"
            value={captions.place}
            options={PLACES}
            onChange={(place) => change({ place })}
          />
          <Distance
            value={captions.distance}
            disabled={middle}
            describedBy={middle ? note : undefined}
            onChange={(distance) => change({ distance }, true)}
            onCommit={commit}
          />
          <Pick
            label="Size"
            value={captions.size}
            options={TEXT_SIZES}
            onChange={(size) => change({ size })}
          />
          <Pick
            label="Look"
            value={captions.look}
            options={LOOKS}
            onChange={(look) => change({ look })}
          />
          <p id={note} className="basis-full text-xs text-muted">
            {middle
              ? "Middle is centred in the frame, so distance changes nothing there."
              : "Each line's words are drawn onto its image once, so building takes no longer."}
          </p>
        </>
      ) : (
        <p className="text-xs text-muted">The words of each line, burned into the picture.</p>
      )}
    </div>
  );
}

function Switch({ on, label, onChange }: { on: boolean; label: string; onChange: (on: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={() => onChange(!on)}
      className="group inline-flex shrink-0 items-center gap-2 rounded-[var(--radius-control)] text-sm font-medium"
    >
      <span
        aria-hidden
        className={`inline-flex h-5 w-9 shrink-0 items-center rounded-full border px-[3px] ${
          on ? "justify-end border-text bg-text" : "justify-start border-hairline bg-graphite group-hover:border-muted"
        }`}
      >
        <span className={`h-3 w-3 rounded-full ${on ? "bg-graphite" : "bg-muted"}`} />
      </span>
      {label}
    </button>
  );
}

type PickProps<T extends string> = {
  label: string;
  value: T;
  options: { value: T; label: ReactNode; title?: string }[];
  onChange: (value: T) => void;
};

/** One named set of choices, its name beside it rather than above it. */
function Pick<T extends string>({ label, value, options, onChange }: PickProps<T>) {
  const id = useId();
  return (
    <div className="flex items-center gap-2">
      <span id={id} className="text-sm text-muted">
        {label}
      </span>
      <Segmented label={label} labelledBy={id} value={value} options={options} onChange={onChange} />
    </div>
  );
}

type DistanceProps = {
  value: number;
  disabled: boolean;
  describedBy: string | undefined;
  onChange: (value: number) => void;
  onCommit: () => void;
};

function Distance({ value, disabled, describedBy, onChange, onCommit }: DistanceProps) {
  const id = useId();
  return (
    <div className={`flex items-center gap-2 ${disabled ? "opacity-45" : ""}`}>
      <label htmlFor={id} className="text-sm text-muted">
        Distance
      </label>
      <input
        id={id}
        type="range"
        min={0}
        max={MAX_DISTANCE}
        step={0.5}
        value={value}
        disabled={disabled}
        aria-describedby={describedBy}
        onChange={(event) => onChange(Number(event.target.value))}
        // Letting go of the slider saves at once. Arrow keys do not, on
        // purpose: each one is its own keyup, and committing on those would
        // send a request per step and undo the waiting entirely.
        onPointerUp={onCommit}
        onBlur={onCommit}
        className="h-7 w-28 accent-[var(--color-text)] disabled:cursor-not-allowed"
      />
      <span className="timecode w-11 text-sm text-muted">{distanceText(value)}</span>
    </div>
  );
}
