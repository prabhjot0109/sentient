import type { InputHTMLAttributes } from "react";
import { twMerge } from "tailwind-merge";

/**
 * The console's ten inputs, which had split between border-input and
 * border-border for no reason anyone recorded. border-input wins: it is the
 * token the auth-UI theme also drives, so a form field looks the same on the
 * sign-in screen and inside the app.
 */
export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={twMerge(
        "w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:opacity-50",
        className,
      )}
      {...rest}
    />
  );
}
