import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createRouter, RouterProvider } from "@tanstack/react-router";
import { ThemeProvider } from "next-themes";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { UnauthenticatedError } from "@/lib/api/errors";

import { routeTree } from "./routeTree.gen";
import "./styles/globals.css";

const router = createRouter({ routeTree });
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // An expired session will not un-expire on retry. The seam already
      // re-reads the token once before surfacing the 401 (lib/api/client.ts), so
      // by the time an UnauthenticatedError arrives here the answer is settled --
      // three more round trips only delay the sign-in prompt.
      //
      // NOT a blanket retry:false. A 502 from a flaky provider is worth one go.
      retry: (failureCount, error) =>
        error instanceof UnauthenticatedError ? false : failureCount < 1,

      // A query error is RETURNED, never thrown, so it never reaches a router
      // error boundary on its own. Opting this one class in is what turns an
      // expired session from a stranded card in the middle of a screen -- under
      // a sidebar still listing projects from cache -- into the app shell's
      // whole-page "Your session has expired" with a way out. Only this class:
      // every other error is better rendered in place, next to the thing that
      // failed.
      throwOnError: (error) => error instanceof UnauthenticatedError,
    },
  },
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/*
      One ThemeProvider for the whole app, and it governs the auth screens too.
      NeonAuthUIProvider mounts its OWN next-themes ThemeProvider with
      `enableSystem: true` and its own defaultTheme -- but next-themes is
      `useContext(ctx) ? <Fragment>{children}</Fragment> : <Provider/>`, read out
      of the installed 0.4.6 bundle, so a nested provider is a NO-OP when a
      parent exists. This one wins, and AuthView follows the console's theme
      rather than the OS.

      `attribute="class"` because that is what Neon's own CSS reads: its dark
      values live under `:root.dark`. tokens.css matches that convention, so one
      class moves both.

      defaultTheme="dark" with enableSystem={false}: apps/landing ships dark
      only, so a visitor arriving through its Launch CTA must not cross a light
      flash. Light is a choice the toggle offers, not a thing the OS imposes.

      disableTransitionOnChange stops every colour-transition in the tree from
      animating at once during the swap, which reads as a smear rather than a
      change.
    */}
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={false}
      disableTransitionOnChange
    >
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
);
