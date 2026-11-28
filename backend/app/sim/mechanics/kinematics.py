from __future__ import annotations

import numpy as np


class Body:
    def __init__(self, name, points, x=0.0, y=0.0, theta=0.0, grounded=False, mass=1.0, inertia=0.0):
        self.name = name
        self.points = {k: np.asarray(v, dtype=float) for k, v in points.items()}
        self.q = np.array([x, y, theta], dtype=float)
        self.grounded = grounded
        self.mass = float(mass)
        self.inertia = float(inertia)


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
            elif kind in ("prismatic", "motor_linear"):
                pa, da = dpoint(j["a"], j["la"])
                pb, db = dpoint(j["b"], j["lb"])
                ax, ay = j["axis"]
                nrm = np.array([-ay, ax])
                rows.append((float(nrm @ (pb - pa)), [
                    (j["a"], np.array([-nrm[0], -nrm[1], -float(nrm @ da)])),
                    (j["b"], np.array([nrm[0], nrm[1], float(nrm @ db)]))]))
                rows.append((j["b"].q[2] - j["a"].q[2],
                             [(j["a"], np.array([0.0, 0.0, -1.0])), (j["b"], np.array([0.0, 0.0, 1.0]))]))
                if kind == "motor_linear":
                    s = float(ax * (pb[0] - pa[0]) + ay * (pb[1] - pa[1]))
                    rows.append((s - (j.get("s0", 0.0) + j.get("v", 0.0) * t), [
                        (j["a"], np.array([-ax, -ay, -float(np.array([ax, ay]) @ da)])),
                        (j["b"], np.array([ax, ay, float(np.array([ax, ay]) @ db)]))]))
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
        return np.linalg.lstsq(J, -phi_dot, rcond=None)[0]

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


def _advance(mech, q, t_from, t_to, depth=0):
    qn, ok = mech.solve_position_robust(q, t_to)
    if ok:
        return qn, True
    if depth >= 6:
        return q, False
    mid = 0.5 * (t_from + t_to)
    qm, okm = _advance(mech, q, t_from, mid, depth + 1)
    if not okm:
        return q, False
    return _advance(mech, qm, mid, t_to, depth + 1)


def simulate(mech, q0, t0, t1, steps):
    ts = np.linspace(t0, t1, steps + 1)
    qs = np.zeros((steps + 1, mech.nq()))
    qdots = np.zeros_like(qs)
    q = q0.copy()
    qs[0] = q
    for k in range(1, steps + 1):
        q, ok = _advance(mech, q, ts[k - 1], ts[k])
        if not ok:
            return ts[:k], qs[:k], qdots[:k], False
        qs[k] = q
        qdots[k] = mech.solve_velocity(q, ts[k])
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


JOINT_CONSTRAINTS = {"revolute": 2, "prismatic": 2, "fixed": 3, "motor_linear": 2}


def analyze_structure(data):
    bodies = data.get("bodies", [])
    joints = data.get("joints", [])
    n = len(bodies)
    anomalies = []
    liaisons = []
    total_c = 0
    n_drivers = (1 if data.get("motor") else 0) + sum(
        1 for j in joints if j.get("type") == "motor_linear")
    if n_drivers == 0:
        anomalies.append("Aucun moteur : ajoute un moteur rotatif (outil manivelle) ou linéaire (sur une glissière).")
    if n > 0 and not any(b.get("grounded") for b in bodies):
        anomalies.append("Aucun solide bâti : plante le BÂTI (outil Bâti) et attache-y au moins une liaison.")
    for j in joints:
        c = JOINT_CONSTRAINTS.get(j.get("type"), 0)
        total_c += c
        meme_solide = j.get("a") is not None and j.get("a") == j.get("b")
        if meme_solide:
            anomalies.append("Une liaison a ses 2 côtés sur le même solide : elle bloque ce solide.")
        liaisons.append({"type": j.get("type"), "a": j.get("a"), "b": j.get("b"),
                         "contraintes": c, "meme_solide": meme_solide})
    raw = 3 * (n - 1) - total_c if n > 0 else 0
    mobilite = max(raw, 0)
    if n_drivers > 0 and mobilite != n_drivers:
        anomalies.append(f"Mobilité m = {mobilite} mais {n_drivers} moteur(s) : il faut m = nombre de moteurs.")
    return {
        "n_solids": n,
        "n_liaisons": len(joints),
        "somme_contraintes": total_c,
        "mobilite": mobilite,
        "hyperstatisme": max(-raw, 0),
        "liaisons": liaisons,
        "anomalies": anomalies,
        "n_drivers": n_drivers,
        "grashof": grashof_warnings(data),
    }


