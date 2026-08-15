export function Logo({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={className}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <path d="M16 2 L28 9 L28 23 L16 30 L4 23 L4 9 Z" stroke="var(--brand)" strokeWidth="1.4" />
      <circle cx="16" cy="16" r="4.5" fill="var(--brand)" />
      <circle cx="16" cy="16" r="9" stroke="var(--brand)" strokeOpacity="0.4" />
    </svg>
  );
}
