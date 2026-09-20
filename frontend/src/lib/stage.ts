// Which step the project is really on, worked out from the project itself
// rather than from what was clicked. A reload, a second tab, or a job that
// finished while nobody was looking all land on the same step, and the words
// here are the words the projects list uses.

import { clock, plural } from "./format";
import type { Blocker, Project } from "./types";

export type StepNumber = 1 | 2 | 3 | 4;
export type StageNumber = 1 | 2 | 3 | 4 | 5;

/** done: finished. current: where the project is. ahead: not reachable yet. */
export type MarkerState = "done" | "current" | "ahead" | "attention";

export const STEP_TITLES: Record<StepNumber, string> = {
  1: "Narration",
  2: "Transcript",
  3: "Images",
  4: "Video",
};

export type Marker = {
  step: StepNumber;
  title: string;
  state: MarkerState;
  /** One line under the title. Null on a step that cannot be reached yet. */
  summary: string | null;
  /** A second, quieter line: a length, or what wants attention. */
  meta: string | null;
};

export type Stage = {
  number: StageNumber;
  /** The marker this stage belongs to. Stages 4 and 5 are both step 4. */
  step: StepNumber;
  title: string;
  message: string;
  /** Why Build video cannot run, in a few words. Null when it can. */
  blocked: string | null;
  markers: Marker[];
};

export function hasAudio(project: Project): boolean {
  return project.audio.files.length > 0;
}

/** Audio that ffmpeg could measure. Without a length there is no timeline. */
export function audioReadable(project: Project): boolean {
  return hasAudio(project) && project.audio.seconds !== null;
}

/** A transcript with lines in it. A file that cannot be read has none. */
export function transcriptReadable(project: Project): boolean {
  return Boolean(project.transcript) && project.storyboard.length > 0;
}

export function blockerOf(project: Project, code: string): Blocker | null {
  return project.blockers.find((blocker) => blocker.code === code) ?? null;
}

/** The engine's first sentence about a problem, for a place with one line to spare. */
export function firstLine(message: string): string {
  return message.split(/\r?\n/)[0].trim();
}

/** "4", "4 and 17", "4, 17 and 52", "4, 17, 52 and 9 more". */
export function listNumbers(numbers: number[], most = 12): string {
  if (!numbers.length) return "";
  if (numbers.length > most) {
    const shown = numbers.slice(0, most).join(", ");
    return `${shown} and ${numbers.length - most} more`;
  }
  if (numbers.length === 1) return String(numbers[0]);
  const last = numbers[numbers.length - 1];
  return `${numbers.slice(0, -1).join(", ")} and ${last}`;
}

/** "1 line still needs an image", "3 lines still need an image". */
export function emptyLineCount(count: number): string {
  return `${plural(count, "line")} still ${count === 1 ? "needs" : "need"} an image`;
}

export function duplicateReason(project: Project): string | null {
  const duplicates = project.images.duplicates;
  if (!duplicates.length) return null;
  if (duplicates.length === 1) return `Two images claim line ${duplicates[0].line}`;
  return `${duplicates.length} lines are claimed by more than one image`;
}

/** Images paired in filename order, so one gap moves everything after it. */
export function pairedByPosition(project: Project): boolean {
  return (
    project.images.mode === "positional" &&
    project.images.total > 0 &&
    project.storyboard.length > 0
  );
}

export function stageNumber(project: Project): StageNumber {
  if (!audioReadable(project)) return 1;
  if (!transcriptReadable(project)) return 2;
  if (project.images.missing.length || project.images.duplicates.length) return 3;
  if (!project.videos.length) return 4;
  return 5;
}

/** Why Build video is disabled, said in the fewest words that still help. */
export function buildBlocked(project: Project): string | null {
  // Short enough to read beside the button. The step's own panel carries the
  // engine's whole sentence about it.
  if (!hasAudio(project)) return "Add your narration first";
  if (!audioReadable(project)) return "The narration cannot be read";
  if (!project.transcript) return "Transcribe the narration first";
  if (!transcriptReadable(project)) return "The transcript cannot be read";
  const duplicate = duplicateReason(project);
  if (duplicate) return duplicate;
  if (project.images.missing.length) return emptyLineCount(project.images.missing.length);
  if (project.blockers.length) return firstLine(project.blockers[0].message);
  return null;
}

function narrationMarker(project: Project): Omit<Marker, "state"> {
  const files = project.audio.files;
  const length = project.audio.seconds !== null ? clock(project.audio.seconds) : null;
  if (!files.length) return { step: 1, title: STEP_TITLES[1], summary: "No audio yet", meta: null };
  if (!audioReadable(project)) {
    return { step: 1, title: STEP_TITLES[1], summary: plural(files.length, "audio file"), meta: "Cannot be read" };
  }
  return {
    step: 1,
    title: STEP_TITLES[1],
    summary: files.length === 1 ? files[0].name : `${files.length} files`,
    meta: length,
  };
}

function transcriptMarker(project: Project, transcribing: boolean): Omit<Marker, "state"> {
  const base = { step: 2 as const, title: STEP_TITLES[2] };
  if (transcribing) return { ...base, summary: "Being made now", meta: null };
  if (!project.transcript) return { ...base, summary: "No transcript yet", meta: null };
  if (!transcriptReadable(project)) {
    return { ...base, summary: project.transcript.name, meta: "Cannot be read" };
  }
  return {
    ...base,
    summary: plural(project.storyboard.length, "line"),
    meta: project.transcript.stale ? "Narration changed since" : null,
  };
}

