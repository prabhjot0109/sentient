import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";
import { twMerge } from "tailwind-merge";

/**
 * The four button shapes the console had already converged on by hand, spelled
 * once. Before this there were 41 <button> elements carrying variations on the
 * same four class strings, and the variations were drift rather than intent:
 * px-3 py-1.5 in one dialog and px-3 py-2 in the next, border-border here and
 * border-input there.
 *
 * Domain-free, per the spec's rule that a primitive knowing what a "project" is
 * has stopped being a primitive.
 */
const button = cva(
  // focus-visible rather than focus: keyboard users get a ring, mouse users do
  // not get one on every click. Not one of the 41 hand-rolled buttons had any
  // focus style at all, so this is the accessibility fix that arrives with the
  // primitive rather than after it.
  "inline-flex items-center justify-center gap-1.5 rounded-md text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-primary text-primary-foreground hover:opacity-90",
        // border + hover, the console's existing "outline" shape.
        secondary: "border border-border hover:bg-muted",
        ghost: "hover:bg-muted",
        destructive: "bg-destructive text-destructive-foreground hover:opacity-90",
      },
      size: { sm: "h-8 px-3", md: "h-9 px-4" },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export function Button({
  className,
  variant,
  size,
  type = "button",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof button>) {
  // twMerge, not string concatenation, so a call site's one-off className
  // overrides the variant instead of fighting it. Without it "px-6" and "px-4"
  // both land and the winner is whichever Tailwind emitted later, which is not
  // the one the reader wrote.
  //
  // type defaults to "button": a bare <button> inside a <form> is type="submit",
  // which is how a Cancel button comes to submit the dialog it was meant to
  // dismiss.
  return <button type={type} className={twMerge(button({ variant, size }), className)} {...rest} />;
}
