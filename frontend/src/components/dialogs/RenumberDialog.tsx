"use client";

import { useEffect, useMemo, useState } from "react";
import { post, projectPath, toApiError } from "@/lib/api";
import { plural } from "@/lib/format";
import type { Project, RenameBody, RenameBy, RenamePreview } from "@/lib/types";
import { Banner } from "../studio/Banners";
import { Button } from "../ui/Button";
import { Checkbox, Choice, Field, inputClass, TextInput } from "../ui/Field";
import { Dialog } from "../ui/Dialog";
import { useToast } from "../ui/Toast";

type Props = {
  project: Project;
  locked: boolean;
  lockedReason: string | null;
  onClose: () => void;
  onProject: (project: Project) => void;
  onUndo: (undoId: string) => Promise<void>;
};

type Order = "auto" | RenameBy;

const ORDERS: { value: Order; label: string }[] = [
  { value: "auto", label: "Automatic" },
  { value: "name", label: "Name" },
  { value: "created", label: "Date created" },
  { value: "modified", label: "Date modified" },
  { value: "size", label: "Size" },
  { value: "type", label: "Type" },
  { value: "random", label: "Random" },
];

/**
 * Give every image a clean number, 001 upward, in an order you choose. Shown
 * before it happens, including every image that would change line.
 */
