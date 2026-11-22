import type { Citation } from "@/types/analysis";
const sourceLabels: Record<string, string> = { user_document: "User document", legislation: "Legislation", judgment: "Judgment", government_publication: "Government publication", secondary: "Secondary source" };
export function CitationViewer({ citations }: { citations: Citation[] }) {
  if (!citations.length) return <p className="muted">No stored citations for this stage.</p>;
  return <div className="citation-viewer"><h4>Source citations</h4>{citations.map((citation) => {
    const safeUrl = citation.source_url && /^https?:\/\//i.test(citation.source_url) ? citation.source_url : null;
    return <article className="citation" key={citation.id} aria-label={`Citation for ${citation.claim_text}`}>
      <div className="provenance"><span>{sourceLabels[citation.source_type] || citation.source_type}</span><span>{citation.verification_status === "verified" ? "Verified" : "Unverified"}</span><span>Claim support: {citation.validation_status}</span></div>
      <p><strong>{citation.source_filename || citation.source_title || "Source"}</strong>{citation.page_number !== null && citation.page_number !== undefined && <span> · Page {citation.page_number}</span>}{citation.heading && <span> · {citation.heading}</span>}</p>
      {citation.citation_reference && <p>{citation.citation_reference}</p>}<p>{citation.claim_text}</p><blockquote className="preserve-whitespace">{citation.excerpt}</blockquote>
      {safeUrl && <a className="text-link" href={safeUrl} target="_blank" rel="noopener noreferrer">Open source</a>}
    </article>;
  })}</div>;
}
