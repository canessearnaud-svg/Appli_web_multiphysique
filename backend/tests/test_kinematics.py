import numpy as np

from app.sim.mechanics import kinematics as kin


def test_four_bar_full_revolution_and_closure():
    res = kin.run_four_bar(steps=360)
    assert res["ok"] is True
    assert len(res["t"]) == 361
    assert res["max_residual"] < 1e-8
    assert abs(res["theta_crank"][-1] - 2 * np.pi) < 1e-9
    assert np.allclose(res["path_C"][0], res["path_C"][-1], atol=1e-6)


def test_four_bar_coupler_point_moves():
    res = kin.run_four_bar(steps=720, omega=np.pi)
    xs = [p[0] for p in res["path_C"]]
    ys = [p[1] for p in res["path_C"]]
    assert max(xs) - min(xs) > 0.05
    assert max(ys) - min(ys) > 0.05


def test_newton_converges_from_perturbation():
    m = kin.build_four_bar()
    m.motor(m.body("crank"), 2 * np.pi, 0.0)
    q0 = m.pack()
    q, ok = m.solve_position(q0 + 0.01, 0.0)
    assert ok
    assert m.residual(q, 0.0) < 1e-10


def test_slider_crank_prismatic():
    m = kin.Mechanism()
    g = m.add_body(kin.Body("ground", {"A": (0.0, 0.0), "S": (0.0, 0.0)}, grounded=True))
    crank = 0.05
    rod = 0.15
    cr = m.add_body(kin.Body("crank", {"A": (0.0, 0.0), "B": (crank, 0.0)}))
    sl = m.add_body(kin.Body("slider", {"C": (0.0, 0.0)}, x=crank + rod, y=0.0))
    rd = m.add_body(kin.Body("rod", {"B": (0.0, 0.0), "C": (rod, 0.0)}, x=crank, y=0.0))
    m.revolute(g, "A", cr, "A")
    m.revolute(cr, "B", rd, "B")
    m.revolute(rd, "C", sl, "C")
    m.prismatic(g, "S", sl, "C", axis=(1.0, 0.0))
    m.motor(cr, 2 * np.pi, 0.0)
    q0 = m.pack()
    ts, qs, qdots, ok = kin.simulate(m, q0, 0.0, 1.0, 200)
    assert ok
    slider = m.body("slider")
    xs = []
    for q in qs:
        m.unpack(q)
        assert abs(slider.q[1]) < 1e-8
        assert abs(slider.q[2]) < 1e-8
        xs.append(slider.q[0])
    assert max(xs) - min(xs) > 0.05


def test_analyze_four_bar():
    data = {
        "bodies": [{"id": "g", "grounded": True}, {"id": "c"}, {"id": "b"}, {"id": "r"}],
        "joints": [
            {"type": "revolute", "a": "g", "b": "c"},
            {"type": "revolute", "a": "c", "b": "b"},
            {"type": "revolute", "a": "b", "b": "r"},
            {"type": "revolute", "a": "r", "b": "g"},
        ],
    }
    s = kin.analyze_structure(data)
    assert s["n_solids"] == 4
    assert s["n_liaisons"] == 4
    assert s["somme_contraintes"] == 8
    assert s["mobilite"] == 1
    assert s["hyperstatisme"] == 0


def test_analyze_hyperstatic():
    data = {
        "bodies": [{"id": "g", "grounded": True}, {"id": "a"}, {"id": "b"}],
        "joints": [
            {"type": "fixed", "a": "g", "b": "a"},
            {"type": "fixed", "a": "g", "b": "b"},
            {"type": "fixed", "a": "a", "b": "b"},
        ],
    }
    s = kin.analyze_structure(data)
    assert s["mobilite"] == 0
    assert s["hyperstatisme"] == 3


