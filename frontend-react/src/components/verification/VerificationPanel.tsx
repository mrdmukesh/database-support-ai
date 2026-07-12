import { useEffect, useState } from "react";
import { loadVerificationChecks, runAllVerificationChecks, runVerificationCheck, skipVerificationCheck } from "../../api/verification-api";
import type { VerificationCheck } from "../../models/verification";
import { VerificationCheckCard } from "./VerificationCheckCard";
import { LoadingState } from "../common/LoadingState"; import { ErrorMessage } from "../common/ErrorMessage"; import { EmptyState } from "../common/EmptyState";
import { SecondaryButton } from "../ui";
export function VerificationPanel({ investigationId }: { investigationId: string | null | undefined }) {
  const [checks, setChecks] = useState<VerificationCheck[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function refresh(signal?: AbortSignal) {
    if (!investigationId) { setChecks([]); setLoading(false); return; }
    setLoading(true); setError(null);
    try { setChecks(await loadVerificationChecks(investigationId, signal)); }
    catch (cause) { if ((cause as { name?: string })?.name !== "AbortError") setError(cause instanceof Error ? cause.message : "Verification checks failed."); }
    finally { if (!signal?.aborted) setLoading(false); }
  }
  useEffect(() => { const controller = new AbortController(); void refresh(controller.signal); return () => controller.abort(); }, [investigationId]);
  async function action(work: () => Promise<unknown>) { setBusy(true); setError(null); try { await work(); await refresh(); } catch (cause) { setError(cause instanceof Error ? cause.message : "Verification action failed."); } finally { setBusy(false); } }
  if (!investigationId) return <p>Generate an investigation to see verification checks.</p>;
  if (loading) return <LoadingState message="Loading verification checks..." />;
  return <section className="verification-panel" aria-labelledby="verification-panel-title"><h3 className="visually-hidden" id="verification-panel-title">Verification Checks</h3>
    {error ? <ErrorMessage message={error} /> : null}
    {checks.length ? <><SecondaryButton disabled={busy} onClick={() => void action(async () => { const result = await runAllVerificationChecks(investigationId); setChecks(result.checks); })}>Run all pending safe checks</SecondaryButton>
      <div className="verification-list">{checks.map((check) => <VerificationCheckCard key={check.id} check={check} busy={busy}
        onRun={(id) => void action(() => runVerificationCheck(id))} onSkip={(id) => void action(() => skipVerificationCheck(id))} />)}</div></>
      : <EmptyState message="No verification checks were suggested." />}
  </section>;
}
