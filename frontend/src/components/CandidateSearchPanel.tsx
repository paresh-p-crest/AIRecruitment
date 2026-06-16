"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, MessageSquare, Send, Sparkles, UserRound } from "lucide-react";
import {
  searchCandidates,
  type CandidateSearchResultItem,
  type SearchContextMessage,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const PLACEHOLDER_EXAMPLES = [
  "List candidates with more than 10 years experience",
  "Employees with 5+ years AWS experience",
  "Java developers open to relocation",
  "React engineers with fintech background",
];

interface ChatTurn {
  id: string;
  query: string;
  summary: string;
  results: CandidateSearchResultItem[];
}

interface CandidateSearchPanelProps {
  apiOnline: boolean;
  onOpenCandidate: (candidateId: number) => void;
}

export function CandidateSearchPanel({
  apiOnline,
  onOpenCandidate,
}: CandidateSearchPanelProps) {
  const [input, setInput] = useState("");
  const [placeholderIndex, setPlaceholderIndex] = useState(0);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const timer = setInterval(() => {
      setPlaceholderIndex((i) => (i + 1) % PLACEHOLDER_EXAMPLES.length);
    }, 4000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, searching]);

  const buildContext = useCallback((): SearchContextMessage[] => {
    const messages: SearchContextMessage[] = [];
    for (const turn of turns) {
      messages.push({ role: "user", content: turn.query });
      messages.push({
        role: "assistant",
        content: `${turn.summary}${turn.results.length ? ` (${turn.results.length} candidates)` : ""}`,
      });
    }
    return messages;
  }, [turns]);

  const lastResultIds = turns.length
    ? turns[turns.length - 1].results.map((r) => r.candidate_id)
    : [];

  const handleSubmit = async () => {
    const trimmed = input.trim();
    if (!trimmed || !apiOnline || searching) return;

    setSearching(true);
    setError(null);
    setInput("");

    try {
      const data = await searchCandidates(trimmed, 15, {
        context: buildContext(),
        previous_result_ids: lastResultIds,
      });
      setTurns((prev) => [
        ...prev,
        {
          id: `${Date.now()}`,
          query: trimmed,
          summary: data.summary,
          results: data.results,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
      setInput(trimmed);
    } finally {
      setSearching(false);
      textareaRef.current?.focus();
    }
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSubmit();
    }
  };

  return (
    <div className="app-search-panel shadow-card">
      <div className="shrink-0 border-b border-white/10 px-4 py-3 sm:px-5">
        <h2 className="flex items-center gap-2 font-display text-lg font-semibold text-white">
          <Sparkles className="h-5 w-5 text-brand-400" />
          Candidate search
        </h2>
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-3 scrollbar-thin sm:px-5">
        {turns.length === 0 && !searching && (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <MessageSquare className="mb-2 h-8 w-8 text-slate-600" />
            <p className="text-sm text-slate-400">
              Ask about your candidate pool. Results appear above the search box.
            </p>
            <p className="mt-1.5 text-xs text-slate-500">
              Try: &quot;{PLACEHOLDER_EXAMPLES[placeholderIndex]}&quot;
            </p>
          </div>
        )}

        <div className="space-y-6">
          {turns.map((turn) => (
            <div key={turn.id} className="space-y-3">
              <div className="flex justify-end">
                <div className="app-search-user-bubble max-w-[85%] rounded-2xl rounded-br-md px-4 py-2.5 text-sm ring-1">
                  {turn.query}
                </div>
              </div>

              <div className="max-w-full rounded-2xl rounded-bl-md border border-white/10 bg-white/[0.03] px-4 py-3">
                <p className="text-sm text-slate-200">{turn.summary}</p>

                {turn.results.length > 0 && (
                  <div className="mt-4 overflow-x-auto">
                    <table className="w-full min-w-[640px] text-left text-sm">
                      <thead>
                        <tr className="app-search-table-head border-b border-white/10 text-xs uppercase tracking-wide text-slate-500">
                          <th className="px-2 py-2 font-medium">Name</th>
                          <th className="px-2 py-2 font-medium">Contact</th>
                          <th className="px-2 py-2 font-medium">Email</th>
                          <th className="px-2 py-2 font-medium">Match</th>
                          <th className="px-2 py-2 text-right font-medium">Profile</th>
                        </tr>
                      </thead>
                      <tbody>
                        {turn.results.map((row) => (
                          <tr
                            key={`${turn.id}-${row.candidate_id}`}
                            className="border-b border-white/5 last:border-0"
                          >
                            <td className="px-2 py-2.5">
                              <p className="font-medium text-white">{row.name}</p>
                              {row.title && (
                                <p className="truncate text-xs text-slate-500">{row.title}</p>
                              )}
                            </td>
                            <td className="px-2 py-2.5 text-slate-300">{row.phone || "—"}</td>
                            <td className="truncate px-2 py-2.5 text-slate-300">
                              {row.email || "—"}
                            </td>
                            <td className="px-2 py-2.5 text-xs text-slate-400">
                              {row.match_reason || "—"}
                            </td>
                            <td className="px-2 py-2.5 text-right">
                              <button
                                type="button"
                                onClick={() => onOpenCandidate(row.candidate_id)}
                                className="inline-flex items-center gap-1 rounded-lg border border-brand-500/30 bg-brand-500/10 px-2.5 py-1 text-xs font-medium text-brand-200 hover:bg-brand-500/20"
                              >
                                <UserRound className="h-3.5 w-3.5" />
                                View
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          ))}

          {searching && (
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin text-brand-400" />
              Searching candidates…
            </div>
          )}
        </div>

        {error && <p className="mt-4 text-sm text-red-300">{error}</p>}
      </div>

      <div className="app-search-composer shrink-0 border-t p-3 sm:px-5 sm:py-4">
        <label htmlFor="candidate-search-input" className="mb-2 block text-xs font-medium app-help-text">
          Search query
        </label>
        <div className="flex gap-2">
          <textarea
            id="candidate-search-input"
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={!apiOnline || searching}
            rows={1}
            placeholder={PLACEHOLDER_EXAMPLES[placeholderIndex]}
            className="app-search-input min-h-[44px] flex-1 resize-none px-3 py-2.5 text-sm disabled:opacity-50"
            aria-label="Search candidates"
          />
          <button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={!apiOnline || searching || !input.trim()}
            className={cn(
              "app-search-submit inline-flex h-[44px] shrink-0 items-center justify-center gap-1.5 rounded-xl px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50"
            )}
          >
            {searching ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            <span className="hidden sm:inline">Search</span>
          </button>
        </div>
        <p className="mt-1.5 text-xs app-help-text">Enter to search · Shift+Enter for new line</p>
      </div>
    </div>
  );
}
