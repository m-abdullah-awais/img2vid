// What a drop will do, worked out on the client from the storyboard so the
// target can say it while the image is still in the air. The rules are the
// API's own (see "Arranging and renumbering" in the contract):
//   place:  an empty line receives the image, an occupied one swaps.
//   insert: the image goes onto the line and the images from there down move
//           one line later each, stopping at the first empty line, which
//           absorbs the shift. The image's own line counts as empty.

import type { ArrangeOp, Line } from "@/lib/types";

export type DragSource = {
  image: string;
  thumb: string;
  /** The line it sits on now, or null for an image in the Unplaced tray. */
  fromLine: number | null;
};

export type DropTarget = { op: ArrangeOp; line: number };

export type Outcome = {
  allowed: boolean;
  /** Dropping here changes nothing. */
  noop: boolean;
  label: string;
};

function occupied(board: Line[], line: number, fromLine: number | null): boolean {
  if (line === fromLine) return false;
  const slot = board[line - 1];
  return Boolean(slot && (slot.image || slot.state === "duplicate"));
}

export function describeDrop(board: Line[], source: DragSource, target: DropTarget): Outcome {
  const { line } = target;
  if (line < 1 || line > board.length) {
    return { allowed: false, noop: false, label: `There is no line ${line}.` };
  }

  if (target.op === "place") {
    if (line === source.fromLine) return { allowed: false, noop: true, label: `Already on line ${line}` };
    if (occupied(board, line, source.fromLine)) {
      return {
        allowed: true,
        noop: false,
        label:
          source.fromLine === null
            ? `Swap with line ${line}, its image goes to Unplaced`
            : `Swap with line ${line}`,
      };
    }
    return {
      allowed: true,
      noop: false,
      label: source.fromLine === null ? `Place on line ${line}` : `Move to line ${line}`,
    };
  }

  // insert
  let empty = -1;
  for (let at = line; at <= board.length; at += 1) {
    if (!occupied(board, at, source.fromLine)) {
      empty = at;
      break;
    }
  }
  if (empty === -1) {
    return {
      allowed: false,
      noop: false,
      label: `Cannot insert here. No line from ${line} to the end is empty, so nothing can take the shift.`,
    };
  }
  if (empty === line) {
    if (line === source.fromLine) return { allowed: false, noop: true, label: `Already on line ${line}` };
    return {
      allowed: true,
      noop: false,
      label: source.fromLine === null ? `Place on line ${line}` : `Move to line ${line}`,
    };
  }
  const last = empty - 1;
  return {
    allowed: true,
    noop: false,
    label:
      last === line
        ? `Insert here, line ${line} moves down`
        : `Insert here, lines ${line} to ${last} move down`,
  };
}

/** Parse the ids the storyboard gives its droppables. */
export function parseTarget(id: string | number | null | undefined): DropTarget | null {
  if (typeof id !== "string") return null;
  const match = /^(line|gap|cell):(\d+)$/.exec(id);
  if (!match) return null;
  return { op: match[1] === "gap" ? "insert" : "place", line: Number(match[2]) };
}