function imagesMarker(project: Project): Omit<Marker, "state"> {
  const base = { step: 3 as const, title: STEP_TITLES[3] };
  const lines = project.storyboard.length;
  if (!lines) return { ...base, summary: plural(project.images.total, "image"), meta: null };
  const placed = lines - project.images.missing.length;
  const duplicate = duplicateReason(project);
  return {
    ...base,
    summary: `${placed} of ${lines}`,
    meta: duplicate ? duplicate : pairedByPosition(project) ? "Paired in name order" : null,
  };
}

function videoMarker(project: Project, rendering: boolean): Omit<Marker, "state"> {
  const base = { step: 4 as const, title: STEP_TITLES[4] };
  if (rendering) return { ...base, summary: "Being built now", meta: null };
  const newest = project.videos[0];
  if (!newest) return { ...base, summary: "Not built yet", meta: null };
  return {
    ...base,
    summary: plural(project.videos.length, "video"),
    meta: newest.outdated ? "Out of date" : clock(newest.seconds),
  };
}

/** A step past or at the current one can want attention. Ahead of it, nothing has happened. */
function attention(project: Project, step: StepNumber): boolean {
  if (step === 1) return hasAudio(project) && !audioReadable(project);
  if (step === 2) {
    if (!project.transcript) return false;
    return !transcriptReadable(project) || project.transcript.stale;
  }
  if (step === 3) {
    if (!project.storyboard.length) return false;
    return project.images.duplicates.length > 0 || pairedByPosition(project);
  }
  return Boolean(project.videos[0]?.outdated);
}

function markerState(step: StepNumber, stage: StageNumber, flagged: boolean): MarkerState {
  const step4Done = stage === 5;
  const done = step < stepOfStage(stage) || (step === 4 && step4Done);
  if (step > stepOfStage(stage)) return "ahead";
  if (flagged) return "attention";
  return done ? "done" : "current";
}

export function stepOfStage(stage: StageNumber): StepNumber {
  return stage === 5 ? 4 : (stage as StepNumber);
}

/** The panel's heading and paragraph, with every number read from the project. */
function copy(project: Project, stage: StageNumber): { title: string; message: string } {
  const lines = project.storyboard.length;
  if (stage === 1) {
    return {
      title: "Start with your narration.",
      message:
        "Everything follows from it: img2vid listens to the narration, writes down what is said and when, and holds one image on screen for each line. Several files are joined in the order their names sort.",
    };
  }
  if (stage === 2) {
    const length = project.audio.seconds !== null ? clock(project.audio.seconds) : null;
    const yours = length ? ` This narration is ${length} long.` : "";
    return {
      title: "Turn the narration into lines.",
      message: `Each line becomes one image, so this also decides how many images the video needs. It runs on this computer, about a minute of work for every six minutes of narration.${yours}`,
    };
  }
  if (stage === 3) {
    const missing = project.images.missing;
    const placed = lines - missing.length;
    const clashes = project.images.duplicates.length;
    if (!missing.length && clashes) {
      const many = clashes > 1;
      return {
        title: "Give every line one image.",
        message: `All ${lines} lines have an image, but ${
          many ? `${clashes} of them are claimed by two images each` : "one of them is claimed by two images"
        }. Move or remove the extra ${many ? "ones" : "one"} and the video can be built.`,
      };
    }
    // Naming the empty lines only helps while there are few enough to read.
    const which = listNumbers(missing, 6);
    const named = !placed
      ? `Not one of the ${lines} lines has an image yet.`
      : missing.length === 1
        ? `${placed} of ${lines} lines have an image. Line ${which} is still empty.`
        : `${placed} of ${lines} lines have an image. Lines ${which} are still empty.`;
    return {
      title: "Add one image for each line.",
      message: `${named} An image whose filename starts with the line number goes on that line, so 004 stays on line 4 whatever else is missing, and you can drop an image straight onto a line below.`,
    };
  }
  if (stage === 4) {
    const [width, height] = (project.settings.size || "1920x1080").split("x");
    const length = project.audio.seconds !== null ? clock(project.audio.seconds) : null;
    const size = width && height ? `${width} by ${height}` : project.settings.size;
    const long = length ? `, ${length} long` : "";
    return {
      title: "Build the video.",
      message: `All ${lines} lines have an image. img2vid will write one MP4 at ${size}, ${project.settings.fps} frames a second${long}, which is the length of the narration. It runs here, and you can watch it in the bar at the bottom.`,
    };
  }
  const changed = project.videos[0]?.outdated
    ? "The narration, transcript or images changed after it was built, so build it again to take them in."
    : "Every build is kept, so building again adds another one rather than replacing this.";
  return {
    title: "Your video is ready.",
    message: `Play it here, or download the MP4 to keep. ${changed}`,
  };
}

/**
 * The whole stage: which step, what to say about it, what stops Build video,
 * and the four markers with the state each one is in.
 */
export function readStage(project: Project): Stage {
  const job = project.job;
  const running = job?.state === "running";
  const transcribing = Boolean(running && job?.kind === "transcribe");
  const rendering = Boolean(running && job?.kind === "render");
  const number = stageNumber(project);
  const step = stepOfStage(number);
  const bodies = [
    narrationMarker(project),
    transcriptMarker(project, transcribing),
    imagesMarker(project),
    videoMarker(project, rendering),
  ];
  // A step ahead of this one says nothing, since nothing has happened there.
  // The exception is a job running for it: a build started from step 3 with
  // black lines is still worth seeing on the Video square.
  const working = transcribing ? 2 : rendering ? 4 : 0;
  const markers: Marker[] = bodies.map((body) => {
    const state = markerState(body.step, number, attention(project, body.step));
    return state === "ahead" && body.step !== working
      ? { ...body, state, summary: null, meta: null }
      : { ...body, state };
  });
  return { number, step, ...copy(project, number), blocked: buildBlocked(project), markers };
}