def grashof_warnings(data, rel_tol=1e-3):
    bodies = {b["id"]: b for b in data.get("bodies", [])}
    adj = {}
    for j in data.get("joints", []):
        if j.get("type") != "revolute":
            continue
        a, b = j.get("a"), j.get("b")
        if not a or not b or a == b or a not in bodies or b not in bodies:
            continue
        adj.setdefault(a, []).append((b, j))
        adj.setdefault(b, []).append((a, j))

    def jworld(j, node):
        side = "a" if j.get("a") == node else "b"
        bd = bodies[node]
        label = j.get("la") if side == "a" else j.get("lb")
        if label not in bd.get("points", {}):
            return None
        px, py = bd["points"][label]
        th = bd.get("theta", 0.0)
        c, s = np.cos(th), np.sin(th)
        return np.array([bd.get("x", 0.0) + c * px - s * py, bd.get("y", 0.0) + s * px + c * py])

    warnings = []
    seen = set()
    for start in adj:
        for n1, j1 in adj.get(start, []):
            for n2, j2 in adj.get(n1, []):
                if n2 in (start, n1):
                    continue
                for n3, j3 in adj.get(n2, []):
                    if n3 in (start, n1, n2):
                        continue
                    for n4, j4 in adj.get(n3, []):
                        if n4 != start:
                            continue
                        key = tuple(sorted([start, n1, n2, n3]))
                        if key in seen:
                            continue
                        seen.add(key)
                        nodes = [start, n1, n2, n3]
                        edges = [j1, j2, j3, j4]
                        lens = []
                        okp = True
                        for i, node in enumerate(nodes):
                            p1 = jworld(edges[i], node)
                            p2 = jworld(edges[(i - 1) % 4], node)
                            if p1 is None or p2 is None:
                                okp = False
                                break
                            lens.append(float(np.linalg.norm(p1 - p2)))
                        if not okp or min(lens) < 1e-9:
                            continue
                        L = sorted(lens)
                        s, l, pq = L[0], L[3], L[1] + L[2]
                        if abs(s + l - pq) <= rel_tol * max(l, 1e-9):
                            warnings.append(
                                f"Boucle 4 barres {list(key)} : POINT DE CHANGEMENT (s+l = p+q = {pq:.3f} m) "
                                "— risque de blocage, modifie une longueur.")
                        elif s + l > pq:
                            warnings.append(
                                f"Boucle 4 barres {list(key)} : aucune barre ne tourne complètement "
                                f"(s+l = {s + l:.3f} > p+q = {pq:.3f} m) — le moteur va bloquer.")
    return warnings


def mechanism_from_dict(data):
    m = Mechanism()
    bodies = {}
    for bd in data.get("bodies", []):
        points = {k: tuple(v) for k, v in bd.get("points", {}).items()}
        b = m.add_body(Body(bd.get("name", bd["id"]), points,
                            x=bd.get("x", 0.0), y=bd.get("y", 0.0),
                            theta=bd.get("theta", 0.0), grounded=bd.get("grounded", False),
                            mass=bd.get("mass", 1.0), inertia=bd.get("inertia", 0.0)))
        bodies[bd["id"]] = b
    for j in data.get("joints", []):
        a = bodies[j["a"]]
        b = bodies[j["b"]]
        if j["type"] == "revolute":
            m.joints.append({"type": "revolute", "a": a, "la": j["la"], "b": b, "lb": j["lb"],
                             "node": j.get("node")})
        elif j["type"] in ("prismatic", "motor_linear"):
            ang = np.deg2rad(j.get("axisDeg", 0.0))
            jj = {"type": j["type"], "a": a, "la": j["la"], "b": b, "lb": j["lb"],
                  "axis": (np.cos(ang), np.sin(ang)), "node": j.get("node")}
            if j["type"] == "motor_linear":
                jj["s0"] = j.get("s0", 0.0)
                jj["v"] = j.get("v", 0.0)
            m.joints.append(jj)
        elif j["type"] == "fixed":
            m.joints.append({"type": "fixed", "a": a, "la": j["la"], "b": b, "lb": j["lb"],
                             "node": j.get("node")})
    motor = data.get("motor")
    if motor and motor.get("body") in bodies:
        m.motor(bodies[motor["body"]], motor.get("omega", 2 * np.pi), motor.get("theta0", 0.0))
    return m, bodies


