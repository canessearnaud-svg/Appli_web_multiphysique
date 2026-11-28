import { writeFileSync } from "fs";
import {
  Diagram,
  createLinkedJoint,
  createSolidAt,
  emptyDiagram,
  plantGround,
  solidFrame,
  toBackendDiagram,
} from "../src/kinematics/model";

let d: Diagram = emptyDiagram();
d = plantGround(d, [0, 0]);

const link = (type: "revolute" | "prismatic", p1: [number, number], p2: [number, number]) => {
  const pick = (p: [number, number]): string => {
    for (const s of d.solids) {
      if (s.grounded) {
        const f = solidFrame(s, d);
        if (Math.abs(p[0] - f.x) <= 0.12 && Math.abs(p[1] - f.y) <= 0.12) return s.id;
      } else if (s.origin && Math.hypot(p[0] - s.origin[0], p[1] - s.origin[1]) < 0.04) return s.id;
    }
    const r = createSolidAt(d, p);
    d = r.diagram;
    return r.solidId;
  };
  const a = pick(p1);
  const b = pick(p2);
  const axisDeg = type === "prismatic" ? (Math.atan2(p2[1] - p1[1], p2[0] - p1[0]) * 180) / Math.PI : 0;
  const res = createLinkedJoint(d, type, p1[0], p1[1], axisDeg, a, b);
  if (res.error) throw new Error(res.error);
  d = res.diagram;
  return res.jointId;
};

const jO = link("revolute", [0, 0], [0.15, 0]);
const jB = link("revolute", [0.15, 0], [0.4, 0]);
const jC = link("revolute", [0.4, 0], [0.45, 0]);
const jS = link("prismatic", [0.45, 0], [0, 0]);

const crank = d.solids.find((s) => s.jointIds.includes(jO) && s.jointIds.includes(jB))!;
const slider = d.solids.find((s) => s.jointIds.includes(jS) && s.jointIds.includes(jC))!;
d.motor = { solid: crank.id, omega: 2 * Math.PI, theta0: solidFrame(crank, d).theta };
d.solids = d.solids.map((s) => (s.id === slider.id ? { ...s, mass: 0.5, load: { point: jS, fx: 0, fy: -50, M: 0 } } : s));

const bd = toBackendDiagram(d);
writeFileSync("/tmp/slidercrank-backend.json", JSON.stringify(bd));
console.log("solides:", bd.bodies.length, "liaisons:", bd.joints.length, "moteur:", bd.motor?.body, "charges:", bd.external_loads?.length);
console.log("OK conversion écrite dans /tmp/slidercrank-backend.json");
