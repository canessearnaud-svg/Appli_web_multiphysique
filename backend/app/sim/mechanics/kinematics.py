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

    def _build(self, q, t=0.0):
        self.unpack(q)
        free = self.free_bodies()
        col = {id(b): 3 * i for i, b in enumerate(free)}
        n = 3 * len(free)

        def dpoint(b, label):
            x, y, th = b.q
            px, py = b.points[label]
            c, s = np.cos(th), np.sin(th)
            p = np.array([x + c * px - s * py, y + s * px + c * py])
            dpdth = np.array([-s * px - c * py, c * px - s * py])
            return p, dpdth

        rows = []
        for j in self.joints:
            kind = j["type"]
            if kind in ("revolute", "fixed"):
                pa, da = dpoint(j["a"], j["la"])
                pb, db = dpoint(j["b"], j["lb"])
                r = pa - pb
                rows.append((r[0], [(j["a"], np.array([1.0, 0.0, da[0]])), (j["b"], np.array([-1.0, 0.0, -db[0]]))]))
                rows.append((r[1], [(j["a"], np.array([0.0, 1.0, da[1]])), (j["b"], np.array([0.0, -1.0, -db[1]]))]))
                if kind == "fixed":
                    rows.append((j["a"].q[2] - j["b"].q[2],
                                 [(j["a"], np.array([0.0, 0.0, 1.0])), (j["b"], np.array([0.0, 0.0, -1.0]))]))
            elif kind == "prismatic":
                pa, da = dpoint(j["a"], j["la"])
                pb, db = dpoint(j["b"], j["lb"])
                ax, ay = j["axis"]
                nrm = np.array([-ay, ax])
                rows.append((float(nrm @ (pb - pa)), [
                    (j["a"], np.array([-nrm[0], -nrm[1], -float(nrm @ da)])),
                    (j["b"], np.array([nrm[0], nrm[1], float(nrm @ db)]))]))
                rows.append((j["b"].q[2] - j["a"].q[2],
                             [(j["a"], np.array([0.0, 0.0, -1.0])), (j["b"], np.array([0.0, 0.0, 1.0]))]))
            elif kind == "motor":
                rows.append((j["body"].q[2] - (j["theta0"] + j["omega"] * t),
                             [(j["body"], np.array([0.0, 0.0, 1.0]))]))
        m = len(rows)
        phi = np.zeros(m)
        J = np.zeros((m, n))
        for i, (v, terms) in enumerate(rows):
            phi[i] = v
            for b, coef in terms:
                c0 = col.get(id(b))
                if c0 is not None:
                    J[i, c0:c0 + 3] = coef
        return phi, J

    def constraints(self, q, t=0.0):
        phi, _ = self._build(q, t)
        return phi

    def jacobian(self, q, t=0.0):
        _, J = self._build(q, t)
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

    def solve_position_robust(self, q0, t, tol=1e-10, max_iter=40):
        q = q0.copy()
        n = len(q)
        for mu in (1.0, 0.1, 1e-2, 1e-3, 1e-4):
            lam = 1e-3
            phi, J = self._build(q, t)
            if np.max(np.abs(phi)) < tol:
                return q, True
            cost = float(phi @ phi) + mu * float((q - q0) @ (q - q0))
            for _ in range(max_iter):
                A = J.T @ J + (lam + mu) * np.eye(n)
                g = J.T @ phi + mu * (q - q0)
                try:
                    dq = -np.linalg.solve(A, g)
                except np.linalg.LinAlgError:
                    lam *= 10
                    continue
                qn = q + dq
                phin, Jn = self._build(qn, t)
                costn = float(phin @ phin) + mu * float((qn - q0) @ (qn - q0))
                if costn < cost:
                    q, phi, J, cost = qn, phin, Jn, costn
                    lam = max(lam * 0.3, 1e-12)
                    if np.max(np.abs(phi)) < tol:
                        return q, True
                else:
                    lam *= 10
        q2, ok2 = self.solve_position(q, t, tol=tol)
        if ok2:
            return q2, True
        return q, self.residual(q, t) < 1e-8


def simulate(mech, q0, t0, t1, steps):
    ts = np.linspace(t0, t1, steps + 1)
    qs = np.zeros((steps + 1, mech.nq()))
    qdots = np.zeros_like(qs)
    q = q0.copy()
    for k, t in enumerate(ts):
        q, ok = mech.solve_position_robust(q, t)
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
    cd = D - C0
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


JOINT_CONSTRAINTS = {"revolute": 2, "prismatic": 2, "fixed": 3}


def analyze_structure(data):
    bodies = data.get("bodies", [])
    joints = data.get("joints", [])
    n = len(bodies)
    total_c = sum(JOINT_CONSTRAINTS.get(j.get("type"), 0) for j in joints)
    raw = 3 * (n - 1) - total_c if n > 0 else 0
    return {
        "n_solids": n,
        "n_liaisons": len(joints),
        "somme_contraintes": total_c,
        "mobilite": max(raw, 0),
        "hyperstatisme": max(-raw, 0),
        "liaisons": [
            {"type": j.get("type"), "a": j.get("a"), "b": j.get("b"),
             "contraintes": JOINT_CONSTRAINTS.get(j.get("type"), 0)}
            for j in joints
        ],
    }


def mechanism_from_dict(data):
    m = Mechanism()
    bodies = {}
    for bd in data.get("bodies", []):
        points = {k: tuple(v) for k, v in bd.get("points", {}).items()}
        b = m.add_body(Body(bd.get("name", bd["id"]), points,
                            x=bd.get("x", 0.0), y=bd.get("y", 0.0),
                            theta=bd.get("theta", 0.0), grounded=bd.get("grounded", False)))
        bodies[bd["id"]] = b
    for j in data.get("joints", []):
        a = bodies[j["a"]]
        b = bodies[j["b"]]
        if j["type"] == "revolute":
            m.revolute(a, j["la"], b, j["lb"])
        elif j["type"] == "prismatic":
            ang = np.deg2rad(j.get("axisDeg", 0.0))
            m.prismatic(a, j["la"], b, j["lb"], axis=(np.cos(ang), np.sin(ang)))
        elif j["type"] == "fixed":
            m.fixed(a, j["la"], b, j["lb"])
    motor = data.get("motor")
    if motor and motor.get("body") in bodies:
        m.motor(bodies[motor["body"]], motor.get("omega", 2 * np.pi), motor.get("theta0", 0.0))
    return m, bodies


def run_mechanism(data, steps=240):
    structure = analyze_structure(data)
    motor = data.get("motor")
    if not motor:
        return {"ok": False, "error": "Ajoute un moteur (outil manivelle) sur un solide.",
                "structure": structure}
    m, bodies = mechanism_from_dict(data)
    omega = float(motor.get("omega", 2 * np.pi))
    period = 2 * np.pi / abs(omega) if omega else 1.0
    q0 = m.pack()
    ts, qs, qdots, ok = simulate(m, q0, 0.0, period, int(steps))
    out_bodies = []
    for bid, b in bodies.items():
        series = []
        for q in qs:
            m.unpack(q)
            series.append(b.q.tolist())
        out_bodies.append({"id": bid, "name": b.name, "grounded": b.grounded, "qs": series,
                           "points": {k: v.tolist() for k, v in b.points.items()}})
    return {
        "ok": bool(ok),
        "error": None if ok else "Assemblage impossible depuis cette position initiale.",
        "t": ts.tolist(),
        "period": period,
        "omega": omega,
        "bodies": out_bodies,
        "max_residual": m.residual(qs[-1], ts[-1]) if len(qs) else None,
        "structure": structure,
    }