export function RenumberDialog({ project, locked, lockedReason, onClose, onProject, onUndo }: Props) {
  const { toast } = useToast();
  const [order, setOrder] = useState<Order>("auto");
  const [desc, setDesc] = useState(false);
  const [seed, setSeed] = useState("");
  const [start, setStart] = useState<"1" | "0">(project.images.base === 0 ? "0" : "1");
  const [digits, setDigits] = useState<"3" | "4">(project.images.width >= 4 ? "4" : "3");
  // The preview and the exact options it was made from: apply must send those back.
  const [preview, setPreview] = useState<{ result: RenamePreview; body: RenameBody } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  const [round, setRound] = useState(0);

  const body = useMemo<RenameBody>(
    () => ({
      by: order === "auto" ? null : order,
      desc: order === "random" ? false : desc,
      seed: order === "random" && seed.trim() ? Number(seed) : null,
      start: Number(start),
      digits: Number(digits),
    }),
    [order, desc, seed, start, digits],
  );

  useEffect(() => {
    let alive = true;
    const timer = window.setTimeout(() => {
      post<RenamePreview>(projectPath(project.id, "rename", "preview"), body)
        .then((result) => {
          if (!alive) return;
          setPreview({ result, body });
          setError(null);
        })
        .catch((failure) => {
          if (alive) setError(toApiError(failure).message);
        });
    }, 200);
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [body, project.id, round]);

  // Only a preview of the options on screen can be applied.
  const current = preview && preview.body === body ? preview : null;

  async function apply() {
    if (!current) return;
    setApplying(true);
    try {
      const result = await post<{ undoId: string; project: Project }>(projectPath(project.id, "rename", "apply"), {
        ...current.body,
        // Random picks a seed when none was given; the plan is only valid with that one.
        seed: current.result.order.seed ?? current.body.seed ?? null,
        planId: current.result.planId,
      });
      onProject(result.project);
      toast({
        tone: "done",
        message: `Renumbered ${plural(current.result.changing, "image")}`,
        action: result.undoId ? { label: "Undo", run: () => onUndo(result.undoId) } : undefined,
      });
      onClose();
    } catch (failure) {
      const apiError = toApiError(failure);
      setApplying(false);
      if (apiError.code === "changed") {
        setError("The images changed since this preview, so it was made again. Check it, then apply.");
        setRound((count) => count + 1);
      } else {
        setError(apiError.message);
      }
    }
  }

  const shown = preview?.result ?? null;
  const changing = shown ? shown.pairs.filter((pair) => pair.from !== pair.to) : [];
  const shifted = shown?.shifted ?? null;

  return (
    <Dialog
      title="Renumber images"
      size="xl"
      onClose={onClose}
      dismissible={!applying}
      description="Gives every image a clean number in the order you choose. Numbers are what put an image on its line."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={applying}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={() => void apply()}
            disabled={!current || applying || locked || current.result.changing === 0}
          >
            {applying ? "Renumbering" : shown && shown.changing ? `Renumber ${plural(shown.changing, "image")}` : "Renumber"}
          </Button>
        </>
      }
    >
      <div className="grid gap-6 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
        <div className="flex flex-col gap-5">
          {locked ? <Banner tone="info" title="Images are locked">{lockedReason}</Banner> : null}
          <Field
            label="Order"
            hint={
              order === "auto"
                ? "The order the filenames already carry when they are numbered, otherwise date created."
                : order === "created"
                  ? "When each file arrived on this computer, which is not always when it was made."
                  : undefined
            }
          >
            {({ id, describedBy }) => (
              <select
                id={id}
                aria-describedby={describedBy}
                value={order}
                onChange={(event) => setOrder(event.target.value as Order)}
                className={inputClass}
              >
                {ORDERS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            )}
          </Field>
          {order === "random" ? (
            <Field label="Seed" hint="Optional. The same seed gives the same shuffle again.">
              {({ id, describedBy }) => (
                <TextInput
                  id={id}
                  aria-describedby={describedBy}
                  type="number"
                  inputMode="numeric"
                  value={seed}
                  onChange={(event) => setSeed(event.target.value)}
                  className="timecode w-40"
                />
              )}
            </Field>
          ) : (
            <Checkbox checked={desc} onChange={setDesc} label="Reverse the order" hint="Newest, largest or Z first." />
          )}
          <Choice<"1" | "0">
            legend="First number"
            value={start}
            onChange={setStart}
            options={[
              { value: "1", label: <span className="timecode">001</span> },
              { value: "0", label: <span className="timecode">000</span> },
            ]}
          />
          <Choice<"3" | "4">
            legend="Digits"
            value={digits}
            onChange={setDigits}
            options={[
              { value: "3", label: <span className="timecode">001</span> },
              { value: "4", label: <span className="timecode">0001</span> },
            ]}
          />
        </div>

        <div className="flex min-w-0 flex-col gap-3">
          {shifted ? (
            <Banner tone="attention" title={`${plural(shifted.count, "image")} would move to a different line, starting at line ${shifted.first}`}>
              Renumbering closes gaps. Every image after a missing one moves up a line and lands on the
              wrong narration. If the gaps are deliberate, add the missing images instead.
            </Banner>
          ) : null}
          {error ? <Banner tone="error" title="Preview problem">{error}</Banner> : null}
          {shown ? (
            <>
              <p className="text-sm">
                <span className="text-muted">Order: </span>
                {shown.order.label}
                {shown.order.seed !== null && order === "random" ? (
                  <span className="timecode text-muted">, seed {shown.order.seed}</span>
                ) : null}
              </p>
              {shown.order.kept ? (
                <p className="text-sm text-muted">
                  The filenames already carry an order, so it is kept. Ordering by {shown.order.kept.wouldHave} would
                  have put {shown.order.kept.first} first.
                </p>
              ) : null}
              <p className="text-sm text-muted">
                {shown.changing
                  ? `${plural(shown.changing, "image")} get a new name. The rest keep theirs.`
                  : "Nothing changes: the images are already numbered this way."}
              </p>
              {changing.length ? (
                <div className="max-h-[46vh] overflow-auto rounded-[var(--radius-control)] border border-hairline">
                  <table className="w-full text-left text-sm">
                    <caption className="sr-only">Every name that changes, and the line before and after</caption>
                    <thead className="sticky top-0 bg-panel text-xs text-muted">
                      <tr className="border-b border-hairline">
                        <th scope="col" className="px-3 py-2 font-medium">From</th>
                        <th scope="col" className="px-3 py-2 font-medium">To</th>
                        <th scope="col" className="px-3 py-2 text-right font-medium">Line before</th>
                        <th scope="col" className="px-3 py-2 text-right font-medium">Line after</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-hairline">
                      {changing.map((pair) => {
                        const moves = pair.lineBefore !== pair.lineAfter;
                        return (
                          <tr key={pair.from}>
                            <td className="max-w-[16rem] truncate px-3 py-1.5" title={pair.from}>
                              {pair.from}
                            </td>
                            <td className="max-w-[16rem] truncate px-3 py-1.5" title={pair.to}>
                              {pair.to}
                            </td>
                            <td className="timecode px-3 py-1.5 text-right text-muted">{pair.lineBefore ?? "none"}</td>
                            <td className={`timecode px-3 py-1.5 text-right ${moves ? "text-missing" : "text-muted"}`}>
                              {pair.lineAfter ?? "none"}
                              {moves ? <span className="sr-only">, a different line</span> : null}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </>
          ) : !error ? (
            <p className="text-sm text-muted">Working out the new names</p>
          ) : null}
        </div>
      </div>
    </Dialog>
  );
}
