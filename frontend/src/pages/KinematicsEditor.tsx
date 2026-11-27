import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Project } from "../App";
import SvgPlot from "../components/SvgPlot";
import {
  Diagram,
  JointNode,
  JointType,
  Solid,
  Vec,
  assignJointToSolid,
  emptyDiagram,
  ensureGround,
  linkNewSolid,
  removeJoint,
  removeSolid,
  solidFrame,
  toBackendDiagram,
  toWorldPoint,
  uid,
} from "../kinematics/model";

type Tool = "select" | "revolute" | "prismatic" | "fixed" | "lier" | "ajouter" | "bati" | "motor" | "delete";

const TOOLS: { id: Tool; label: string }[] = [
  { id: "select", label: "Sélection / déplacer" },
  { id: "revolute", label: "Pivot (clic = centre exact)" },
  { id: "prismatic", label: "Glissière" },
  { id: "fixed", label: "Encastrement" },
  { id: "lier", label: "Relier 2 liaisons → nouveau solide" },
  { id: "ajouter", label: "Ajouter une liaison au solide sélectionné" },
  { id: "bati", label: "Attacher une liaison au BÂTI" },
  { id: "motor", label: "Moteur sur le solide d'une liaison" },
  { id: "delete", label: "Supprimer" },
];

const JOINT_LABEL: Record<JointType, string> = { revolute: "Pivot", prismatic: "Glissière", fixed: "Encastrement" };
const SOLID_COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#8c564b"];

const distToSegment = (p: Vec, a: Vec, b: Vec): number => {
  const abx = b[0] - a[0];
  const aby = b[1] - a[1];
  const den = abx * abx + aby * aby;
  const t = den > 0 ? Math.max(0, Math.min(1, ((p[0] - a[0]) * abx + (p[1] - a[1]) * aby) / den)) : 0;
  return Math.hypot(p[0] - (a[0] + t * abx), p[1] - (a[1] + t * aby));
};

