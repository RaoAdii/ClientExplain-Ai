"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Project } from "@/types/project";
import type { AnalysisRequest, Job } from "@/types/analysis";
import { api } from "@/services/api";
import { Button } from "./ui/button";
export function AnalysisForm({ project, selected, selectionReady, disabled, onSubmitted }: { project: Project; selected: string[]; selectionReady: boolean; disabled: boolean; onSubmitted: (job: Job) => void }) {
  const provider = useQuery({
    queryKey: ["ai-status"],
    queryFn: ({ signal }) => api<{ provider: "openai" | "ollama" | "groq"; available: boolean; reason: string | null }>("ai/status", { signal }),
    retry: false,
    staleTime: 30000,
  });
  const [text, setText] = useState("");
  const [jurisdiction, setJurisdiction] = useState(project.jurisdiction);
  const [legalArea, setLegalArea] = useState(project.legal_area || "General");
  const [language, setLanguage] = useState(project.language || "English");
  const [audience, setAudience] = useState(project.target_audience || "Client");
  const [complexity, setComplexity] = useState<AnalysisRequest["complexity"]>(["simple", "standard", "detailed"].includes(project.complexity.toLowerCase()) ? project.complexity.toLowerCase() as AnalysisRequest["complexity"] : "simple");
  const [date, setDate] = useState("");
  const [consent, setConsent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const selectionKey = JSON.stringify([...selected].sort());
  const isLocal = provider.data?.provider === "ollama";
  const isGroq = provider.data?.provider === "groq";
  const allowed = !!text.trim() && !!jurisdiction.trim() && !!legalArea.trim() && !!language.trim() && !!audience.trim() && selectionReady && provider.data?.available === true && (isLocal || !selected.length || consent === selectionKey);
  async function submit(event: React.FormEvent) {
    event.preventDefault(); if (!allowed || busy || disabled) return;
    setBusy(true); setError(null);
    const data: AnalysisRequest = { process_text: text.trim(), jurisdiction: jurisdiction.trim(), legal_area: legalArea.trim(), language: language.trim(), target_audience: audience.trim(), complexity, applicability_date: date || null, selected_document_ids: selected };
    try { const job = await api<Job>(`projects/${project.id}/analyze`, { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify(data) }); onSubmitted(job); }
    catch (failure) { setError(failure instanceof Error ? failure.message : "Analysis could not be submitted. Try again."); }
    finally { setBusy(false); }
  }
  return <form className="analysis-form" onSubmit={submit}>
    <div className="field"><label htmlFor="process-text">Process text</label><textarea id="process-text" required maxLength={20000} rows={7} value={text} onChange={(event) => setText(event.target.value)} aria-describedby="analysis-disclosure" /></div>
    <div className="project-context-fields">
      <div className="field"><label htmlFor="analysis-jurisdiction">Analysis jurisdiction</label><input id="analysis-jurisdiction" required maxLength={120} value={jurisdiction} onChange={(event) => setJurisdiction(event.target.value)} /></div>
      <div className="field"><label htmlFor="analysis-legal-area">Analysis legal area</label><input id="analysis-legal-area" required maxLength={200} value={legalArea} onChange={(event) => setLegalArea(event.target.value)} /></div>
      <div className="field"><label htmlFor="analysis-language">Analysis language</label><input id="analysis-language" required maxLength={200} value={language} onChange={(event) => setLanguage(event.target.value)} /></div>
      <div className="field"><label htmlFor="analysis-audience">Analysis audience</label><input id="analysis-audience" required maxLength={200} value={audience} onChange={(event) => setAudience(event.target.value)} /></div>
      <div className="field"><label htmlFor="analysis-complexity">Analysis complexity</label><select id="analysis-complexity" value={complexity} onChange={(event) => setComplexity(event.target.value as AnalysisRequest["complexity"])}><option value="simple">Simple</option><option value="standard">Standard</option><option value="detailed">Detailed</option></select></div>
      <div className="field"><label htmlFor="applicability-date">Applicability date (optional)</label><input id="applicability-date" type="date" value={date} onChange={(event) => setDate(event.target.value)} /></div>
    </div>
    <p id="analysis-disclosure">{isLocal ? "Process text and selected document excerpts are sent to the configured local Ollama server. Professional review is required before use." : isGroq ? "Process text and relevant excerpts from selected documents are sent to Groq. Only select documents you are authorized to process. Uploaded documents remain unverified evidence. Professional review is required before use." : "Process text and relevant excerpts from selected documents are sent to the configured external AI provider. Only select documents you are authorized to process. Professional review is required before use."}</p>
    {provider.isPending && <p role="status">Checking AI provider availability…</p>}
    {provider.error && <p role="alert">AI provider status could not be checked. Analysis is unavailable until the service is reachable.</p>}
    {provider.data && !provider.data.available && <p role="alert">{provider.data.reason === "models_not_installed" ? "The configured local AI models are not installed in Ollama." : provider.data.reason === "unreachable" ? "The local Ollama server is unreachable. Start it and verify both configured models are installed." : "AI analysis is not configured. Configure local Ollama or explicitly enable and configure the external provider."}</p>}
    {provider.data?.available && isLocal && <p role="status">Local Ollama analysis is available. Model output remains unverified and requires professional review.</p>}
    {provider.data?.available && !isLocal && <p role="status">The external AI provider is configured. Live provider availability is checked when analysis runs.</p>}
    <p>{selected.length} document(s) selected. Only documents with completed parsing can be included.</p>
    {selected.length === 0 && <p>No documents selected. This analysis will use process text only.</p>}
    {selected.length > 0 && !isLocal && <label className="checkbox-label"><input type="checkbox" checked={consent === selectionKey} onChange={(event) => setConsent(event.target.checked ? selectionKey : "")} />I authorize external processing of the selected documents.</label>}
    {selected.length > 0 && !selectionReady && <p role="alert">Selected documents are no longer ready. Deselect them or wait for parsing to complete.</p>}
    {error && <p role="alert">{error}</p>}
    {disabled && <p>An analysis job is active. Wait for it to finish before submitting again.</p>}
    <Button disabled={!allowed || busy || disabled}>{busy ? "Submitting analysis…" : selected.length ? "Analyze process and selected documents" : "Analyze process"}</Button>
  </form>;
}

