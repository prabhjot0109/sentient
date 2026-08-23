import { createFileRoute } from "@tanstack/react-router";

import { SignInScreen } from "@/features/auth";

export const Route = createFileRoute("/auth/sign-in")({ component: SignInScreen });
