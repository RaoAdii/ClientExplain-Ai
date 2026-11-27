import type { Citation, ProcessResult } from "@/types/analysis";
import { CitationViewer } from "./citation-viewer";

function DetailList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return <div><h4>{title}</h4><ul>{items.map((item, index) => <li key={index}>{item}</li>)}</ul></div>;
}

function evidenceLocation(filename: string | null, page: number | null) {
  return [filename, page === null ? null : `page ${page}`].filter(Boolean).join(", ");
}

export function ProcessResults({ result, citations }: { result: ProcessResult; citations: Citation[] }) {
  if (!result.stages.length) return <p>No stored analysis yet. Submit process text to start an analysis when the provider is available.</p>;
  return <div className="process-results">
    <p className="review-notice"><strong>Professional review required.</strong> A qualified lawyer must review this explanation and its sources before use. Source support does not establish legal accuracy.</p>
    {result.process_name && <h3>{result.process_name}</h3>}
    {result.summary && <p className="preserve-whitespace">{result.summary}</p>}
    <dl className="project-details">{[["Jurisdiction", result.jurisdiction], ["Legal area", result.legal_area], ["Applicability date", result.applicability_date], ["Audience", result.audience], ["Language", result.language], ["Complexity", result.complexity]].filter(([, value]) => value).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    {result.main_objective && <p><strong>Main objective:</strong> {result.main_objective}</p>}
    {result.parties_involved.length > 0 && <DetailList title="Parties involved" items={result.parties_involved} />}
    {result.facts.length > 0 && <section><h3>Facts from selected documents</h3><ul>{result.facts.map((fact, index) => <li key={`${fact.evidence_chunk_id}-${index}`}><p>{fact.statement}</p><blockquote>{fact.excerpt}</blockquote><small>Unverified document evidence{evidenceLocation(fact.source_filename, fact.page_number) ? `: ${evidenceLocation(fact.source_filename, fact.page_number)}` : ""}</small></li>)}</ul></section>}
    {result.financial_facts.length > 0 && <section><h3>Financial facts from selected documents</h3><ul>{result.financial_facts.map((fact, index) => <li key={`${fact.evidence_chunk_id}-${index}`}><p>{fact.label}: {fact.currency} {fact.amount} ({fact.kind === "deposit" ? "deposit" : "proposed deduction; unverified"})</p><blockquote>{fact.excerpt}</blockquote><small>Unverified document evidence{evidenceLocation(fact.source_filename, fact.page_number) ? `: ${evidenceLocation(fact.source_filename, fact.page_number)}` : ""}</small></li>)}</ul></section>}
    {result.potential_balances.length > 0 && <section><h3>Potential balances (calculated by the server)</h3><p>Deposit totals minus proposed deduction totals, calculated separately for each currency. This is not a determination that a deduction is valid or that money is owed.</p><ul>{result.potential_balances.map((balance) => <li key={balance.currency}>{balance.currency}: deposits {balance.deposit_total} − proposed deductions {balance.proposed_deductions_total} = potential balance {balance.potential_balance}</li>)}</ul></section>}
    {result.information_gaps.length > 0 && <div><h3>Information gaps</h3><ul>{result.information_gaps.map((gap, index) => <li key={index}><strong>{gap.category.replaceAll("_", " ")}:</strong> {gap.description}</li>)}</ul></div>}
    {result.missing_information.length > 0 && <DetailList title="Missing information" items={result.missing_information} />}
    {result.limitations.length > 0 && <DetailList title="Limitations" items={result.limitations} />}
    <ol className="process-stages" aria-label="Process stages">{[...result.stages].sort((a, b) => a.position - b.position).map((stage) => <li key={stage.id}>
      <h3>{stage.position}. {stage.title}</h3>
      <div className="provenance">{stage.source_backed && <span>Source-backed</span>}{stage.general_explanation && <span>General explanation</span>}<span>Stage support: {stage.verification_status}</span></div>
      <p className="preserve-whitespace">{stage.explanation}</p>
      {stage.responsible_party && <p><strong>Responsible party:</strong> {stage.responsible_party}</p>}
      {stage.estimated_duration && <p><strong>Estimated duration:</strong> {stage.estimated_duration}</p>}
      <DetailList title="Inputs" items={stage.inputs} />
      <DetailList title="Actions" items={stage.actions} />
      <DetailList title="Expected outputs" items={stage.expected_outputs} />
      <DetailList title="Decision points" items={stage.decision_points} />
      <DetailList title="Required documents" items={stage.required_documents} />
      <DetailList title="Stage limitations" items={stage.limitations} />
      <CitationViewer citations={citations.filter((citation) => citation.stage_id === stage.id)} />
    </li>)}</ol>
  </div>;
}
