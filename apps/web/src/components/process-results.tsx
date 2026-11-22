import type { Citation, ProcessResult } from "@/types/analysis";
import { CitationViewer } from "./citation-viewer";
export function ProcessResults({ result, citations }: { result: ProcessResult; citations: Citation[] }) {
  if (!result.stages.length) return <p>No stored analysis yet. Submit process text to start an analysis when the provider is available.</p>;
  return <div className="process-results"><p className="review-notice"><strong>Professional review required.</strong> A qualified lawyer must review this explanation and its sources before use. Source support does not establish legal accuracy.</p>
    {result.process_name && <h3>{result.process_name}</h3>}{result.summary && <p className="preserve-whitespace">{result.summary}</p>}
    <dl className="project-details">{[["Jurisdiction", result.jurisdiction], ["Legal area", result.legal_area], ["Applicability date", result.applicability_date], ["Audience", result.audience], ["Complexity", result.complexity]].filter(([, value]) => value).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    {result.missing_information.length > 0 && <div><h3>Missing information</h3><ul>{result.missing_information.map((text, index) => <li key={index}>{text}</li>)}</ul></div>}
    {result.limitations.length > 0 && <div><h3>Limitations</h3><ul>{result.limitations.map((text, index) => <li key={index}>{text}</li>)}</ul></div>}
    <ol className="process-stages" aria-label="Process stages">{[...result.stages].sort((a, b) => a.position - b.position).map((stage) => <li key={stage.id}>
      <h3>{stage.position}. {stage.title}</h3><div className="provenance">{stage.source_backed && <span>Source-backed</span>}{stage.general_explanation && <span>General explanation</span>}<span>Stage support: {stage.verification_status}</span></div><p className="preserve-whitespace">{stage.explanation}</p>
      {stage.responsible_party && <p><strong>Responsible party:</strong> {stage.responsible_party}</p>}{stage.estimated_duration && <p><strong>Estimated duration:</strong> {stage.estimated_duration}</p>}
      {stage.required_documents.length > 0 && <div><h4>Required documents</h4><ul>{stage.required_documents.map((text, index) => <li key={index}>{text}</li>)}</ul></div>}
      {stage.limitations.length > 0 && <div><h4>Stage limitations</h4><ul>{stage.limitations.map((text, index) => <li key={index}>{text}</li>)}</ul></div>}
      <CitationViewer citations={citations.filter((citation) => citation.stage_id === stage.id)} />
    </li>)}</ol>
  </div>;
}
