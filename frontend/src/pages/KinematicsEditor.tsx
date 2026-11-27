import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Project } from "../App";
import SvgPlot from "../components/SvgPlot";
import {
  Body,
  Diagram,
  Joint,
  JointType,
  Vec,
  autoPointName,
  emptyDiagram,
  toLocal,
  toWorldPoint,
  uid,
} from "../kinematics/model";

type Tool = "select" | "body" | "ground" | "revolute" | "prismatic" | "fixed" | "motor" | "delete";

const TOOLS: { id: Tool; label: string }[] = [
  { id: "select", label: "Sélection / déplacer / panoramique" },
  { id: "body", label: "+ Solide" },
  { id: "ground", label: "+ Bâti (fixe)" },
  { id: "revolute", label: "Liaison pivot" },
  { id: "prismatic", label: "Liaison glissière" },
  { id: "fixed", label: "Encastrement" },
  { id: "motor", label: "Moteur (manivelle)" },
  { id: "delete", label: "Supprimer" },
];

const JOINT_LABEL: Record<JointType, string> = {
  revolute: "Pivot",
  prismatic: "Glissière",
  fixed: "Encastrement",
};

export default function KinematicsEditor({ project, onBack }: { project: Project; onBack: () => void }) {
  const [diagram, setDiagram] = useState<Diagram>(emptyDiagram());
  const [tool, setTool] = useState<Tool>("select");
  const [sel, setSel] = useState<{ kind: "body" | "joint"; id: string } | null>(null);
  const [pending, setPending] = useState<{ type: JointType; aId: string; la: string; pt: Vec } | null>(null);
  const [view, setView] = useState({ s: 300, ox: 420, oy: 280 });
  const [msg, setMsg] = useState("");
  const [analysis, setAnalysis] = useState<any>(null);
  const [run, setRun] = useState<any>(null);
  const [frame, setFrame] = useState<number | null>(null);
  const drag = useRef<{ bodyId: string } | null>(null);
  const pan = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const timer = useRef<number | null>(null);
  const raf = useRef<number | null>(null);

  useEffect(() => {
    api
      .diagrams(project.id)
      .then((list) => {
        const d = list.find((x: any) => x.domain === "kinematics");
        if (d?.data?.bodies) setDiagram(d.data);
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
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    return [(mx - view.ox) / view.s, (view.oy - my) / view.s];
  };
  const sx = (x: number) => view.ox + x * view.s;
  const sy = (y: number) => view.oy - y * view.s;

  const pickBody = (w: Vec): Body | null => {
    let best: Body | null = null;
    let bd = 1e9;
    for (const b of diagram.bodies) {
      const d = Math.hypot(b.x - w[0], b.y - w[1]);
      const r = Math.max(b.w, b.h) / 2 + 0.03;
      if (d < r && d < bd) {
        best = b;
        bd = d;
      }
    }
    return best;
  };

  const anchorWorld = (j: Joint): Vec => {
    const a = diagram.bodies.find((b) => b.id === j.a);
    if (!a || !a.points[j.la]) return [0, 0];
    const [x, y, th] = qOf(a);
    return toWorldPoint(x, y, th, a.points[j.la]);
  };

  const pickJoint = (w: Vec): Joint | null => {
    let best: Joint | null = null;
    let bd = 0.04;
    for (const j of diagram.joints) {
      const [wx, wy] = anchorWorld(j);
      const d = Math.hypot(wx - w[0], wy - w[1]);
      if (d < bd) {
        best = j;
        bd = d;
      }
    }
    return best;
  };

  const qOf = (b: Body): [number, number, number] => {
    if (frame !== null && run?.result?.ok) {
      const rb = run.result.bodies.find((x: any) => x.id === b.id);
      if (rb?.qs?.[frame]) return rb.qs[frame] as [number, number, number];
    }
    return [b.x, b.y, b.theta];
  };

  const onDown = (e: React.MouseEvent<SVGSVGElement>) => {
    const w = toWorldXY(e);
    if (tool === "body" || tool === "ground") {
      const id = uid();
      const b: Body = {
        id,
        name: (tool === "ground" ? "Bâti-" : "Solide-") + id.slice(0, 3),
        grounded: tool === "ground",
        x: w[0],
        y: w[1],
        theta: 0,
        w: 0.12,
        h: 0.07,
        points: {},
      };
      setDiagram((d) => ({ ...d, bodies: [...d.bodies, b] }));
      setSel({ kind: "body", id });
      return;
    }
    const b = pickBody(w);
    if (tool === "revolute" || tool === "prismatic" || tool === "fixed") {
      if (!b) return;
      if (!pending) {
        const la = autoPointName(b);
        const local = toLocal(b, w[0], w[1]);
        setDiagram((d) => ({
          ...d,
          bodies: d.bodies.map((x) => (x.id === b.id ? { ...x, points: { ...x.points, [la]: local } } : x)),
        }));
        setPending({ type: tool, aId: b.id, la, pt: [w[0], w[1]] });
      } else {
        if (b.id === pending.aId) return;
        const lb = autoPointName(b);
        const j: Joint = { id: uid(), type: pending.type, a: pending.aId, la: pending.la, b: b.id, lb, axisDeg: 0 };
        setDiagram((d) => ({
          ...d,
          bodies: d.bodies.map((x) => (x.id === b.id ? { ...x, points: { ...x.points, [lb]: toLocal(b, w[0], w[1]) } } : x)),
          joints: [...d.joints, j],
        }));
        setPending(null);
        setSel({ kind: "joint", id: j.id });
      }
      return;
    }
    if (tool === "motor") {
      if (!b) return;
      setDiagram((d) => ({ ...d, motor: { body: b.id, omega: 2 * Math.PI, theta0: 0 } }));
      setMsg(`Moteur posé sur « ${b.name} » (ω = 2π rad/s, 1 tour/s).`);
      return;
    }
    if (tool === "delete") {
      const j = pickJoint(w);
      if (j) {
        setDiagram((d) => ({ ...d, joints: d.joints.filter((x) => x.id !== j.id) }));
        return;
      }
      if (b) {
        setDiagram((d) => ({
          ...d,
          bodies: d.bodies.filter((x) => x.id !== b.id),
          joints: d.joints.filter((x) => x.a !== b.id && x.b !== b.id),
          motor: d.motor?.body === b.id ? null : d.motor,
        }));
      }
      return;
    }
    const j = pickJoint(w);
    if (j) {
      setSel({ kind: "joint", id: j.id });
      return;
    }
    if (b) {
      setSel({ kind: "body", id: b.id });
      drag.current = { bodyId: b.id };
      return;
    }
    pan.current = { x: e.clientX, y: e.clientY, ox: view.ox, oy: view.oy };
  };

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (drag.current) {
      const w = toWorldXY(e);
      const id = drag.current.bodyId;
      setDiagram((d) => ({ ...d, bodies: d.bodies.map((b) => (b.id === id ? { ...b, x: w[0], y: w[1] } : b)) }));
    } else if (pan.current) {
      setView((v) => ({ ...v, ox: pan.current!.ox + (e.clientX - pan.current!.x), oy: pan.current!.oy + (e.clientY - pan.current!.y) }));
    }
  };
  const onUp = () => {
    drag.current = null;
    pan.current = null;
  };

  const selBody = sel?.kind === "body" ? diagram.bodies.find((b) => b.id === sel.id) : null;
  const selJoint = sel?.kind === "joint" ? diagram.joints.find((j) => j.id === sel.id) : null;

  const updateBody = (patch: Partial<Body>) =>
    setDiagram((d) => ({ ...d, bodies: d.bodies.map((b) => (b.id === sel?.id ? { ...b, ...patch } : b)) }));
  const updateJoint = (patch: Partial<Joint>) =>
    setDiagram((d) => ({ ...d, joints: d.joints.map((j) => (j.id === sel?.id ? { ...j, ...patch } : j)) }));

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
      setAnalysis(await api.analyze(project.id, "kinematics", diagram));
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
      const r = await api.createRun(project.id, "kinematics", { diagram, steps: 240 });
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
    const rb = run.result.bodies.find((x: any) => x.id === diagram.motor!.body);
    if (!rb) return null;
    return { x: run.result.t, y: rb.qs.map((q: number[]) => q[2]) };
  };

  const inputStyle = { width: 80, padding: 4 };

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
                setPending(null);
              }}
              style={{ padding: "6px 10px", textAlign: "left", background: tool === t.id ? "#cfe3ff" : "#fff", border: "1px solid #bbb", borderRadius: 4, cursor: "pointer" }}
            >
              {t.label}
            </button>
          ))}
          <div style={{ marginTop: 8, fontSize: 12, color: "#555" }}>
            <div>Liaisons : cliquer sur un 1ᵉʳ solide,</div>
            <div>puis sur un 2ᵉ solide.</div>
            <div>Glissière : régler l'axe dans le panneau.</div>
            {pending && <div style={{ color: "#d62728" }}>… en attente du 2ᵉ solide</div>}
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
          {diagram.joints.map((j) => {
            const [wx, wy] = anchorWorld(j);
            const X = sx(wx);
            const Y = sy(wy);
            const selJ = sel?.kind === "joint" && sel.id === j.id;
            if (j.type === "revolute")
              return (
                <g key={j.id}>
                  <circle cx={X} cy={Y} r={7} fill="#fff" stroke={selJ ? "#d62728" : "#1f77b4"} strokeWidth={selJ ? 3 : 2} />
                  <circle cx={X} cy={Y} r={2.5} fill="#1f77b4" />
                </g>
              );
            if (j.type === "fixed")
              return (
                <g key={j.id} stroke={selJ ? "#d62728" : "#7f7f7f"} strokeWidth={selJ ? 3 : 2}>
                  <line x1={X - 7} y1={Y - 7} x2={X + 7} y2={Y + 7} />
                  <line x1={X - 7} y1={Y + 7} x2={X + 7} y2={Y - 7} />
                </g>
              );
            const ang = (j.axisDeg * Math.PI) / 180;
            const ddx = Math.cos(ang) * 16;
            const ddy = -Math.sin(ang) * 16;
            return (
              <g key={j.id}>
                <circle cx={X} cy={Y} r={6} fill="#fff" stroke={selJ ? "#d62728" : "#2ca02c"} strokeWidth={selJ ? 3 : 2} />
                <line x1={X - ddx} y1={Y - ddy} x2={X + ddx} y2={Y + ddy} stroke="#2ca02c" strokeWidth={2} />
              </g>
            );
          })}
          {diagram.bodies.map((b) => {
            const [x, y, th] = qOf(b);
            const X = sx(x);
            const Y = sy(y);
            const selB = sel?.kind === "body" && sel.id === b.id;
            return (
              <g key={b.id} transform={`translate(${X} ${Y}) rotate(${-th * 180 / Math.PI})`} style={{ cursor: "pointer" }}>
                <rect
                  x={-b.w * view.s / 2}
                  y={-b.h * view.s / 2}
                  width={b.w * view.s}
                  height={b.h * view.s}
                  fill={b.grounded ? "#d8d8d8" : selB ? "#cfe3ff" : "#eef4ff"}
                  stroke="#335"
                  strokeWidth={selB ? 2 : 1}
                />
                <text x={0} y={-b.h * view.s / 2 - 6} textAnchor="middle" fontSize={12} fill="#335">
                  {b.name}
                  {b.grounded ? " (bâti)" : ""}
                </text>
                {Object.entries(b.points).map(([k, l]) => (
                  <g key={k}>
                    <circle cx={l[0] * view.s} cy={-l[1] * view.s} r={4} fill="#d62728" />
                    <text x={l[0] * view.s + 6} y={-l[1] * view.s - 4} fontSize={10} fill="#d62728">
                      {k}
                    </text>
                  </g>
                ))}
              </g>
            );
          })}
          {pending && <circle cx={sx(pending.pt[0])} cy={sy(pending.pt[1])} r={9} fill="none" stroke="#d62728" strokeWidth={2} strokeDasharray="4 3" />}
        </svg>

        <div style={{ width: 240, border: "1px solid #ccc", borderRadius: 6, padding: 10, fontSize: 13, height: "fit-content" }}>
          <h3 style={{ marginTop: 0 }}>Propriétés</h3>
          {selBody && (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div><strong>{selBody.name}</strong></div>
              <label>nom <input style={inputStyle} value={selBody.name} onChange={(e) => updateBody({ name: e.target.value })} /></label>
              <label>x (m) <input style={inputStyle} type="number" step={0.01} value={+selBody.x.toFixed(4)} onChange={(e) => updateBody({ x: parseFloat(e.target.value) || 0 })} /></label>
              <label>y (m) <input style={inputStyle} type="number" step={0.01} value={+selBody.y.toFixed(4)} onChange={(e) => updateBody({ y: parseFloat(e.target.value) || 0 })} /></label>
              <label>angle (°) <input style={inputStyle} type="number" value={+(selBody.theta * 180 / Math.PI).toFixed(1)} onChange={(e) => updateBody({ theta: (parseFloat(e.target.value) || 0) * Math.PI / 180 })} /></label>
              <label>largeur (m) <input style={inputStyle} type="number" step={0.01} value={selBody.w} onChange={(e) => updateBody({ w: parseFloat(e.target.value) || 0.1 })} /></label>
              <label>hauteur (m) <input style={inputStyle} type="number" step={0.01} value={selBody.h} onChange={(e) => updateBody({ h: parseFloat(e.target.value) || 0.05 })} /></label>
              <label><input type="checkbox" checked={selBody.grounded} onChange={(e) => updateBody({ grounded: e.target.checked })} /> bâti (fixe)</label>
            </div>
          )}
          {selJoint && (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div><strong>Liaison : {JOINT_LABEL[selJoint.type]}</strong></div>
              <div>entre {diagram.bodies.find((b) => b.id === selJoint.a)?.name} ({selJoint.la}) et {diagram.bodies.find((b) => b.id === selJoint.b)?.name} ({selJoint.lb})</div>
              {selJoint.type === "prismatic" && (
                <label>axe (°) <input style={inputStyle} type="number" value={selJoint.axisDeg} onChange={(e) => updateJoint({ axisDeg: parseFloat(e.target.value) || 0 })} /></label>
              )}
            </div>
          )}
          {!selBody && !selJoint && <div style={{ color: "#777" }}>Sélectionne un solide ou une liaison…</div>}

          <h3>Moteur</h3>
          {diagram.motor ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div>Solide : {diagram.bodies.find((b) => b.id === diagram.motor!.body)?.name}</div>
              <label>ω (rad/s) <input style={inputStyle} type="number" step={0.1} value={+diagram.motor.omega.toFixed(3)} onChange={(e) => setDiagram((d) => (d.motor ? { ...d, motor: { ...d.motor, omega: parseFloat(e.target.value) || 1 } } : d))} /></label>
              <button onClick={() => setDiagram((d) => ({ ...d, motor: null }))}>Retirer le moteur</button>
            </div>
          ) : (
            <div style={{ color: "#777" }}>Aucun moteur. Utilise l'outil « Moteur ».</div>
          )}

          {analysis && (
            <div style={{ marginTop: 10, borderTop: "1px solid #ddd", paddingTop: 8 }}>
              <h3>Analyse structurelle</h3>
              <div>Solides (classes d'équivalence) : <strong>{analysis.n_solids}</strong></div>
              <div>Liaisons : <strong>{analysis.n_liaisons}</strong> (Σ contraintes = {analysis.somme_contraintes})</div>
              <div>Mobilité m = <strong>{analysis.mobilite}</strong></div>
              <div>Hyperstatisme h = <strong>{analysis.hyperstatisme}</strong></div>
              {analysis.mobilite !== 1 && <div style={{ color: "#d62728" }}>Il faut m = 1 avec un moteur pour simuler.</div>}
            </div>
          )}
        </div>
      </div>

      {run?.status === "done" && run.result && !run.result.ok && (
        <p style={{ color: "red" }}>Erreur de simulation : {run.result.error}</p>
      )}
      {run?.status === "done" && run.result?.ok && motorThetaSeries() && (
        <div style={{ marginTop: 16 }}>
          <h3>Angle du solide moteur vs temps (animation en cours sur le schéma)</h3>
          <SvgPlot series={[{ x: motorThetaSeries()!.x, y: motorThetaSeries()!.y, color: "#1f77b4" }]} />
          <p style={{ color: "#555" }}>Résidu max des contraintes : {run.result.max_residual?.toExponential(2)}</p>
        </div>
      )}
    </div>
  );
}
