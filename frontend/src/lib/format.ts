// Every number the interface shows goes through here, so a timecode reads the
// same in the timeline, the storyboard and the build dialog.

/** m:ss.s, the storyboard's timecode. 32.46 becomes 0:32.4. */
export function timecode(seconds: number): string {
  const tenths = Math.max(0, Math.floor(seconds * 10 + 1e-6));
  const minutes = Math.floor(tenths / 600);
  const rest = (tenths % 600) / 10;
  return `${minutes}:${rest.toFixed(1).padStart(4, "0")}`;
}

/** m:ss, or h:mm:ss past the hour. For lengths of narration and video. */
export function clock(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return "";
  const whole = Math.max(0, Math.round(seconds));
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const secs = String(whole % 60).padStart(2, "0");
  if (hours) return `${hours}:${String(minutes).padStart(2, "0")}:${secs}`;
  return `${minutes}:${secs}`;
}

/** 2.7s, for the length of one line. */
export function shortSeconds(seconds: number): string {
  if (seconds >= 10) return `${seconds.toFixed(0)}s`;
  return `${seconds.toFixed(1)}s`;
}

export function bytes(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "";
  if (value < 1024) return `${value} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let size = value / 1024;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  const digits = size >= 100 || unit === 0 ? 0 : 1;
  return `${size.toFixed(digits)} ${units[unit]}`;
}

/** 001, 012, 170: line numbers at a fixed width so they line up. */
export function pad(value: number, width = 3): string {
  return String(value).padStart(width, "0");
}

export function plural(count: number, one: string, many = `${one}s`): string {
  return `${count} ${count === 1 ? one : many}`;
}

/** 45s, 3m 05s, 1h 02m. For elapsed time and time left. */
export function duration(seconds: number): string {
  const whole = Math.max(0, Math.round(seconds));
  if (whole < 60) return `${whole}s`;
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const secs = whole % 60;
  if (hours) return `${hours}h ${String(minutes).padStart(2, "0")}m`;
  return `${minutes}m ${String(secs).padStart(2, "0")}s`;
}

const dateFormat = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/** 18 Sep 2026, 14:02 in local time. */
export function stamp(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return dateFormat.format(date);
}

/** "5 minutes ago", falling back to the date after a week. */
export function relative(iso: string | null | undefined, now: number): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.round((now - then) / 1000);
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${plural(minutes, "minute")} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${plural(hours, "hour")} ago`;
  const days = Math.round(hours / 24);
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  return stamp(iso);
}

/** Collapse the engine's console indentation into one readable paragraph. */
export function prose(text: string | null | undefined): string {
  if (!text) return "";
  return text
    .split(/\r?\n/)
    .map((part) => part.trim())
    .filter(Boolean)
    .join(" ")
    .replace(/\s{2,}/g, " ");
}

/**
 * The engine's console text as readable lines. Its messages are wrapped at 80
 * columns for a terminal: a line that stops mid-sentence and a next line that
 * starts in lower case are one sentence, anything else keeps its own line.
 */
export function paragraphs(text: string | null | undefined): string {
  if (!text) return "";
  const lines = text
    .split(/\r?\n/)
    .map((part) => part.trim())
    .filter(Boolean);
  let out = "";
  for (const line of lines) {
    if (!out) {
      out = line;
      continue;
    }
    const joins = !/[.!?:;]$/.test(out) && /^[a-z(]/.test(line);
    out += joins ? ` ${line}` : `\n${line}`;
  }
  return out;
}

/** The first words of a line of narration, for lists that must stay short. */
export function snippet(text: string, length = 90): string {
  const clean = text.replace(/\s+/g, " ").trim();
  if (clean.length <= length) return clean;
  const cut = clean.slice(0, length);
  const space = cut.lastIndexOf(" ");
  return `${cut.slice(0, space > 40 ? space : length).trimEnd()}...`;
}

/** The number a filename starts with, or null. "004. two men.jpg" is 4. */
export function leadingNumber(name: string): number | null {
  const match = /^(\d+)/.exec(name);
  return match ? Number(match[1]) : null;
}

/** Natural name order, so 2.jpg sorts before 10.jpg. */
export const naturalCompare = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" })
  .compare;
