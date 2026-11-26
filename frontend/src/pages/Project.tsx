import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Project } from "../App";
import SvgPlot from "../components/SvgPlot";

type Run = {
  id: number;
  type: string;
  status: string;
  result: any;
};

export default function ProjectPage({ project, onBack }: { project: Project; onBack: () => void }) {
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState("");
  const timer = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timer.current) window.clearInterval(timer.current);
    };
  }, []);

  async function start() {
    setError("");
    try {
      const r = await api.createRun(project.id, "kinematics_four_bar", {});
      setRun(r);
      timer.current = window.setInterval(async () => {
        const cur = await api.run(r.id);
        setRun(cur);
        if (cur.status === "done" || cur.status === "error") {
          if (timer.current) window.clearInterval(timer.current);
        }
      }, 500);
    } catch (err) {
      setError(String(err));
    }
  }

  const res = run?.result;
  return (
    <div style={{ maxWidth: 760, margin: "40px auto", fontFamily: "sans-serif" }}>
      <button onClick={onBack}>← retour</button>
      <h1>{project.name}</h1>
      <p style={{ color: "#555" }}>{project.description}</p>

      <section style={{ marginTop: 24 }}>
        <h2>Module schéma cinématique (démo)</h2>
        <p>
          Lance une simulation de mécanisme quatre-barres (manivelle motorisée, une révolution) :
        </p>
        <button onClick={start} style={{ padding: "8px 16px" }} disabled={run?.status === "running" || run?.status === "queued"}>
          Lancer la simulation
        </button>
        {run && <p>Run #{run.id} — statut : <strong>{run.status}</strong></p>}
        {error && <p style={{ color: "red" }}>{error}</p>}
        {res?.error && <p style={{ color: "red" }}>{res.error}</p>}
        {res?.ok && (
          <div>
            <h3>Angle de la manivelle vs temps</h3>
            <SvgPlot series={[{ x: res.t, y: res.theta_crank, color: "#1f77b4" }]} />
            <h3>Trajectoire du point C de la bielle</h3>
            <SvgPlot
              series={[{ x: res.path_C.map((p: number[]) => p[0]), y: res.path_C.map((p: number[]) => p[1]), color: "#d62728" }]}
            />
            <p style={{ color: "#555" }}>Résidu max des contraintes : {res.max_residual?.toExponential(2)}</p>
          </div>
        )}
      </section>
    </div>
  );
}
