import { writeFileSync } from "fs";
import {
  Diagram,
  assignJointToSolid,
  emptyDiagram,
  ensureGround,
  linkNewSolid,
  solidFrame,
  toBackendDiagram,
  uid,
} from "../src/kinematics/model";

const d: Diagram = emptyDiagram();
const g = ensureGround(d);
d.solids = g.solids;
d.groundId = g.groundId;

const mk = (x: number, y: number) => {
  const id = uid();
  d.joints.push({ id, type: "revolute", x, y, axisDeg: 0, sideA: null, sideB: null });
  return id;
};

const A = mk(0, 0);
const D = mk(0.3, 0);
const B = mk(0.08, 0);
const C = mk(0.2264, 0.1642);

let out = assignJointToSolid(d, A, d.groundId!);
out = assignJointToSolid(out, D, out.groundId!);
out = linkNewSolid(out, A, B).diagram;
out = linkNewSolid(out, B, C).diagram;
out = linkNewSolid(out, C, D).diagram;

const crank = out.solids.find((s) => s.jointIds.includes(A) && s.jointIds.includes(B))!;
out.motor = { solid: crank.id, omega: 2 * Math.PI, theta0: solidFrame(crank, out).theta };

const bd = toBackendDiagram(out);
writeFileSync("/tmp/fourbar-backend.json", JSON.stringify(bd));
console.log("solides:", bd.bodies.length, "liaisons:", bd.joints.length, "moteur:", bd.motor?.body);
console.log("OK conversion écrite dans /tmp/fourbar-backend.json");
