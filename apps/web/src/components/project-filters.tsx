"use client";
import { useEffect, useState } from "react";
import { reviewLabels, workflowLabels } from "@/types/project";
import { Button } from "./ui/button";

export function ProjectFilters({ search, status, reviewStatus, onChange }: {
  search: string;
  status: string;
  reviewStatus: string;
  onChange: (changes: Record<string, string>) => void;
}) {
  const [searchState, setSearchState] = useState({ source: search, draft: search, pending: [] as string[] });
  const { draft } = searchState;
  if (searchState.source !== search) {
    const submitted = searchState.pending.indexOf(search);
    // A local URL acknowledgment must not replace text entered since submission.
    setSearchState({ source: search, draft: submitted < 0 ? search : draft,
      pending: submitted < 0 ? [] : searchState.pending.slice(submitted + 1) });
  }
  useEffect(() => {
    if (draft.trim() === search) return;
    const timer = setTimeout(() => {
      const next = draft.trim();
      setSearchState((current) => ({ ...current, pending: [...current.pending, next] }));
      onChange({ search: next });
    }, 300);
    return () => clearTimeout(timer);
  }, [draft, search, onChange]);
  return (
    <div className="project-filters" role="search" aria-label="Filter projects">
      <div className="field">
        <label htmlFor="project-search">Search projects</label>
        <input id="project-search" type="search" maxLength={200} placeholder="Search project context…" value={draft} onChange={(event) => setSearchState((current) => ({ ...current, draft: event.target.value }))} />
      </div>
      <div className="field">
        <label htmlFor="project-status">Workflow status filter</label>
        <select id="project-status" value={status} onChange={(event) => onChange({ status: event.target.value })}>
          <option value="">All workflow statuses</option>
          {Object.entries(workflowLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </div>
      <div className="field">
        <label htmlFor="project-review">Review status filter</label>
        <select id="project-review" value={reviewStatus} onChange={(event) => onChange({ review_status: event.target.value })}>
          <option value="">All review statuses</option>
          {Object.entries(reviewLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </div>
      {(draft || status || reviewStatus) && <Button variant="ghost" onClick={() => { setSearchState((current) => ({ ...current, draft: "", pending: [...current.pending, ""] })); onChange({ search: "", status: "", review_status: "" }); }}>Clear filters</Button>}
    </div>
  );
}