export default function KinematicsEditor({ project, onBack }: { project: Project; onBack: () => void }) {
  const [diagram, setDiagram] = useState<Diagram>(emptyDiagram());
  const [tool, setTool] = useState<Tool>("select");
  const [sel, setSel] = useState<{ kind: "joint" | "solid"; id: string } | null>(null);
  const [pendingLink, setPendingLink] = useState<string | null>(null);
  const [view, setView] = useState({ s: 300, ox: 420, oy: 280 });
  const [msg, setMsg] = useState("");
  const [analysis, setAnalysis] = useState<any>(null);
  const [run, setRun] = useState<any>(null);
  const [frame, setFrame] = useState<number | null>(null);
  const [backendDiag, setBackendDiag] = useState<any>(null);
  const drag = useRef<{ jointId: string } | null>(null);
  const pan = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const timer = useRef<number | null>(null);
  const raf = useRef<number | null>(null);

  const stopAnim = () => {
    if (raf.current) {
      cancelAnimationFrame(raf.current);
      raf.current = null;
    }
    setFrame(null);
  };

  useEffect(() => {
    stopAnim();
  }, [diagram]);

  useEffect(() => {
    api
      .diagrams(project.id)
      .then((list) => {
        const d = list.find((x: any) => x.domain === "kinematics");
        if (d?.data?.joints && d?.data?.solids) setDiagram(d.data);
      })
      .catch(() => {});
    return () => {
      if (timer.current) window.clearInterval(timer.current);
      if (raf.current) cancelAnimationFrame(raf.current);
    };
  }, [project.id]);

  useEffect(() => {
    if (raf.current) {
      cancelAnimationFrame(raf.current);
      raf.current = null;
    }
    if (run?.status === "done" && run.result?.ok) {
      const steps = run.result.t.length - 1;
      const period = run.result.period || 1;
      const start = performance.now();
      const loop = () => {
        const ph = (((performance.now() - start) / 1000) % period) / period;
        setFrame(Math.floor(ph * steps));
        raf.current = requestAnimationFrame(loop);
      };
      raf.current = requestAnimationFrame(loop);
    } else {
      setFrame(null);
    }
  }, [run?.status, run?.result?.ok]);

  const toWorldXY = (e: React.MouseEvent<SVGSVGElement>): Vec => {
    const rect = svgRef.current!.getBoundingClientRect();
    return [((e.clientX - rect.left) - view.ox) / view.s, (view.oy - (e.clientY - rect.top)) / view.s];
  };
  const sx = (x: number) => view.ox + x * view.s;
  const sy = (y: number) => view.oy - y * view.s;

  const jointWorld = (j: JointNode): Vec => {
    if (frame !== null && run?.result?.ok && backendDiag) {
      const bj = backendDiag.joints.find((x: any) => x.node === j.id);
      const rb = bj && run.result.bodies.find((x: any) => x.id === bj.a);
      const q = rb?.qs?.[frame];
      const pt = rb?.points?.[bj?.la];
      if (bj && q && pt) return toWorldPoint(q[0], q[1], q[2], pt);
    }
    return [j.x, j.y];
  };

  const pickJoint = (w: Vec): JointNode | null => {
    let best: JointNode | null = null;
    let bd = 0.08;
    for (const j of diagram.joints) {
      const [wx, wy] = jointWorld(j);
      const d = Math.hypot(wx - w[0], wy - w[1]);
      if (d < bd) {
        best = j;
        bd = d;
      }
    }
    return best;
  };

  const pickSolid = (w: Vec): Solid | null => {
    let best: Solid | null = null;
    let bd = 0.04;
    for (const s of diagram.solids) {
      const pts = s.jointIds.map((id) => jointWorld(diagram.joints.find((j) => j.id === id)!));
      for (let i = 0; i + 1 < pts.length; i++) {
        const d = distToSegment(w, pts[i], pts[i + 1]);
        if (d < bd) {
          best = s;
          bd = d;
        }
      }
      if (pts.length === 1) {
        const d = Math.hypot(pts[0][0] - w[0], pts[0][1] - w[1]);
        if (d < bd) {
          best = s;
          bd = d;
        }
      }
    }
    return best;
  };

  const onDown = (e: React.MouseEvent<SVGSVGElement>) => {
    const w = toWorldXY(e);
    if (tool === "revolute" || tool === "prismatic" || tool === "fixed") {
      const existing = pickJoint(w);
      if (existing && Math.hypot(existing.x - w[0], existing.y - w[1]) < 0.04) {
        setSel({ kind: "joint", id: existing.id });
        setMsg("Une liaison existe déjà à cet endroit : elle est sélectionnée (pas de doublon).");
        return;
      }
      const id = uid();
      const j: JointNode = { id, type: tool, x: w[0], y: w[1], axisDeg: 0, sideA: null, sideB: null };
      setDiagram((d) => ({ ...d, joints: [...d.joints, j] }));
      setSel({ kind: "joint", id });
      return;
    }
    const j = pickJoint(w);
    if (tool === "bati" || tool === "lier" || tool === "ajouter" || tool === "motor" || tool === "delete") {
      if (!j) {
        setMsg("Clique sur le symbole de la liaison (cercle, croix ou glisseur).");
        return;
      }
    }
    if (tool === "bati") {
      if (!j) return;
      setDiagram((d) => {
        const g = ensureGround(d);
        return assignJointToSolid(g, j.id, g.groundId!);
      });
      setMsg("Liaison attachée au bâti.");
      return;
    }
    if (tool === "lier") {
      if (!j) return;
      if (!pendingLink) {
        setPendingLink(j.id);
        setMsg("Clique maintenant la 2ᵉ liaison du même solide.");
        return;
      }
      if (pendingLink === j.id) {
        setPendingLink(null);
        return;
      }
      const res = linkNewSolid(diagram, pendingLink, j.id);
      setDiagram(res.diagram);
      setMsg(res.error ?? "Nouveau solide créé (relie les 2 liaisons).");
      setPendingLink(null);
      if (!res.error) setSel({ kind: "solid", id: res.diagram.solids[res.diagram.solids.length - 1].id });
      return;
    }
    if (tool === "ajouter") {
      if (!j) return;
      if (sel?.kind !== "solid") {
        setMsg("Sélectionne d'abord un solide dans le panneau de droite.");
        return;
      }
      setDiagram((d) => assignJointToSolid(d, j.id, sel.id));
      setMsg("Liaison ajoutée au solide sélectionné.");
      return;
    }
    if (tool === "motor") {
      if (!j) return;
      const sid = j.sideA && j.sideA !== diagram.groundId ? j.sideA : j.sideB;
      const s = sid ? diagram.solids.find((x) => x.id === sid) : null;
      if (!s || s.grounded) {
        setMsg("Le moteur se met sur un solide mobile (liaison entre ce solide et le bâti).");
        return;
      }
      setDiagram((d) => ({ ...d, motor: { solid: s.id, omega: 2 * Math.PI, theta0: solidFrame(s, d).theta } }));
      setMsg(`Moteur sur « ${s.name} » (ω = 2π rad/s, 1 tour/s).`);
      return;
    }
    if (tool === "delete") {
      if (j) {
        setDiagram((d) => removeJoint(d, j.id));
        setMsg("Liaison supprimée.");
        return;
      }
      const s = pickSolid(w);
      if (s) {
        setDiagram((d) => removeSolid(d, s.id));
        setMsg(`Solide « ${s.name} » supprimé (ses liaisons restent, détachées).`);
      }
      return;
    }
    if (j) {
      setSel({ kind: "joint", id: j.id });
      drag.current = { jointId: j.id };
      return;
    }
    const s = pickSolid(w);
    if (s) {
      setSel({ kind: "solid", id: s.id });
      return;
    }
    pan.current = { x: e.clientX, y: e.clientY, ox: view.ox, oy: view.oy };
  };

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (drag.current) {
      const w = toWorldXY(e);
      const id = drag.current.jointId;
      setDiagram((d) => ({
        ...d,
        joints: d.joints.map((j) => (j.id === id ? { ...j, x: w[0], y: w[1] } : j)),
      }));
    } else if (pan.current) {
      setView((v) => ({
        ...v,
        ox: pan.current!.ox + (e.clientX - pan.current!.x),
        oy: pan.current!.oy + (e.clientY - pan.current!.y),
      }));
    }
  };
  const onUp = () => {
    drag.current = null;
    pan.current = null;
  };

  const selJoint = sel?.kind === "joint" ? diagram.joints.find((j) => j.id === sel.id) : null;
  const selSolid = sel?.kind === "solid" ? diagram.solids.find((s) => s.id === sel.id) : null;

  const save = async () => {
    try {
      await api.saveDiagram(project.id, "kinematics", diagram);
      setMsg("Schéma enregistré.");
    } catch (e) {
      setMsg(String(e));
    }
  };

  const analyze = async () => {
    try {
      const bd = toBackendDiagram(diagram);
      setAnalysis(await api.analyze(project.id, "kinematics", bd));
      setMsg("");
    } catch (e) {
      setMsg(String(e));
    }
  };

  const simulate = async () => {
    setMsg("");
    setRun(null);
    setAnalysis(null);
    try {
      const bd = toBackendDiagram(diagram);
      setBackendDiag(bd);
      const r = await api.createRun(project.id, "kinematics", { diagram: bd, steps: 240 });
      setRun(r);
      if (timer.current) window.clearInterval(timer.current);
      timer.current = window.setInterval(async () => {
        const cur = await api.run(r.id);
        setRun(cur);
        if (cur.status === "done" || cur.status === "error") {
          if (timer.current) window.clearInterval(timer.current);
        }
      }, 400);
    } catch (e) {
      setMsg(String(e));
    }
  };

  const motorThetaSeries = () => {
    if (!run?.result?.ok || !diagram.motor) return null;
    const rb = run.result.bodies.find((x: any) => x.id === diagram.motor!.solid);
    if (!rb) return null;
    return { x: run.result.t, y: rb.qs.map((q: number[]) => q[2]) };
  };

  const inputStyle = { width: 90, padding: 4 };

  return (
    <div style={{ fontFamily: "sans-serif", padding: 12 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <button onClick={onBack}>← projets</button>
        <h2 style={{ margin: 0 }}>{project.name}</h2>
        <button onClick={save}>Enregistrer</button>
        <button onClick={analyze}>Analyser (m, h)</button>
        <button onClick={simulate} disabled={!!run && (run.status === "running" || run.status === "queued")}>
          ▶ Simuler
        </button>
        {frame !== null && <button onClick={stopAnim}>⏹ Arrêter l'animation</button>}
        <button onClick={() => setView((v) => ({ ...v, s: Math.min(3000, v.s * 1.2) }))}>Zoom +</button>
        <button onClick={() => setView((v) => ({ ...v, s: Math.max(50, v.s / 1.2) }))}>Zoom −</button>
        {msg && <span style={{ color: "#1f77b4" }}>{msg}</span>}
        {run && <span>Run #{run.id} : <strong>{run.status}</strong></span>}
      </div>

      <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {TOOLS.map((t) => (
            <button
              key={t.id}
              onClick={() => {
                setTool(t.id);
                setPendingLink(null);
              }}
              style={{
                padding: "6px 10px",
                textAlign: "left",
                background: tool === t.id ? "#cfe3ff" : "#fff",
                border: "1px solid #bbb",
                borderRadius: 4,
                cursor: "pointer",
              }}
            >
              {t.label}
            </button>
          ))}
          <div style={{ marginTop: 8, fontSize: 12, color: "#555" }}>
            <div>Méthode : on pose d'abord les</div>
            <div>liaisons (clic = centre exact),</div>
            <div>puis on les relie en solides.</div>
            <div>Un solide = un trait entre ses liaisons.</div>
            {pendingLink && <div style={{ color: "#d62728" }}>… en attente de la 2ᵉ liaison</div>}
          </div>
        </div>

        <svg
          ref={svgRef}
          width={840}
          height={520}
          style={{ border: "1px solid #999", background: "#fafafa", touchAction: "none" }}
          onMouseDown={onDown}
          onMouseMove={onMove}
          onMouseUp={onUp}
          onMouseLeave={onUp}
        >
          <line x1={0} y1={sy(0)} x2={840} y2={sy(0)} stroke="#ddd" />
          <line x1={sx(0)} y1={0} x2={sx(0)} y2={520} stroke="#ddd" />
          {diagram.solids.map((s, i) => {
            const pts = s.jointIds.map((id) => jointWorld(diagram.joints.find((j) => j.id === id)!));
            if (pts.length === 0) return null;
            const color = s.grounded ? "#888" : SOLID_COLORS[i % SOLID_COLORS.length];
            const selS = sel?.kind === "solid" && sel.id === s.id;
            const label =
              pts.reduce((a, p) => [a[0] + p[0] / pts.length, a[1] + p[1] / pts.length], [0, 0] as Vec);
            return (
              <g key={s.id}>
                {pts.length > 1 && (
                  <polyline
                    points={pts.map((p) => `${sx(p[0])},${sy(p[1])}`).join(" ")}
                    fill="none"
                    stroke={color}
                    strokeWidth={selS ? 7 : 4}
                    strokeOpacity={s.grounded ? 0.5 : 0.8}
                  />
                )}
                <text x={sx(label[0])} y={sy(label[1]) - 10} textAnchor="middle" fontSize={13} fill={color} fontWeight="bold">
                  {s.name}
                  {s.grounded ? " (bâti)" : ""}
                  {diagram.motor?.solid === s.id ? "  ω" : ""}
                </text>
              </g>
            );
          })}
          {diagram.joints.map((j) => {
            const [wx, wy] = jointWorld(j);
            const X = sx(wx);
            const Y = sy(wy);
            const selJ = sel?.kind === "joint" && sel.id === j.id;
            const isPending = pendingLink === j.id;
            const ang = (j.axisDeg * Math.PI) / 180;
            if (j.type === "revolute")
              return (
                <g key={j.id}>
                  <circle cx={X} cy={Y} r={isPending ? 10 : 7} fill="#fff" stroke={selJ || isPending ? "#d62728" : "#1f77b4"} strokeWidth={selJ || isPending ? 3 : 2} />
                  <circle cx={X} cy={Y} r={2.5} fill="#1f77b4" />
                </g>
              );
            if (j.type === "fixed")
              return (
                <g key={j.id} stroke={selJ || isPending ? "#d62728" : "#7f7f7f"} strokeWidth={selJ || isPending ? 3 : 2}>
                  <line x1={X - 7} y1={Y - 7} x2={X + 7} y2={Y + 7} />
                  <line x1={X - 7} y1={Y + 7} x2={X + 7} y2={Y - 7} />
                </g>
              );
            const ddx = Math.cos(ang) * 16;
            const ddy = -Math.sin(ang) * 16;
            return (
              <g key={j.id}>
                <circle cx={X} cy={Y} r={6} fill="#fff" stroke={selJ || isPending ? "#d62728" : "#2ca02c"} strokeWidth={selJ || isPending ? 3 : 2} />
                <line x1={X - ddx} y1={Y - ddy} x2={X + ddx} y2={Y + ddy} stroke="#2ca02c" strokeWidth={2} />
              </g>
            );
          })}
        </svg>

        <div style={{ width: 260, border: "1px solid #ccc", borderRadius: 6, padding: 10, fontSize: 13, height: "fit-content" }}>
          <h3 style={{ marginTop: 0 }}>Propriétés</h3>
          {selJoint && (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div><strong>{JOINT_LABEL[selJoint.type]}</strong></div>
              <label>x (m) <input style={inputStyle} type="number" step={0.005} value={+selJoint.x.toFixed(4)} onChange={(e) => setDiagram((d) => ({ ...d, joints: d.joints.map((j) => (j.id === selJoint.id ? { ...j, x: parseFloat(e.target.value) || 0 } : j)) }))} /></label>
              <label>y (m) <input style={inputStyle} type="number" step={0.005} value={+selJoint.y.toFixed(4)} onChange={(e) => setDiagram((d) => ({ ...d, joints: d.joints.map((j) => (j.id === selJoint.id ? { ...j, y: parseFloat(e.target.value) || 0 } : j)) }))} /></label>
              {selJoint.type === "prismatic" && (
                <label>axe (°) <input style={inputStyle} type="number" value={selJoint.axisDeg} onChange={(e) => setDiagram((d) => ({ ...d, joints: d.joints.map((j) => (j.id === selJoint.id ? { ...j, axisDeg: parseFloat(e.target.value) || 0 } : j)) }))} /></label>
              )}
              <div style={{ color: "#777" }}>
                solides : {solidName(selJoint.sideA)} ↔ {solidName(selJoint.sideB)}
              </div>
            </div>
          )}

          <h3>Solides</h3>
          {diagram.solids.length === 0 && <div style={{ color: "#777" }}>Aucun solide. Pose des liaisons puis « Relier ».</div>}
          {diagram.solids.map((s, i) => (
            <div key={s.id} style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 4 }}>
              <button
                onClick={() => setSel({ kind: "solid", id: s.id })}
                style={{ border: "1px solid " + (s.grounded ? "#888" : SOLID_COLORS[i % SOLID_COLORS.length]), background: sel?.kind === "solid" && sel.id === s.id ? "#cfe3ff" : "#fff", borderRadius: 4, padding: "3px 8px", cursor: "pointer" }}
              >
                {s.name}
                {s.grounded ? " (bâti)" : ""}
              </button>
              <span style={{ color: "#777" }}>{s.jointIds.length} liaison(s)</span>
            </div>
          ))}
          {selSolid && (
            <button onClick={() => { setDiagram((d) => removeSolid(d, selSolid.id)); setSel(null); }} style={{ color: "#d62728" }}>
              Supprimer « {selSolid.name} »
            </button>
          )}

          <h3>Moteur</h3>
          {diagram.motor ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div>Solide : {diagram.solids.find((s) => s.id === diagram.motor!.solid)?.name}</div>
              <label>ω (rad/s) <input style={inputStyle} type="number" step={0.1} value={+diagram.motor.omega.toFixed(3)} onChange={(e) => setDiagram((d) => (d.motor ? { ...d, motor: { ...d.motor, omega: parseFloat(e.target.value) || 1 } } : d))} /></label>
              <button onClick={() => setDiagram((d) => ({ ...d, motor: null }))}>Retirer le moteur</button>
            </div>
          ) : (
            <div style={{ color: "#777" }}>Aucun moteur. Outil « Moteur » sur une liaison d'un solide mobile.</div>
          )}

          {analysis && (
            <div style={{ marginTop: 10, borderTop: "1px solid #ddd", paddingTop: 8 }}>
              <h3>Analyse structurelle</h3>
              <div>Solides : <strong>{analysis.n_solids}</strong></div>
              <div>Liaisons : <strong>{analysis.n_liaisons}</strong> (Σ contraintes = {analysis.somme_contraintes})</div>
              <div>Mobilité m = <strong>{analysis.mobilite}</strong></div>
              <div>Hyperstatisme h = <strong>{analysis.hyperstatisme}</strong></div>
              {analysis.mobilite !== 1 && <div style={{ color: "#d62728" }}>Il faut m = 1 avec un moteur pour simuler.</div>}
              {analysis.hyperstatisme > 0 && (
                <div style={{ color: "#d62728" }}>
                  Hyperstatique (h = {analysis.hyperstatisme}) : une liaison est en trop —
                  vérifie qu'elle n'est pas attachée deux fois au bâti ou au même solide.
                </div>
              )}
              {analysis.anomalies?.map((a: string, i: number) => (
                <div key={i} style={{ color: "#d62728" }}>{a}</div>
              ))}
              {analysis.grashof?.map((g: string, i: number) => (
                <div key={i} style={{ color: "#d62728", fontWeight: "bold" }}>{g}</div>
              ))}
            </div>
          )}
        </div>
      </div>

      {run?.status === "done" && run.result && !run.result.ok && (
        <p style={{ color: "red" }}>Erreur de simulation : {run.result.error}</p>
      )}
      {run?.status === "done" && run.result?.ok && motorThetaSeries() && (
        <div style={{ marginTop: 16 }}>
          <h3>Angle du solide moteur vs temps (animation en cours)</h3>
          <SvgPlot series={[{ x: motorThetaSeries()!.x, y: motorThetaSeries()!.y, color: "#1f77b4" }]} />
          <p style={{ color: "#555" }}>Résidu max des contraintes : {run.result.max_residual?.toExponential(2)}</p>
        </div>
      )}
    </div>
  );

  function solidName(id: string | null): string {
    if (!id) return "—";
    return diagram.solids.find((s) => s.id === id)?.name ?? "—";
  }
}
