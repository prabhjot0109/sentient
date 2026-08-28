import { useOnline } from "../hooks";

export function OfflineBanner() {
  const online = useOnline();
  if (online) return null;

  return (
    <div
      role="status"
      className="border-b border-warning/40 bg-warning/10 px-4 py-2 text-center text-sm"
    >
      You&apos;re offline. Nothing will save until the connection is back.
    </div>
  );
}
