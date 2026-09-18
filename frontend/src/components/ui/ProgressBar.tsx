type Props = {
  /** 0..1, or null when the engine cannot say yet. */
  value: number | null;
  label: string;
  tone?: "text" | "ready" | "build";
  className?: string;
  thin?: boolean;
};

const fills = {
  text: "bg-text",
  ready: "bg-ready",
  build: "bg-build",
};

/**
 * The only thing allowed to move while a job runs. It fills with a transform,
 * so each update is a compositor step rather than a layout.
 */
export function ProgressBar({ value, label, tone = "text", className = "", thin = false }: Props) {
  const known = value !== null && Number.isFinite(value);
  const clamped = known ? Math.min(1, Math.max(0, value as number)) : 0;
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={known ? Math.round(clamped * 100) : undefined}
      aria-valuetext={known ? `${Math.round(clamped * 100)} percent` : "Working"}
      className={`relative overflow-hidden rounded-full bg-hairline ${thin ? "h-1" : "h-1.5"} ${known ? "" : "hatch-muted"} ${className}`}
    >
      {known ? (
        <div
          className={`motion-progress absolute inset-0 origin-left ${fills[tone]}`}
          style={{ transform: `scaleX(${clamped})` }}
        />
      ) : null}
    </div>
  );
}
