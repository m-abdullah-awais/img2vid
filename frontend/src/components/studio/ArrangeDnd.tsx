"use client";

import {
  closestCenter,
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  pointerWithin,
  TouchSensor,
  useSensor,
  useSensors,
  type Announcements,
  type CollisionDetection,
  type DragEndEvent,
  type DragStartEvent,
  type KeyboardCoordinateGetter,
  type PointerSensorOptions,
} from "@dnd-kit/core";
import type { PointerEvent as ReactPointerEvent, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { describeDrop, parseTarget, type DragSource, type DropTarget } from "@/lib/arrange";
import { Thumb } from "../ui/Thumb";
import { BoardContext, type Board } from "./targets";

/**
 * Mouse and pen only. Touch goes to the TouchSensor, which waits a moment
 * before lifting so a finger can still scroll the storyboard.
 */
class MousePenSensor extends PointerSensor {
  static activators = [
    {
      eventName: "onPointerDown" as const,
      handler: ({ nativeEvent: event }: ReactPointerEvent, { onActivation }: PointerSensorOptions) => {
        if (event.pointerType === "touch" || !event.isPrimary || event.button !== 0) return false;
        onActivation?.({ event });
        return true;
      },
    },
  ];
}

/**
 * Rows and gaps both contain the pointer at an edge: the gap wins, so inserting
 * is reachable. On the timeline the edge at a cut lies over the ends of the two
 * clips beside it, and wins over them the same way.
 */
function collide(args: Parameters<CollisionDetection>[0], lifted: Size | null) {
  if (args.pointerCoordinates) {
    const hits = pointerWithin(args);
    const between = hits.find((hit) => {
      const id = String(hit.id);
      return id.startsWith("gap:") || id.startsWith("edge:");
    });
    return between ? [between] : hits.slice(0, 1);
  }
  return closestCenter({ ...args, collisionRect: sourceBox(args.collisionRect, lifted) });
}

type Size = { width: number; height: number };

/**
 * Where the picked up image is, at its own size. dnd-kit measures the drag
 * overlay's content, which is 128 px wide whatever was lifted; a clip on the
 * timeline can be a few pixels wide, and the overlay's centre then sits past
 * the clip's own cut, so the keyboard would start one target to the right.
 * The overlay keeps the source's top left corner, so the source's size
 * placed there is where the keyboard is really pointing.
 */
function sourceBox<T extends Size & { left: number; top: number }>(overlay: T, source: Size | null | undefined): T {
  if (!source || source.width <= 0 || source.height <= 0) return overlay;
  return { ...overlay, width: source.width, height: source.height, right: overlay.left + source.width, bottom: overlay.top + source.height };
}

function sizeOf(node: Element | null | undefined): Size | null {
  if (!node) return null;
  const rect = node.getBoundingClientRect();
  return { width: rect.width, height: rect.height };
}

const directions: Record<string, [number, number]> = {
  ArrowDown: [0, 1],
  ArrowUp: [0, -1],
  ArrowRight: [1, 0],
  ArrowLeft: [-1, 0],
};

/** Arrow keys jump from one target to the next, gap, row, gap, row, instead of 25 px at a time. */
const jump: KeyboardCoordinateGetter = (event, { context }) => {
  const direction = directions[event.code];
  const { droppableRects, droppableContainers } = context;
  if (!direction || !context.collisionRect) return undefined;
  const collisionRect = sourceBox(context.collisionRect, sizeOf(context.activeNode));
  event.preventDefault();
  const cx = collisionRect.left + collisionRect.width / 2;
  const cy = collisionRect.top + collisionRect.height / 2;
  let best: { left: number; top: number; width: number; height: number } | null = null;
  let bestScore = Infinity;
  for (const container of droppableContainers.getEnabled()) {
    const rect = droppableRects.get(container.id);
    if (!rect) continue;
    const dx = rect.left + rect.width / 2 - cx;
    const dy = rect.top + rect.height / 2 - cy;
    const along = dx * direction[0] + dy * direction[1];
    if (along <= 1) continue;
    const across = Math.abs(direction[0] ? dy : dx);
    const score = along + across * 4;
    if (score < bestScore) {
      bestScore = score;
      best = rect;
    }
  }
  if (!best) return undefined;
  return {
    x: best.left + best.width / 2 - collisionRect.width / 2,
    y: best.top + best.height / 2 - collisionRect.height / 2,
  };
};

type Props = {
  board: Board;
  onDrop: (source: DragSource, target: DropTarget) => void;
  children: ReactNode;
};

export function ArrangeDnd({ board, onDrop, children }: Props) {
  const [active, setActive] = useState<DragSource | null>(null);
  const boardRef = useRef(board);
  const dropRef = useRef(onDrop);
  /** The size of the thing picked up, read when it is picked up. */
  const lifted = useRef<Size | null>(null);
  useEffect(() => {
    boardRef.current = board;
    dropRef.current = onDrop;
  });
  const detect = useCallback<CollisionDetection>((args) => collide(args, lifted.current), []);

  const reduced = useReducedMotion();
  const sensors = useSensors(
    useSensor(MousePenSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 220, tolerance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: jump, scrollBehavior: reduced ? "auto" : "smooth" }),
  );

  const announcements = useMemo<Announcements>(() => {
    const where = (source: DragSource) => (source.fromLine ? `line ${source.fromLine}` : "the Unplaced tray");
    const say = (source: DragSource, id: string | number | undefined) => {
      const target = parseTarget(id);
      if (!target) return "Not over a line.";
      return describeDrop(boardRef.current.lines, source, target).label;
    };
    return {
      onDragStart: ({ active: item }) => {
        const source = item.data.current as DragSource;
        return `Picked up ${source.image} from ${where(source)}.`;
      },
      onDragOver: ({ active: item, over }) => say(item.data.current as DragSource, over?.id),
      onDragEnd: ({ active: item, over }) => {
        const source = item.data.current as DragSource;
        const target = parseTarget(over?.id);
        if (!target) return `Dropped outside the storyboard and the timeline. ${source.image} did not move.`;
        const outcome = describeDrop(boardRef.current.lines, source, target);
        return outcome.allowed ? `Dropped. ${outcome.label}.` : `${outcome.label} Nothing changed.`;
      },
      onDragCancel: ({ active: item }) => `Cancelled. ${(item.data.current as DragSource).image} did not move.`,
    };
  }, []);

  function handleStart(event: DragStartEvent) {
    const target = event.activatorEvent?.target;
    lifted.current = target instanceof Element ? sizeOf(target.closest("button") ?? target) : null;
    setActive((event.active.data.current as DragSource) ?? null);
  }

  function handleEnd(event: DragEndEvent) {
    lifted.current = null;
    setActive(null);
    const source = event.active.data.current as DragSource | undefined;
    const target = parseTarget(event.over?.id);
    if (!source || !target) return;
    const outcome = describeDrop(boardRef.current.lines, source, target);
    if (outcome.allowed) dropRef.current(source, target);
  }

  return (
    <BoardContext.Provider value={board}>
      <DndContext
        sensors={sensors}
        collisionDetection={detect}
        onDragStart={handleStart}
        onDragEnd={handleEnd}
        onDragCancel={() => {
          lifted.current = null;
          setActive(null);
        }}
        accessibility={{
          announcements,
          screenReaderInstructions: {
            draggable:
              "To move this image, press Space or Enter. The arrow keys then step through lines and the gaps between them. Space or Enter drops it, Escape puts it back. Alt with the up or down arrow swaps it with the line next to it.",
          },
        }}
      >
        {children}
        <DragOverlay dropAnimation={null}>
          {active ? (
            <div className="w-32 overflow-hidden rounded-[var(--radius-frame)] border border-text bg-graphite shadow-[0_16px_40px_rgb(0_0_0/0.55)]">
              <Thumb src={active.thumb} alt="" eager className="aspect-video w-full" />
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </BoardContext.Provider>
  );
}

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    const first = window.setTimeout(update, 0);
    query.addEventListener("change", update);
    return () => {
      window.clearTimeout(first);
      query.removeEventListener("change", update);
    };
  }, []);
  return reduced;
}
