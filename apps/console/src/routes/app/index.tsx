import { createFileRoute } from "@tanstack/react-router";

import { AuthProbe } from "@/features/auth";

export const Route = createFileRoute("/app/")({ component: AuthProbe });