def _load_Q(Q, free, loads):
    for ld in loads or []:
        b = ld.get("body")
        if b not in free:
            continue
        i = free.index(b)
        F = np.asarray(ld.get("force", [0.0, 0.0]), dtype=float)
        if ld.get("point") in b.points:
            p = point_world(b, ld["point"])
        else:
            p = b.q[:2].copy()
        r = p - b.q[:2]
        Q[3 * i] += F[0]
        Q[3 * i + 1] += F[1]
        Q[3 * i + 2] += r[0] * F[1] - r[1] * F[0] + float(ld.get("torque", 0.0))


def dynamics_step(mech, q, qdot, t, g=9.81, loads=None):
    phi, J = mech._build(q, t)
    free = mech.free_bodies()
    n = len(q)
    M = np.zeros((n, n))
    Q = np.zeros(n)
    for i, b in enumerate(free):
        M[3 * i, 3 * i] = b.mass
        M[3 * i + 1, 3 * i + 1] = b.mass
        M[3 * i + 2, 3 * i + 2] = b.inertia
        Q[3 * i + 1] = -b.mass * g
    _load_Q(Q, free, loads)
    h = 1e-6
    Jp, _ = mech._build(q + h * qdot, t + h)
    Jm, _ = mech._build(q - h * qdot, t - h)
    A = (Jp - Jm) / (2 * h)

    def phi_t(qq, tt):
        return (mech.constraints(qq, tt + h) - mech.constraints(qq, tt - h)) / (2 * h)

    B = (phi_t(q + h * qdot, t + h) - phi_t(q - h * qdot, t - h)) / (2 * h)
    rhs_acc = -(A @ qdot + B)
    m = len(phi)
    KKT = np.zeros((n + m, n + m))
    KKT[:n, :n] = M
    KKT[:n, n:] = -J.T
    KKT[n:, :n] = J
    rhs = np.concatenate([Q, rhs_acc])
    sol = np.linalg.solve(KKT, rhs)
    return sol[:n], sol[n:]


def statics_reactions(mech, q, t, g=9.81, loads=None):
    phi, J = mech._build(q, t)
    free = mech.free_bodies()
    n = len(q)
    Q = np.zeros(n)
    for i, b in enumerate(free):
        Q[3 * i + 1] = -b.mass * g
    _load_Q(Q, free, loads)
    return -np.linalg.solve(J.T, Q)


def extract_reactions(mech, lam):
    out = []
    row = 0
    for j in mech.joints:
        kind = j["type"]
        if kind == "revolute":
            out.append({"node": j.get("node"), "kind": kind,
                        "fx": float(lam[row]), "fy": float(lam[row + 1])})
            row += 2
        elif kind == "fixed":
            out.append({"node": j.get("node"), "kind": kind,
                        "fx": float(lam[row]), "fy": float(lam[row + 1]), "M": float(lam[row + 2])})
            row += 3
        elif kind == "prismatic":
            out.append({"node": j.get("node"), "kind": kind, "F": float(lam[row])})
            row += 2
        elif kind == "motor_linear":
            out.append({"node": j.get("node"), "kind": kind, "F": float(lam[row + 2])})
            row += 3
        elif kind == "motor":
            out.append({"node": j.get("node"), "kind": kind, "torque": float(lam[row])})
            row += 1
    return out


