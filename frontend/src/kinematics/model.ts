export type Vec = [number, number];

export type Body = {
  id: string;
  name: string;
  grounded: boolean;
  x: number;
  y: number;
  theta: number;
  w: number;
  h: number;
  points: Record<string, Vec>;
};

export type JointType = "revolute" | "prismatic" | "fixed";

export type Joint = {
  id: string;
  type: JointType;
  a: string;
  la: string;
  b: string;
  lb: string;
  axisDeg: number;
};

export type Motor = { body: string; omega: number; theta0: number };

export type Diagram = { bodies: Body[]; joints: Joint[]; motor: Motor | null };

export const uid = () => Math.random().toString(36).slice(2, 9);

export const emptyDiagram = (): Diagram => ({ bodies: [], joints: [], motor: null });

export const toLocal = (b: Body, wx: number, wy: number): Vec => {
  const dx = wx - b.x;
  const dy = wy - b.y;
  const c = Math.cos(-b.theta);
  const s = Math.sin(-b.theta);
  return [dx * c - dy * s, dx * s + dy * c];
};

export const toWorldPoint = (x: number, y: number, th: number, l: Vec): Vec => {
  const c = Math.cos(th);
  const s = Math.sin(th);
  return [x + c * l[0] - s * l[1], y + s * l[0] + c * l[1]];
};

export const autoPointName = (b: Body) => `P${Object.keys(b.points).length + 1}`;
