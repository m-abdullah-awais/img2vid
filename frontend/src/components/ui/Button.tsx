import { forwardRef, type ButtonHTMLAttributes } from "react";

export type ButtonVariant = "build" | "primary" | "secondary" | "ghost" | "quiet";
export type ButtonSize = "sm" | "md";

const base =
  "inline-flex shrink-0 items-center justify-center gap-2 rounded-[var(--radius-control)] font-medium whitespace-nowrap select-none " +
  "disabled:cursor-not-allowed disabled:opacity-45 aria-disabled:cursor-not-allowed aria-disabled:opacity-45";

const variants: Record<ButtonVariant, string> = {
  // The one red thing on a page: Build video, and the confirm that builds it.
  build: "bg-build text-ink font-semibold enabled:hover:brightness-110 enabled:active:brightness-95",
  primary: "bg-text text-graphite font-semibold enabled:hover:brightness-110 enabled:active:brightness-95",
  secondary: "border border-hairline bg-panel text-text hover:border-muted",
  ghost: "text-text hover:bg-panel",
  quiet: "text-muted hover:text-text",
};

const sizes: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-sm",
  md: "h-10 px-4 text-sm",
};

export function buttonClass(variant: ButtonVariant = "secondary", size: ButtonSize = "md", extra = "") {
  return `${base} ${variants[variant]} ${sizes[size]} ${extra}`.trim();
}

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
};

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = "secondary", size = "md", className = "", type = "button", ...rest },
  ref,
) {
  return <button ref={ref} type={type} className={buttonClass(variant, size, className)} {...rest} />;
});

/** A square button holding one icon. The label is required, for screen readers and the tooltip. */
export const IconButton = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { label: string; size?: ButtonSize }
>(function IconButton({ label, size = "sm", className = "", type = "button", ...rest }, ref) {
  const box = size === "sm" ? "h-8 w-8" : "h-10 w-10";
  return (
    <button
      ref={ref}
      type={type}
      aria-label={label}
      title={label}
      className={`inline-flex ${box} shrink-0 items-center justify-center rounded-[var(--radius-control)] text-muted hover:bg-panel hover:text-text disabled:cursor-not-allowed disabled:opacity-45 ${className}`}
      {...rest}
    />
  );
});
