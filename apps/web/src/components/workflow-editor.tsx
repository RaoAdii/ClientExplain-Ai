"use client";
import { useCallback, useEffect, useId, useState } from "react";
import { Background, Controls, ReactFlow, type Connection } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { api } from "@/services/api";
import type { EditorStage, WorkflowGraph } from "@/types/workflow";
import { Button } from "./ui/button";

export function WorkflowEditor({ projectId, canEdit, onSaved }: { projectId: string; canEdit: boolean; onSaved: () => void }) {
  const fieldId = useId();
  const [graph, setGraph] = useState<WorkflowGraph>();
  const [baseline, setBaseline] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
  const [selected, setSelected] = useState<string>();
  const [history, setHistory] = useState<WorkflowGraph[]>([]);
  const [future, setFuture] = useState<WorkflowGraph[]>([]);
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const dirty = !!graph && JSON.stringify(graph) !== baseline;
  const load = useCallback(async () => {
    try {
      const data = await api<WorkflowGraph>(`projects/${projectId}/workflow`);
      setError("");
      setGraph(data); setBaseline(JSON.stringify(data)); setHistory([]); setFuture([]);
    } catch (failure) { setError((failure as Error).message); }
  }, [projectId]);
  useEffect(() => {
    const controller = new AbortController();
    api<WorkflowGraph>(`projects/${projectId}/workflow`, { signal: controller.signal })
      .then((data) => { if (!controller.signal.aborted) { setGraph(data); setBaseline(JSON.stringify(data)); } })
      .catch((failure: Error) => { if (!controller.signal.aborted) setError(failure.message); });
    return () => controller.abort();
  }, [projectId]);
  useEffect(() => {
    if (!dirty) return;
    const guard = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    const navigate = (event: MouseEvent) => {
      const anchor = (event.target as Element).closest("a[href]");
      if (anchor && !anchor.getAttribute("href")?.startsWith("#") && !window.confirm("Discard unsaved workflow changes?")) {
        event.preventDefault(); event.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", guard);
    document.addEventListener("click", navigate, true);
    return () => { window.removeEventListener("beforeunload", guard); document.removeEventListener("click", navigate, true); };
  }, [dirty]);
  function change(next: WorkflowGraph) {
    if (!canEdit || saving || !graph) return;
    setHistory((items) => [...items.slice(-29), graph]); setFuture([]); setGraph(next); setNotice("");
  }
  function editStage(values: Partial<EditorStage>) {
    if (graph) change({ ...graph, stages: graph.stages.map((stage) => stage.id === selected ? { ...stage, ...values } : stage) });
  }
  function connect(connection: Connection | { source: string; target: string }) {
    if (!graph || !connection.source || !connection.target) return;
    const next = { source: connection.source, target: connection.target };
    const edges = [...graph.edges, next];
    const reaches = (start: string, goal: string, seen = new Set<string>()): boolean => {
      if (start === goal) return true;
      if (seen.has(start)) return false;
      seen.add(start);
      return graph.edges.filter((edge) => edge.source === start).some((edge) => reaches(edge.target, goal, seen));
    };
    if (graph.edges.some((edge) => edge.source === next.source && edge.target === next.target) || reaches(next.target, next.source)) {
      setError("Connections must be unique and cannot form a cycle."); return;
    }
    setError(""); change({ ...graph, edges });
  }
  async function save() {
    if (!graph) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const payload = { version: graph.version, stages: graph.stages.map((item) => ({ ...item,
        required_documents: item.required_documents.map((value) => value.trim()).filter(Boolean),
        actions: item.actions.map((value) => value.trim()).filter(Boolean),
        preconditions: item.preconditions.map((value) => value.trim()).filter(Boolean),
        outcomes: item.outcomes.map((value) => value.trim()).filter(Boolean),
        limitations: item.limitations.map((value) => value.trim()).filter(Boolean),
      })), edges: graph.edges };
      const data = await api<WorkflowGraph>(`projects/${projectId}/workflow`, { method: "PATCH", body: JSON.stringify(payload) });
      setGraph(data); setBaseline(JSON.stringify(data)); setHistory([]); setFuture([]);
      setNotice("Workflow saved."); onSaved();
    } catch (failure) { setError((failure as Error).message); }
    finally { setSaving(false); }
  }
  const stage = graph?.stages.find((item) => item.id === selected);
  return <div className="workflow-editor">
    <p>Manual edits are unverified and require professional review. Saving changes resets approval; editing a stage removes citations supporting its previous wording.</p>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    <div className="editor-toolbar">
      <Button variant="outline" disabled={saving} onClick={() => { if (!dirty || window.confirm("Discard unsaved workflow changes?")) void load(); }}>Reload workflow</Button>
      {graph && canEdit && <>
        <Button disabled={saving || graph.stages.length >= 50} onClick={() => {
          const id = crypto.randomUUID();
          let number = graph.stages.length + 1;
          while (graph.stages.some((item) => item.title === `Stage ${number}`)) number++;
          change({ ...graph, stages: [...graph.stages, { id, title: `Stage ${number}`, explanation: "Describe this stage using your source material.", responsible_party: null, required_documents: [], limitations: ["User-authored; not legally verified."], actions: [], preconditions: [], outcomes: [], status: "pending", position: { x: 40, y: graph.stages.length * 180 } }] }); setSelected(id);
        }}>Add stage</Button>
        <Button disabled={!dirty || saving} onClick={() => void save()}>{saving ? "Saving…" : "Save workflow"}</Button>
        <Button variant="outline" disabled={!history.length || saving} onClick={() => { setFuture((items) => [graph, ...items]); setGraph(history[history.length - 1]); setHistory(history.slice(0, -1)); }}>Undo</Button>
        <Button variant="outline" disabled={!future.length || saving} onClick={() => { setHistory([...history, graph]); setGraph(future[0]); setFuture(future.slice(1)); }}>Redo</Button>
      </>}
      {dirty && <span role="status">Unsaved changes</span>}
    </div>
    {!graph ? !error && <p role="status">Loading workflow…</p> : <>
      <div className="workflow-canvas" aria-label="Workflow diagram">
        <ReactFlow nodes={graph.stages.map((item, index) => ({ id: item.id, position: item.position, data: { label: `${index + 1}. ${item.title} — ${item.status.replace("_", " ")}` }, selected: selected === item.id }))}
          edges={graph.edges.map((edge) => ({ ...edge, id: `${edge.source}:${edge.target}` }))}
          nodesDraggable={canEdit && !saving} nodesConnectable={canEdit && !saving}
          onNodeClick={(_event, node) => setSelected(node.id)}
          onNodeDragStop={(_event, node) => {
            const current = graph.stages.find((item) => item.id === node.id);
            if (current && current.position.x === node.position.x && current.position.y === node.position.y) return;
            change({ ...graph, stages: graph.stages.map((item) => item.id === node.id ? { ...item, position: node.position } : item) });
          }}
          onConnect={connect} fitView minZoom={0.1} maxZoom={2} deleteKeyCode={null}>
          <Background /><Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <div className="editor-columns">
        <div><h3>Stages</h3>{!graph.stages.length && <p>Add a stage to build a workflow from your own information without an AI provider.</p>}
          <ol>{graph.stages.map((item, index) => <li key={item.id}><Button variant="ghost" onClick={() => setSelected(item.id)} aria-pressed={selected === item.id}>{index + 1}. {item.title}</Button></li>)}</ol>
          <h3>Dependencies</h3>
          <ul>{graph.edges.map((edge) => <li key={`${edge.source}:${edge.target}`}>{graph.stages.find((item) => item.id === edge.source)?.title} → {graph.stages.find((item) => item.id === edge.target)?.title} {canEdit && <Button variant="ghost" onClick={() => change({ ...graph, edges: graph.edges.filter((item) => item !== edge) })}>Remove connection</Button>}</li>)}</ul>
          {canEdit && <><label htmlFor={`${fieldId}-source`}>From stage</label><select id={`${fieldId}-source`} value={source} onChange={(event) => setSource(event.target.value)}><option value="">Choose stage</option>{graph.stages.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select>
            <label htmlFor={`${fieldId}-target`}>To stage</label><select id={`${fieldId}-target`} value={target} onChange={(event) => setTarget(event.target.value)}><option value="">Choose stage</option>{graph.stages.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select>
            <Button disabled={!source || !target || saving} onClick={() => connect({ source, target })}>Connect stages</Button></>}
        </div>
        {stage && <fieldset disabled={!canEdit || saving} className="editor-details"><legend>Stage details</legend>
          <label>Stage title<input maxLength={200} value={stage.title} onChange={(event) => editStage({ title: event.target.value })} /></label>
          <label htmlFor={`${fieldId}-explanation`}>Stage explanation</label><textarea id={`${fieldId}-explanation`} maxLength={5000} value={stage.explanation} onChange={(event) => editStage({ explanation: event.target.value })} />
          <label>Responsible party<input maxLength={1000} value={stage.responsible_party || ""} onChange={(event) => editStage({ responsible_party: event.target.value || null })} /></label>
          {([['required_documents', 'Required documents'], ['actions', 'Actions'], ['preconditions', 'Preconditions'], ['outcomes', 'Possible outcomes'], ['limitations', 'Uncertainties and limitations']] as const).map(([key, label]) => <div key={key}><label htmlFor={`${fieldId}-${key}`}>{label} (one per line)</label><textarea id={`${fieldId}-${key}`} value={stage[key].join("\n")} onChange={(event) => editStage({ [key]: event.target.value.split("\n") })} /></div>)}
          <label htmlFor={`${fieldId}-status`}>Stage status</label><select id={`${fieldId}-status`} value={stage.status} onChange={(event) => editStage({ status: event.target.value as EditorStage['status'] })}><option value="pending">Pending</option><option value="in_progress">In progress</option><option value="completed">Completed</option></select>
          <div className="editor-toolbar">{[-1, 1].map((delta) => <Button key={delta} variant="outline" disabled={graph.stages.indexOf(stage) + delta < 0 || graph.stages.indexOf(stage) + delta >= graph.stages.length} onClick={() => { const stages = [...graph.stages]; const index = stages.indexOf(stage); [stages[index], stages[index + delta]] = [stages[index + delta], stages[index]]; change({ ...graph, stages }); }}>{delta < 0 ? "Move earlier" : "Move later"}</Button>)}
            <Button variant="destructive" onClick={() => { if (window.confirm(`Delete stage "${stage.title}" and its connections?`)) { change({ ...graph, stages: graph.stages.filter((item) => item.id !== stage.id), edges: graph.edges.filter((edge) => edge.source !== stage.id && edge.target !== stage.id) }); setSelected(undefined); } }}>Delete stage</Button></div>
        </fieldset>}
      </div>
    </>}
  </div>;
}
