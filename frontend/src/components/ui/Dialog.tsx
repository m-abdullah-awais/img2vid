"use client";

import { X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";

type Props = {
  title: string;
  onClose: () => void;
  children: ReactNode;
  /** Buttons along the bottom edge. */
  footer?: ReactNode;
  description?: ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
  /** False while something is uploading or saving, so Escape cannot orphan it. */
  dismissible?: boolean;
};

const widths = {
  sm: "max-w-[440px]",
  md: "max-w-[560px]",
  lg: "max-w-[720px]",
  xl: "max-w-[920px]",
};

/**
 * A modal on the native <dialog> element. Mount it to open it, unmount it to
 * close it: the browser supplies the focus trap, Escape and the backdrop.
 */
export function Dialog({
  title,
  onClose,
  children,
  footer,
  description,
  size = "md",
  dismissible = true,
}: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const closeRef = useRef(onClose);
  const dismissRef = useRef(dismissible);

  useEffect(() => {
    closeRef.current = onClose;
    dismissRef.current = dismissible;
  });

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (!dialog.open) dialog.showModal();
    // showModal() focuses the first focusable element, which is the Close
    // button in the header. Move focus to what the dialog is for instead:
    // a field marked data-autofocus, or else the first control in the body.
    let preferred =
      dialog.querySelector<HTMLElement>("[data-autofocus]") ??
      dialog.querySelector<HTMLElement>(
        "[data-dialog-body] :is(input, select, textarea, button):not([disabled]):not([tabindex='-1'])",
      );
    // In a set of radio buttons, the chosen one is the one to land on.
    if (preferred instanceof HTMLInputElement && preferred.type === "radio" && !preferred.checked) {
      const group = dialog.querySelectorAll<HTMLInputElement>(`input[type="radio"][name="${CSS.escape(preferred.name)}"]`);
      preferred = Array.from(group).find((radio) => radio.checked) ?? preferred;
    }
    preferred?.focus();
    const handleCancel = (event: Event) => {
      event.preventDefault();
      if (dismissRef.current) closeRef.current();
    };
    dialog.addEventListener("cancel", handleCancel);
    return () => {
      dialog.removeEventListener("cancel", handleCancel);
      if (dialog.open) dialog.close();
    };
  }, []);

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      className={`motion-dialog m-auto w-[calc(100vw-2rem)] ${widths[size]} max-h-[calc(100dvh-2rem)] overflow-hidden rounded-[var(--radius-control)] border border-hairline bg-panel p-0 text-text shadow-[0_24px_64px_rgb(0_0_0/0.45)]`}
      onMouseDown={(event) => {
        // A press that starts on the backdrop, not one that ends there after selecting text.
        if (event.target === event.currentTarget && dismissRef.current) {
          const box = event.currentTarget.getBoundingClientRect();
          const inside =
            event.clientX >= box.left &&
            event.clientX <= box.right &&
            event.clientY >= box.top &&
            event.clientY <= box.bottom;
          if (!inside) closeRef.current();
        }
      }}
    >
      <div className="flex max-h-[calc(100dvh-2rem)] flex-col">
        <header className="flex items-start gap-4 border-b border-hairline px-5 pt-4 pb-3">
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className="heading text-2xl">
              {title}
            </h2>
            {description ? <div className="mt-1 text-sm text-muted">{description}</div> : null}
          </div>
          <button
            type="button"
            onClick={() => dismissRef.current && closeRef.current()}
            disabled={!dismissible}
            aria-label="Close"
            title="Close"
            className="-mr-2 inline-flex h-8 w-8 items-center justify-center rounded-[var(--radius-control)] text-muted hover:bg-graphite hover:text-text disabled:opacity-40"
          >
            <X size={18} aria-hidden />
          </button>
        </header>
        <div data-dialog-body className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {children}
        </div>
        {footer ? (
          <footer className="flex flex-wrap items-center justify-end gap-2 border-t border-hairline px-5 py-3">
            {footer}
          </footer>
        ) : null}
      </div>
    </dialog>
  );
}