def _dict_from_mech(m, motor_body="crank"):
    bodies = []
    ids = {}
    for i, b in enumerate(m.bodies):
        bid = f"b{i}"
        ids[b.name] = bid
        bodies.append({"id": bid, "name": b.name, "grounded": b.grounded,
                       "x": float(b.q[0]), "y": float(b.q[1]), "theta": float(b.q[2]),
                       "points": {k: v.tolist() for k, v in b.points.items()}})
    joints = [{"type": j["type"], "a": ids[j["a"].name], "la": j["la"],
               "b": ids[j["b"].name], "lb": j["lb"], "axisDeg": 0}
              for j in m.joints if j["type"] != "motor"]
    return {"bodies": bodies, "joints": joints,
            "motor": {"body": ids[motor_body], "omega": 2 * np.pi, "theta0": 0.0}}


def test_run_mechanism_roundtrip():
    m = kin.build_four_bar()
    res = kin.run_mechanism(_dict_from_mech(m), steps=180)
    assert res["ok"] is True
    assert res["structure"]["mobilite"] == 1
    assert len(res["bodies"]) == 4
    assert len(res["bodies"][1]["qs"]) == 181
    assert res["max_residual"] < 1e-8


def test_run_mechanism_sans_moteur():
    m = kin.build_four_bar()
    data = _dict_from_mech(m)
    data["motor"] = None
    res = kin.run_mechanism(data)
    assert res["ok"] is False
    assert "moteur" in res["error"].lower()


def test_run_mechanism_assembles_near_drawn_pose():
    m = kin.build_four_bar()
    data = _dict_from_mech(m)
    data["bodies"][3]["x"] += 0.01
    data["bodies"][3]["y"] += 0.005
    res = kin.run_mechanism(data, steps=60)
    assert res["ok"] is True
    assert res["max_residual"] < 1e-8
    rocker = res["bodies"][3]["qs"][0]
    assert abs(rocker[0] - data["bodies"][3]["x"]) < 0.02
    assert abs(rocker[1] - data["bodies"][3]["y"]) < 0.02


def _four_bar_dict(a, b, c, d):
    return {
        "bodies": [
            {"id": "g", "grounded": True, "x": 0, "y": 0, "theta": 0, "points": {"A": [0, 0], "D": [d, 0]}},
            {"id": "c", "x": 0, "y": 0, "theta": 0, "points": {"A": [0, 0], "B": [a, 0]}},
            {"id": "b", "x": a, "y": 0, "theta": 0, "points": {"B": [0, 0], "C": [b, 0]}},
            {"id": "r", "x": a + b, "y": 0, "theta": 0, "points": {"C": [0, 0], "D": [d - a - b, 0]}},
        ],
        "joints": [
            {"type": "revolute", "a": "g", "la": "A", "b": "c", "lb": "A"},
            {"type": "revolute", "a": "c", "la": "B", "b": "b", "lb": "B"},
            {"type": "revolute", "a": "b", "la": "C", "b": "r", "lb": "C"},
            {"type": "revolute", "a": "r", "la": "D", "b": "g", "lb": "D"},
        ],
    }


def test_grashof_change_point_detected():
    s = kin.analyze_structure(_four_bar_dict(0.4, 0.4, 0.4, 0.4))
    assert any("POINT DE CHANGEMENT" in w for w in s["grashof"])


def test_grashof_double_rocker_detected():
    s = kin.analyze_structure(_four_bar_dict(0.2, 0.2, 0.2, 0.5))
    assert any("aucune barre" in w for w in s["grashof"])


def test_grashof_ok_no_warning():
    s = kin.analyze_structure(_four_bar_dict(0.08, 0.22, 0.18, 0.30))
    assert s["grashof"] == []


def test_analyze_detects_degenerate_joint():
    data = {
        "bodies": [{"id": "g", "grounded": True}, {"id": "a"}],
        "joints": [{"type": "revolute", "a": "a", "b": "a"}],
    }
    s = kin.analyze_structure(data)
    assert s["anomalies"]
    assert s["liaisons"][0]["meme_solide"] is True


def test_run_mechanism_impossible_geometry():
    m = kin.build_four_bar()
    data = _dict_from_mech(m)
    for b in data["bodies"]:
        if b["name"] == "coupler":
            b["points"]["C"] = [0.02, 0.0]
    res = kin.run_mechanism(data, steps=10)
    assert res["ok"] is False
    assert "bloqué vers t" in res["error"]
    assert "Grashof" in res["error"]