def run_mechanism(data, steps=240, mode="dynamics", g=9.81):
    structure = analyze_structure(data)
    motor = data.get("motor")
    linear = [j for j in data.get("joints", []) if j.get("type") == "motor_linear"]
    if not motor and not linear:
        return {"ok": False, "error": "Ajoute un moteur (rotatif sur un solide, ou linéaire sur une glissière).",
                "structure": structure}
    m, bodies = mechanism_from_dict(data)
    loads_raw = list(data.get("external_loads") or [])
    ext = data.get("external_force")
    if ext:
        loads_raw.append(ext)
    loads = []
    for ld in loads_raw:
        if ld.get("body") in bodies:
            loads.append({"body": bodies[ld["body"]], "point": ld.get("point", "J1"),
                          "force": ld.get("force", [0.0, 0.0]), "torque": ld.get("torque", 0.0)})
    omega = float(motor.get("omega", 2 * np.pi)) if motor else 0.0
    if linear:
        v = float(linear[0].get("v", 0.0))
        period = abs(2.0 / v) if v else 1.0
    else:
        period = 2 * np.pi / abs(omega) if omega else 1.0
    q0 = m.pack()
    if mode == "statics":
        q, ok0 = m.solve_position_robust(q0, 0.0)
        if not ok0:
            return {"ok": False, "mode": "statics", "structure": structure,
                    "error": "Assemblage impossible à t = 0 pour l'étude statique (vérifie m = 1, h = 0)."}
        lam = statics_reactions(m, q, 0.0, g=g, loads=loads)
        return {"ok": True, "mode": "statics", "t": [0.0], "period": 1.0, "omega": omega,
                "bodies": [], "max_residual": m.residual(q, 0.0), "structure": structure,
                "reactions": extract_reactions(m, lam), "gravity": g,
                "loads": [{"body": ld["body"].name, "point": ld["point"],
                           "force": list(ld["force"]), "torque": ld.get("torque", 0.0)} for ld in loads]}
    ts, qs, qdots, ok = simulate(m, q0, 0.0, period, int(steps))
    out_bodies = []
    for bid, b in bodies.items():
        series = []
        for q in qs:
            m.unpack(q)
            series.append(b.q.tolist())
        out_bodies.append({"id": bid, "name": b.name, "grounded": b.grounded, "qs": series,
                           "points": {k: v.tolist() for k, v in b.points.items()}})
    deg = 0.0
    if not ok and len(qs) and motor:
        m.unpack(qs[-1])
        mb = bodies.get(motor.get("body"))
        if mb is not None:
            deg = float(np.degrees(mb.q[2] - motor.get("theta0", 0.0)))
    if not ok:
        has_slide = any(j.get("type") in ("prismatic", "motor_linear") for j in data.get("joints", []))
        if has_slide:
            hint = ("Piste glissière (ex. bielle-manivelle) : la manivelle doit être PLUS COURTE que la bielle, "
                    "et l'axe de la glissière doit être bien orienté "
                    "(axe = direction entre les 2 points d'accroche de la glissière).")
        else:
            hint = ("Cause probable : la barre motrice ne peut pas faire un tour complet "
                    "(condition de Grashof : plus petite barre + plus grande < somme des deux autres). "
                    "Modifie une longueur, ou mets le moteur sur une autre barre.")
        return {
            "ok": False, "mode": "dynamics",
            "error": (f"Assemblage impossible (bloqué vers t = {float(ts[-1]) if len(ts) else 0.0:.3f} s, "
                      f"angle moteur ≈ {deg:.0f}°). {hint} "
                      "Autre piste : « Analyser (m, h) » doit donner m = nombre de moteurs, h = 0."),
            "structure": structure,
        }
    free = m.free_bodies()
    qdd_series = {id(b): [] for b in free}
    joint_series = {}
    for j in m.joints:
        if j.get("node"):
            joint_series[j["node"]] = []
    motor_torque = []
    motor_power = []
    lin_v = next((j.get("v", 0.0) for j in m.joints if j["type"] == "motor_linear"), 0.0)
    for k in range(len(ts)):
        qdd, lam = dynamics_step(m, qs[k], qdots[k], ts[k], g=g, loads=loads)
        for i, b in enumerate(free):
            qdd_series[id(b)].append(qdd[3 * i:3 * i + 3].tolist())
        for r in extract_reactions(m, lam):
            if r["node"] in joint_series:
                joint_series[r["node"]].append(r)
            if r["kind"] == "motor":
                motor_torque.append(r["torque"])
            if r["kind"] == "motor_linear":
                motor_power.append(r["F"] * lin_v)
    if motor_torque:
        motor_power = [tq * omega for tq in motor_torque]
    for ob in out_bodies:
        b = bodies[ob["id"]]
        ob["qdds"] = qdd_series.get(id(b), [])
        ob["mass"] = b.mass
        ob["inertia"] = b.inertia
    return {
        "ok": True,
        "mode": "dynamics",
        "t": ts.tolist(),
        "period": period,
        "omega": omega,
        "bodies": out_bodies,
        "joint_series": joint_series,
        "motor_torque": motor_torque,
        "motor_power": motor_power,
        "gravity": g,
        "max_residual": m.residual(qs[-1], ts[-1]) if len(qs) else None,
        "structure": structure,
    }
