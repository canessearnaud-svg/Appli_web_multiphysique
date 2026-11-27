from __future__ import annotations

import numpy as np


class Body:
    def __init__(self, name, points, x=0.0, y=0.0, theta=0.0, grounded=False):
        self.name = name
        self.points = {k: np.asarray(v, dtype=float) for k, v in points.items()}
        self.q = np.array([x, y, theta], dtype=float)
        self.grounded = grounded


def point_world(body, label, q=None):
    x, y, th = body.q if q is None else q
    px, py = body.points[label]
    c, s = np.cos(th), np.sin(th)
    return np.array([x + c * px - s * py, y + s * px + c * py])


class Mechanism:
    def __init__(self):
        self.bodies = []
        self.joints = []

    def add_body(self, body):
        self.bodies.append(body)
        return body

    def body(self, name):
        return next(b for b in self.bodies if b.name == name)

    def revolute(self, a, label_a, b, label_b):
        self.joints.append({"type": "revolute", "a": a, "la": label_a, "b": b, "lb": label_b})

    def prismatic(self, a, label_a, b, label_b, axis):
        self.joints.append({"type": "prismatic", "a": a, "la": label_a, "b": b, "lb": label_b,
                            "axis": np.asarray(axis, dtype=float)})

    def fixed(self, a, label_a, b, label_b):
        self.joints.append({"type": "fixed", "a": a, "la": label_a, "b": b, "lb": label_b})

    def motor(self, body, omega, theta0=0.0):
        self.joints.append({"type": "motor", "body": body, "omega": float(omega), "theta0": float(theta0)})

    def free_bodies(self):
        return [b for b in self.bodies if not b.grounded]

    def nq(self):
        return 3 * len(self.free_bodies())

    def pack(self):
        free = self.free_bodies()
        if not free:
            return np.zeros(0)
        return np.concatenate([b.q for b in free])

    def unpack(self, q):
        for i, b in enumerate(self.free_bodies()):
            b.q = q[3 * i:3 * i + 3].copy()

    def constraints(self, q, t=0.0):
        self.unpack(q)
        out = []
        for j in self.joints:
            kind = j["type"]
            if kind in ("revolute", "fixed"):
                pa = point_world(j["a"], j["la"])
                pb = point_world(j["b"], j["lb"])
                out.append(pa[0] - pb[0])
                out.append(pa[1] - pb[1])
                if kind == "fixed":
                    out.append(j["a"].q[2] - j["b"].q[2])
            elif kind == "prismatic":
                pa = point_world(j["a"], j["la"])
                pb = point_world(j["b"], j["lb"])
                ax, ay = j["axis"]
                out.append(-ay * (pb[0] - pa[0]) + ax * (pb[1] - pa[1]))
                out.append(j["b"].q[2] - j["a"].q[2])
            elif kind == "motor":
                out.append(j["body"].q[2] - (j["theta0"] + j["omega"] * t))
        return np.asarray(out, dtype=float)

    def jacobian(self, q, t=0.0, eps=1e-7):
        phi0 = self.constraints(q, t)
        n = len(q)
        J = np.zeros((len(phi0), n))
        for i in range(n):
            dq = np.zeros(n)
            dq[i] = eps
            J[:, i] = (self.constraints(q + dq, t) - self.constraints(q - dq, t)) / (2 * eps)
        return J

    def residual(self, q, t=0.0):
        return float(np.max(np.abs(self.constraints(q, t))))

    def solve_position(self, q0, t, tol=1e-10, max_iter=60):
        q = q0.copy()
        for _ in range(max_iter):
            phi = self.constraints(q, t)
            if np.max(np.abs(phi)) < tol:
                return q, True
            J = self.jacobian(q, t)
            try:
                dq = np.linalg.solve(J, -phi)
            except np.linalg.LinAlgError:
                return q, False
            q = q + dq
        return q, self.residual(q, t) < 1e-8

    def solve_velocity(self, q, t, h=1e-6):
        J = self.jacobian(q, t)
        phi_dot = (self.constraints(q, t + h) - self.constraints(q, t - h)) / (2 * h)
        return np.linalg.solve(J, -phi_dot)


def simulate(mech, q0, t0, t1, steps):
    ts = np.linspace(t0, t1, steps + 1)
    qs = np.zeros((steps + 1, mech.nq()))
    qdots = np.zeros_like(qs)
    q = q0.copy()
    for k, t in enumerate(ts):
        q, ok = mech.solve_position(q, t)
        if not ok:
            return ts[:k], qs[:k], qdots[:k], False
        qs[k] = q
        qdots[k] = mech.solve_velocity(q, t)
    return ts, qs, qdots, True


def circle_intersection(p1, r1, p2, r2, upper=True):
    p1 = np.asarray(p1, dtype=float)
    p2 = np.asarray(p2, dtype=float)
    d = float(np.linalg.norm(p2 - p1))
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h = np.sqrt(max(r1 * r1 - a * a, 0.0))
    base = p1 + a * (p2 - p1) / d
    perp = np.array([-(p2 - p1)[1], (p2 - p1)[0]]) / d
    return base + (h if upper else -h) * perp


def build_four_bar(crank=0.08, coupler=0.22, rocker=0.18, ground=0.30):
    m = Mechanism()
    g = m.add_body(Body("ground", {"A": (0.0, 0.0), "D": (ground, 0.0)}, grounded=True))
    B0 = np.array([crank, 0.0])
    D = np.array([ground, 0.0])
    C0 = circle_intersection(B0, coupler, D, rocker, upper=True)
    cr = m.add_body(Body("crank", {"A": (0.0, 0.0), "B": (crank, 0.0)}))
    cb = m.add_body(Body("coupler", {"B": (0.0, 0.0), "C": (C0[0] - B0[0], C0[1] - B0[1])},
                         x=B0[0], y=B0[1]))
    cd = C0 - D
    rk = m.add_body(Body("rocker", {"C": (0.0, 0.0), "D": (cd[0], cd[1])},
                         x=C0[0], y=C0[1]))
    m.revolute(g, "A", cr, "A")
    m.revolute(cr, "B", cb, "B")
    m.revolute(cb, "C", rk, "C")
    m.revolute(rk, "D", g, "D")
    return m


def run_four_bar(crank=0.08, coupler=0.22, rocker=0.18, ground=0.30, omega=2.0 * np.pi, steps=360):
    m = build_four_bar(crank, coupler, rocker, ground)
    m.motor(m.body("crank"), omega, theta0=0.0)
    q0 = m.pack()
    period = 2.0 * np.pi / omega
    ts, qs, qdots, ok = simulate(m, q0, 0.0, period, steps)
    path_c = []
    theta_crank = []
    for q in qs:
        m.unpack(q)
        path_c.append(point_world(m.body("coupler"), "C").tolist())
        theta_crank.append(float(m.body("crank").q[2]))
    return {
        "ok": bool(ok),
        "t": ts.tolist(),
        "theta_crank": theta_crank,
        "path_C": path_c,
        "max_residual": m.residual(qs[-1], ts[-1]) if len(qs) else None,
        "q0": qs[0].tolist() if len(qs) else [],
        "qT": qs[-1].tolist() if len(qs) else [],
    }
