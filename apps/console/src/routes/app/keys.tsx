import { createFileRoute } from "@tanstack/react-router";

import { KeysScreen } from "@/features/keys";

export const Route = createFileRoute("/app/keys")({ component: KeysScreen });
