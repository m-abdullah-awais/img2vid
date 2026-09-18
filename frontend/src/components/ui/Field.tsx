"use client";

import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes } from "react";

export const inputClass =
  "h-10 w-full rounded-[var(--radius-control)] border border-hairline bg-graphite px-3 text-sm text-text placeholder:text-muted " +
  "hover:border-muted focus-visible:border-text disabled:opacity-50";

type FieldProps = {
  label: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  children: (ids: { id: string; describedBy: string | undefined }) => ReactNode;
  className?: string;
};

/** A label, a control, and the line of help or error under it. */
export function Field({ label, hint, error, children, className = "" }: FieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : "", error ? errorId : ""].filter(Boolean).join(" ") || undefined;
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      {children({ id, describedBy })}
      {hint ? (
        <p id={hintId} className="text-xs text-muted">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="flex items-start gap-1.5 text-xs text-text">
          <span aria-hidden className="mt-[5px] h-2 w-2 shrink-0 rounded-full bg-build" />
          {error}
        </p>
      ) : null}
    </div>
  );
}

export const TextInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function TextInput({ className = "", ...rest }, ref) {
    return <input ref={ref} className={`${inputClass} ${className}`} {...rest} />;
  },
);

export const TextArea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function TextArea({ className = "", ...rest }, ref) {
    return (
      <textarea
        ref={ref}
        className={`w-full rounded-[var(--radius-control)] border border-hairline bg-graphite p-3 text-sm text-text placeholder:text-muted hover:border-muted focus-visible:border-text ${className}`}
        {...rest}
      />
    );
  },
);

type CheckboxProps = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: ReactNode;
  hint?: ReactNode;
  disabled?: boolean;
};

export function Checkbox({ checked, onChange, label, hint, disabled }: CheckboxProps) {
  const id = useId();
  return (
    <div className="flex items-start gap-3">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        aria-describedby={hint ? `${id}-hint` : undefined}
        className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--color-text)]"
      />
      <div>
        <label htmlFor={id} className="text-sm font-medium">
          {label}
        </label>
        {hint ? (
          <p id={`${id}-hint`} className="text-xs text-muted">
            {hint}
          </p>
        ) : null}
      </div>
    </div>
  );
}

export type ChoiceOption<T extends string | number> = {
  value: T;
  label: ReactNode;
  note?: ReactNode;
};

type ChoiceProps<T extends string | number> = {
  legend: ReactNode;
  hint?: ReactNode;
  value: T;
  options: ChoiceOption<T>[];
  onChange: (value: T) => void;
  disabled?: boolean;
  /** Stacked shows each option's note under it; inline is a segmented row. */
  layout?: "inline" | "stacked";
};

/** A set of native radio buttons, so arrow keys move between them. */
export function Choice<T extends string | number>({
  legend,
  hint,
  value,
  options,
  onChange,
  disabled,
  layout = "inline",
}: ChoiceProps<T>) {
  const name = useId();
  return (
    <fieldset className="flex flex-col gap-1.5" disabled={disabled}>
      <legend className="mb-1.5 text-sm font-medium">{legend}</legend>
      <div
        className={
          layout === "inline"
            ? "flex flex-wrap gap-1 rounded-[var(--radius-control)] border border-hairline bg-graphite p-1 sm:w-fit"
            : "flex flex-col divide-y divide-hairline rounded-[var(--radius-control)] border border-hairline bg-graphite"
        }
      >
        {options.map((option) => {
          const checked = option.value === value;
          return (
            <label
              key={String(option.value)}
              className={
                layout === "inline"
                  ? `relative flex cursor-pointer items-center rounded-[4px] px-3 py-1.5 text-sm has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-text ${
                      checked ? "bg-panel text-text shadow-[inset_0_0_0_1px_var(--color-hairline)]" : "text-muted hover:text-text"
                    }`
                  : `flex cursor-pointer items-start gap-3 px-3 py-2.5 has-[:focus-visible]:outline-2 has-[:focus-visible]:-outline-offset-2 has-[:focus-visible]:outline-text ${
                      checked ? "bg-panel" : "hover:bg-panel/60"
                    }`
              }
            >
              <input
                type="radio"
                name={name}
                value={String(option.value)}
                checked={checked}
                onChange={() => onChange(option.value)}
                className={layout === "inline" ? "sr-only" : "mt-1 h-4 w-4 shrink-0 accent-[var(--color-text)]"}
              />
              {layout === "inline" ? (
                option.label
              ) : (
                <span className="flex flex-col">
                  <span className="text-sm font-medium">{option.label}</span>
                  {option.note ? <span className="text-xs text-muted">{option.note}</span> : null}
                </span>
              )}
            </label>
          );
        })}
      </div>
      {hint ? <p className="text-xs text-muted">{hint}</p> : null}
    </fieldset>
  );
}
