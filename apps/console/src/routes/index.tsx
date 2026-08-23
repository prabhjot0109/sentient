import { createFileRoute, Navigate } from "@tanstack/react-router";

import { useSession } from "@/features/auth";

function Landing() {
  const { data, isPending } = useSession();
  if (isPending) return null;
  return <Navigate to={data ? "/app" : "/auth/sign-in"} />;
}

export const Route = createFileRoute("/")({ component: Landing });
