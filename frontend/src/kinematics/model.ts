export type Vec = [number, number];
export type JointType = "revolute" | "prismatic" | "fixed" | "motor_linear";

export type JointNode = {
  id: string;
  type: JointType;
  x: number;
  y: number;
  axisDeg: number;
  sideA: string | null;
  sideB: string | null;
  v?: number;
  s0?: number;
};

export type Solid = {
  id: string;
  name: string;
  grounded: boolean;
  jointIds: string[];
  mass?: number;
  inertia?: number;
};

export type Motor = { solid: string; omega: number; theta0: number };

export type Diagram = {
  solids: Solid[];
  joints: JointNode[];
  motor: Motor | null;
  groundId: string | null;
};

export const uid = () => Math.random().toString(36).slice(2, 9);

export const emptyDiagram = (): Diagram => ({ solids: [], joints: [], motor: null, groundId: null });

export const toWorldPoint = (x: number, y: number, th: number, l: Vec): Vec => {
  const c = Math.cos(th);
  const s = Math.sin(th);
  return [x + c * l[0] - s * l[1], y + s * l[0] + c * l[1]];
};

export const solidFrame = (s: Solid, d: Diagram): { x: number; y: number; theta: number } => {
  const js = s.jointIds.map((id) => d.joints.find((j) => j.id === id)).filter((j): j is JointNode => !!j);
  if (js.length === 0) return { x: 0, y: 0, theta: 0 };
  const theta = js.length > 1 ? Math.atan2(js[1].y - js[0].y, js[1].x - js[0].x) : 0;
  return { x: js[0].x, y: js[0].y, theta };
};

export const ensureGround = (d: Diagram): Diagram => {
  if (d.groundId) return d;
  const id = uid();
  return { ...d, groundId: id, solids: [...d.solids, { id, name: "BÂTI", grounded: true, jointIds: [] }] };
};

export const assignJointToSolid = (d: Diagram, jointId: string, solidId: string): Diagram => {
  const j = d.joints.find((x) => x.id === jointId);
  if (!j || !d.solids.find((x) => x.id === solidId)) return d;
  if (j.sideA === solidId || j.sideB === solidId) return d;
  if (j.sideA !== null && j.sideB !== null) return d;
  const nj: JointNode = j.sideA === null ? { ...j, sideA: solidId } : { ...j, sideB: solidId };
  return {
    ...d,
    joints: d.joints.map((x) => (x.id === jointId ? nj : x)),
    solids: d.solids.map((s) => (s.id === solidId ? { ...s, jointIds: [...s.jointIds, jointId] } : s)),
  };
};

export const linkNewSolid = (
  d: Diagram,
  aId: string,
  bId: string
): { diagram: Diagram; error: string | null } => {
  const a = d.joints.find((x) => x.id === aId);
  const b = d.joints.find((x) => x.id === bId);
  if (!a || !b || aId === bId) return { diagram: d, error: "Il faut deux liaisons différentes." };
  if ((a.sideA !== null && a.sideB !== null) || (b.sideA !== null && b.sideB !== null))
    return { diagram: d, error: "Cette liaison a déjà ses 2 solides — utilise « ajouter au solide »." };
  const sid = uid();
  const solid: Solid = { id: sid, name: "Solide-" + sid.slice(0, 3), grounded: false, jointIds: [aId, bId] };
  let out: Diagram = { ...d, solids: [...d.solids, solid] };
  out = assignJointToSolid(out, aId, sid);
  out = assignJointToSolid(out, bId, sid);
  return { diagram: out, error: null };
};

export const removeJoint = (d: Diagram, jointId: string): Diagram => ({
  ...d,
  joints: d.joints.filter((x) => x.id !== jointId),
  solids: d.solids.map((s) => ({ ...s, jointIds: s.jointIds.filter((id) => id !== jointId) })),
});

export const removeSolid = (d: Diagram, solidId: string): Diagram => {
  const s = d.solids.find((x) => x.id === solidId);
  if (!s) return d;
  let out: Diagram = {
    ...d,
    solids: d.solids.filter((x) => x.id !== solidId),
    groundId: d.groundId === solidId ? null : d.groundId,
    motor: d.motor?.solid === solidId ? null : d.motor,
  };
  for (const jid of s.jointIds) {
    out = {
      ...out,
      joints: out.joints.map((j) =>
        j.id === jid
          ? { ...j, sideA: j.sideA === solidId ? null : j.sideA, sideB: j.sideB === solidId ? null : j.sideB }
          : j
      ),
    };
  }
  return out;
};

export const toBackendDiagram = (d: Diagram) => {
  const pointOf = new Map<string, string>();
  const bodies = d.solids
    .filter((s) => s.jointIds.length > 0)
    .map((s) => {
      const f = solidFrame(s, d);
      const js = s.jointIds.map((id) => d.joints.find((j) => j.id === id)).filter((j): j is JointNode => !!j);
      const points: Record<string, Vec> = {};
      js.forEach((j, i) => {
        pointOf.set(s.id + ":" + j.id, "J" + (i + 1));
        const c = Math.cos(-f.theta);
        const si = Math.sin(-f.theta);
        const dx = j.x - f.x;
        const dy = j.y - f.y;
        points["J" + (i + 1)] = [dx * c - dy * si, dx * si + dy * c];
      });
      return { id: s.id, name: s.name, grounded: s.grounded, x: f.x, y: f.y, theta: f.theta,
               mass: s.mass ?? 1.0, inertia: s.inertia ?? 0.0, points };
    });
  const joints = d.joints
    .filter((j) => j.sideA && j.sideB)
    .map((j) => ({
      node: j.id,
      type: j.type,
      a: j.sideA!,
      la: pointOf.get(j.sideA + ":" + j.id)!,
      b: j.sideB!,
      lb: pointOf.get(j.sideB + ":" + j.id)!,
      axisDeg: j.axisDeg,
      v: j.v ?? 0.05,
      s0: j.s0 ?? 0,
    }));
  const motor = d.motor ? { body: d.motor.solid, omega: d.motor.omega, theta0: d.motor.theta0 } : null;
  return { bodies, joints, motor };
};
