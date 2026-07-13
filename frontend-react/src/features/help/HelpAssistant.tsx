import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { askApplicationHelp } from "../../api/help-api";
import { useAuth } from "../../hooks/use-auth";
import type { HelpMessage } from "../../models/help";
import { articleForQuestion, HELP_KNOWLEDGE_VERSION, suggestionsForRoute } from "./help-knowledge";

const MAX_LENGTH = 500;
const fallback = "I can help with using LegacyDB Copilot, such as workspaces, database connections, investigations, feedback, reports, and user access.";
const id = () => `${Date.now()}-${Math.random().toString(36).slice(2)}`;

export function HelpAssistant() {
  const { user } = useAuth(); const { pathname } = useLocation(); const launcherRef = useRef<HTMLButtonElement>(null); const panelRef = useRef<HTMLElement>(null); const inputRef = useRef<HTMLTextAreaElement>(null); const openedRef = useRef(false);
  const [mode, setMode] = useState<"closed"|"open"|"expanded">(() => localStorage.getItem("legacydb-help-state") === "open" ? "open" : "closed");
  const [messages, setMessages] = useState<HelpMessage[]>([]); const [question, setQuestion] = useState(""); const [pending, setPending] = useState(false); const [error, setError] = useState<string | null>(null); const abortRef = useRef<AbortController | null>(null);
  const suggestions = useMemo(() => suggestionsForRoute(pathname, user?.role), [pathname, user?.role]);
  useEffect(() => { setMessages([]); setQuestion(""); setError(null); }, [user?.id]);
  useEffect(() => { if (mode !== "closed") { inputRef.current?.focus(); localStorage.setItem("legacydb-help-state", "open"); } else localStorage.setItem("legacydb-help-state", "closed"); }, [mode]);
  useEffect(() => { if (mode === "closed" && openedRef.current) launcherRef.current?.focus(); }, [mode]);
  useEffect(() => () => abortRef.current?.abort(), []);
  useEffect(() => { if (mode !== "expanded") return; const key = (event: globalThis.KeyboardEvent) => { if (event.key === "Escape") close(); if (event.key === "Tab") { const items = [...(panelRef.current?.querySelectorAll<HTMLElement>("button:not(:disabled),a[href],textarea:not(:disabled)") || [])]; if (!items.length) return; if (event.shiftKey && document.activeElement === items[0]) { event.preventDefault(); items.at(-1)?.focus(); } else if (!event.shiftKey && document.activeElement === items.at(-1)) { event.preventDefault(); items[0].focus(); } } }; document.addEventListener("keydown", key); return () => document.removeEventListener("keydown", key); });
  function close() { abortRef.current?.abort(); setPending(false); setMode("closed"); }
  function reset() { abortRef.current?.abort(); setMessages([]); setQuestion(""); setError(null); setPending(false); }
  async function send(value = question) { const clean = value.trim().slice(0, MAX_LENGTH); if (!clean || pending) return; const userMessage: HelpMessage = { id: id(), role: "user", text: clean }; setMessages(rows => [...rows, userMessage]); setQuestion(""); setError(null); setPending(true); const controller = new AbortController(); abortRef.current = controller; try { const response = await askApplicationHelp(clean, pathname, controller.signal); setMessages(rows => [...rows, { id: id(), role: "assistant", text: response.answer || fallback, response }]); } catch (cause) { if ((cause as { name?: string }).name !== "AbortError") setError(cause instanceof Error ? cause.message : "Application help is temporarily unavailable."); } finally { if (!controller.signal.aborted) setPending(false); } }
  function keyDown(event: KeyboardEvent<HTMLTextAreaElement>) { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void send(); } }
  const latestArticle = articleForQuestion([...messages].reverse().find(message => message.role === "user")?.text || "");
  const mayNavigate = (route?: string) => route && (!route.includes("admin/users") || ["super_admin","organization_admin"].includes(user?.role || ""));
  return <>
    {mode === "closed" && <button ref={launcherRef} className="help-launcher" aria-label="Open application help" title="Application Help" onClick={() => { openedRef.current = true; setMode("open"); }}><span aria-hidden="true">?</span></button>}
    {mode !== "closed" && <section ref={panelRef} className="help-panel" data-expanded={mode === "expanded"} role={mode === "expanded" ? "dialog" : "complementary"} aria-modal={mode === "expanded" || undefined} aria-label="Application Help">
      <header className="help-header"><div><strong>App Help</strong><small><span aria-hidden="true">●</span> Guidance for using LegacyDB Copilot</small></div><div><button aria-label="Minimize application help" onClick={() => setMode("closed")}>—</button><button aria-label={mode === "expanded" ? "Restore application help" : "Expand application help"} onClick={() => setMode(mode === "expanded" ? "open" : "expanded")}>{mode === "expanded" ? "↘" : "↗"}</button><button aria-label="Close application help" onClick={close}>×</button></div></header>
      <div className="help-context"><strong>{messages.length ? "Application guidance" : "How can I help you use LegacyDB Copilot?"}</strong><small>Suggestions are tailored to this page. This assistant cannot perform actions or query databases.</small></div>
      <div className="help-conversation" aria-live="polite">{messages.map(message => <article key={message.id} className={`help-message ${message.role}`}><span>{message.role === "assistant" ? "App Help" : "You"}</span><p>{message.text}</p>{message.response?.steps.length ? <ol>{message.response.steps.map(step => <li key={step}>{step}</li>)}</ol> : null}{message.response?.warnings.map(warning => <small className="help-warning" key={warning}>⚠ {warning}</small>)}{message.role === "assistant" && <div className="help-message-actions"><button onClick={() => void navigator.clipboard?.writeText([message.text, ...(message.response?.steps || [])].join("\n"))}>Copy answer</button></div>}</article>)}{pending && <div className="help-typing" role="status">App Help is finding approved guidance…</div>}{error && <div className="help-error" role="alert"><span>{error}</span><button onClick={() => void send(messages.at(-1)?.text || question)}>Retry</button></div>}</div>
      <div className="help-suggestions" aria-label="Suggested help questions">{suggestions.map(article => <button key={article.id} disabled={pending} onClick={() => void send(article.question)}>{article.question}</button>)}</div>
      {mayNavigate(latestArticle?.route) && <Link className="help-navigation-link" to={latestArticle!.route!}>Open {latestArticle!.category}</Link>}
      <form className="help-composer" onSubmit={(event: FormEvent) => { event.preventDefault(); void send(); }}><textarea ref={inputRef} aria-label="Ask application help" maxLength={MAX_LENGTH} rows={2} placeholder="Ask how to use the application…" value={question} onKeyDown={keyDown} onChange={event => setQuestion(event.target.value)}/><button aria-label="Send help question" disabled={!question.trim() || pending}>Send</button></form>
      <footer><button onClick={reset} disabled={!messages.length}>Start over</button><span>Approved help · v{HELP_KNOWLEDGE_VERSION}</span></footer>
    </section>}
  </>;
}
