import { useState } from "react";

import { ApiError } from "@/lib/api/errors";
import type { Thread } from "@/types/threads";

import { useChatTurn, useDeleteThread, useMessages, useRenameThread, useThreads } from "../hooks";
import { showDraft } from "../transcript";
import { Composer } from "./Composer";
import { DeleteThreadDialog } from "./DeleteThreadDialog";
import { MessageList } from "./MessageList";
import { RenameThreadDialog } from "./RenameThreadDialog";
import { SourcesPanel } from "./SourcesPanel";
import { ThreadList } from "./ThreadList";

/**
 * Holds the selected thread and the in-flight turn. `routes/` may not hold
 * domain state, which is the same reason `KeysScreen` and `DocumentsScreen`
 * exist.
 */
export function ChatScreen({ projectId }: { projectId: string }) {
  const { data: threads = [], error: threadsError } = useThreads(projectId);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<Thread | null>(null);
  const [deleting, setDeleting] = useState<Thread | null>(null);

  const rename = useRenameThread(projectId);
  const remove = useDeleteThread(projectId);
  const turn = useChatTurn(projectId);

  // A new conversation gets its id from the meta frame, which arrives BEFORE the
  // first token. Deriving the active thread rather than assigning it after the
  // stream is what mounts the transcript query while the reply is still
  // arriving, and what makes the second message continue the SAME thread instead
  // of opening another one.
  const activeId = selectedId ?? turn.threadId;
  const { data: messages = [] } = useMessages(activeId, turn.draft, turn.isStreaming);

  const select = (id: string | null) => {
    setSelectedId(id);
    turn.reset();
  };

  return (
    <section className="flex gap-4">
      <ThreadList
        threads={threads}
        activeId={activeId}
        onSelect={(thread) => select(thread.id)}
        onRename={setRenaming}
        onDelete={setDeleting}
        onNew={() => select(null)}
      />

      <div className="min-w-0 flex-1 space-y-4">
        {threadsError && (
          <p className="text-sm text-destructive">
            {threadsError instanceof ApiError ? threadsError.detail : "Could not load threads."}
          </p>
        )}

        <MessageList
          messages={messages}
          draft={turn.draft}
          showDraft={showDraft(messages, turn.draft, turn.isStreaming)}
          isStreaming={turn.isStreaming}
        />
        <SourcesPanel sources={turn.sources} />

        {/*
          The 409 is not a failure and must not read as one: retrieval is awaited
          before the response starts, so a reindexing project answers a clean
          status code rather than opening a stream and breaking it.
        */}
        {turn.isReindexing ? (
          <p className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm">
            This project&rsquo;s lore is re-embedding. NPCs can&rsquo;t cite it until that finishes
            — send again in a moment.
          </p>
        ) : (
          turn.error && <p className="text-sm text-destructive">{turn.error}</p>
        )}

        <Composer
          onSend={(message) => void turn.send(message, activeId)}
          disabled={turn.isStreaming}
        />
      </div>

      <RenameThreadDialog
        thread={renaming}
        isPending={rename.isPending}
        onClose={() => setRenaming(null)}
        onConfirm={(title) =>
          rename.mutate({ id: renaming!.id, title }, { onSuccess: () => setRenaming(null) })
        }
      />
      <DeleteThreadDialog
        thread={deleting}
        isPending={remove.isPending}
        onClose={() => setDeleting(null)}
        onConfirm={() =>
          remove.mutate(deleting!.id, {
            onSuccess: () => {
              // Clearing `selectedId` alone is not enough: the turn may still be
              // holding this id from its meta frame, and `activeId` would fall
              // back to it and refetch a transcript that is now a 404.
              if (deleting!.id === activeId) select(null);
              setDeleting(null);
            },
          })
        }
      />
    </section>
  );
}
