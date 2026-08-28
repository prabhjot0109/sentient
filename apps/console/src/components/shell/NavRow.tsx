import { Link } from "@tanstack/react-router";
import type { LucideIcon } from "lucide-react";

/**
 * One destination in the rail's top section.
 *
 * Domain-free: it takes a route and an icon and knows nothing about keys,
 * credentials or projects, which is what keeps it in components/shell rather
 * than in whichever feature happened to need it first.
 */
export function NavRow({
  to,
  icon: Icon,
  label,
}: {
  to: "/app/keys" | "/app/credentials";
  icon: LucideIcon;
  label: string;
}) {
  return (
    <Link
      to={to}
      activeProps={{ className: "bg-sidebar-accent text-sidebar-foreground" }}
      inactiveProps={{ className: "text-muted-foreground hover:bg-sidebar-accent/60" }}
      className="flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm transition-colors hover:text-sidebar-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      <Icon className="size-4 shrink-0" />
      {label}
    </Link>
  );
}
