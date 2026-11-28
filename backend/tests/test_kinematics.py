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
               "b": ids[j["b"].name], "lb": j["lb"], "axisDeg": 0, "node": f"j{i}"}
              for i, j in enumerate(m.joints) if j["type"] != "motor"]
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


def test_linear_motor_drives_slider():
    data = {
        "bodies": [
            {"id": "g", "grounded": True, "x": 0, "y": 0, "theta": 0, "points": {"S": [0, 0]}},
            {"id": "s", "x": 0.1, "y": 0, "theta": 0, "points": {"C": [0, 0]}, "mass": 2.0, "inertia": 0.0},
        ],
        "joints": [{"type": "motor_linear", "a": "g", "la": "S", "b": "s", "lb": "C",
                    "axisDeg": 0, "s0": 0.1, "v": 0.5, "node": "j1"}],
    }
    s = kin.analyze_structure(data)
    assert s["mobilite"] == 1 and s["n_drivers"] == 1 and not s["anomalies"]
    res = kin.run_mechanism(data, steps=100)
    assert res["ok"] is True
    slider_x = [q[0] for q in res["bodies"][1]["qs"]]
    assert abs(slider_x[-1] - 2.1) < 1e-6
    assert len(res["motor_power"]) == len(res["t"])
    assert len(res["joint_series"]["j1"]) == len(res["t"])


def test_statics_lever():
    data = {
        "bodies": [
            {"id": "g", "grounded": True, "x": 0, "y": 0, "theta": 0, "points": {"O": [0, 0]}},
            {"id": "bar", "x": 0, "y": 0, "theta": 0, "points": {"O": [0, 0], "A": [0.3, 0]}, "mass": 0.0, "inertia": 0.0},
        ],
        "joints": [{"type": "revolute", "a": "g", "la": "O", "b": "bar", "lb": "O", "node": "j1"}],
        "motor": {"body": "bar", "omega": 2 * np.pi, "theta0": 0.0},
        "external_force": {"body": "bar", "point": "A", "force": [0.0, -100.0]},
    }
    res = kin.run_mechanism(data, mode="statics")
    assert res["ok"] is True
    j1 = [r for r in res["reactions"] if r["kind"] == "revolute"][0]
    mot = [r for r in res["reactions"] if r["kind"] == "motor"][0]
    assert abs(abs(j1["fy"]) - 100.0) < 1e-6
    assert abs(abs(mot["torque"]) - 30.0) < 1e-6


def test_dynamics_four_bar_outputs():
    m = kin.build_four_bar()
    data = _dict_from_mech(m)
    for b in data["bodies"]:
        b["mass"] = 1.5
        b["inertia"] = 0.02
    res = kin.run_mechanism(data, steps=120)
    assert res["ok"] is True
    assert res["mode"] == "dynamics"
    assert len(res["motor_torque"]) == len(res["t"])
    assert len(res["motor_power"]) == len(res["t"])
    assert all(np.isfinite(res["motor_power"]))
    assert all(len(ob.get("qdds", [])) == len(res["t"]) for ob in res["bodies"] if not ob["grounded"])
    assert len(res["joint_series"]) >= 4


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


def _slider_crank_dict(crank=0.05, rod=0.15):
    return {
        "bodies": [
            {"id": "g", "grounded": True, "x": 0, "y": 0, "theta": 0, "points": {"O": [0, 0], "S": [0, 0]}},
            {"id": "c", "x": 0, "y": 0, "theta": 0, "points": {"O": [0, 0], "B": [crank, 0]}, "mass": 1.0, "inertia": 0.01},
            {"id": "r", "x": crank, "y": 0, "theta": 0, "points": {"B": [0, 0], "C": [rod, 0]}, "mass": 1.0, "inertia": 0.01},
            {"id": "s", "x": crank + rod, "y": 0, "theta": 0, "points": {"C": [0, 0]}, "mass": 0.5, "inertia": 0.0},
        ],
        "joints": [
            {"type": "revolute", "a": "g", "la": "O", "b": "c", "lb": "O", "node": "j1"},
            {"type": "revolute", "a": "c", "la": "B", "b": "r", "lb": "B", "node": "j2"},
            {"type": "revolute", "a": "r", "la": "C", "b": "s", "lb": "C", "node": "j3"},
            {"type": "prismatic", "a": "g", "la": "S", "b": "s", "lb": "C", "axisDeg": 0, "node": "j4"},
        ],
        "motor": {"body": "c", "omega": 2 * np.pi, "theta0": 0.0},
    }


def test_slider_crank_run_ok():
    data = _slider_crank_dict()
    s = kin.analyze_structure(data)
    assert s["mobilite"] == 1 and s["n_drivers"] == 1 and not s["anomalies"]
    assert s["grashof"] == []
    res = kin.run_mechanism(data, steps=180)
    assert res["ok"] is True, res.get("error")
    assert res["max_residual"] < 1e-8
    slider = [b for b in res["bodies"] if b["id"] == "s"][0]
    xs = [q[0] for q in slider["qs"]]
    assert max(xs) - min(xs) > 0.05
    assert all(abs(q[1]) < 1e-8 for q in slider["qs"])


def test_slider_crank_blocked_gives_manivelle_hint():
    res = kin.run_mechanism(_slider_crank_dict(crank=0.30, rod=0.15), steps=30)
    assert res["ok"] is False
    assert "bloqué vers t" in res["error"]
    assert "manivelle" in res["error"]


def test_statics_external_loads_list():
    data = {
        "bodies": [
            {"id": "g", "grounded": True, "x": 0, "y": 0, "theta": 0, "points": {"O": [0, 0]}},
            {"id": "bar", "x": 0, "y": 0, "theta": 0, "points": {"O": [0, 0], "A": [0.3, 0]}, "mass": 0.0, "inertia": 0.0},
        ],
        "joints": [{"type": "revolute", "a": "g", "la": "O", "b": "bar", "lb": "O", "node": "j1"}],
        "motor": {"body": "bar", "omega": 2 * np.pi, "theta0": 0.0},
        "external_loads": [
            {"body": "bar", "point": "A", "force": [0.0, -100.0], "torque": 0.0},
            {"body": "bar", "point": "O", "force": [10.0, 0.0], "torque": 0.0},
        ],
    }
    res = kin.run_mechanism(data, mode="statics")
    assert res["ok"] is True
    assert len(res["loads"]) == 2
    j1 = [r for r in res["reactions"] if r["kind"] == "revolute"][0]
    mot = [r for r in res["reactions"] if r["kind"] == "motor"][0]
    assert abs(abs(j1["fx"]) - 10.0) < 1e-6
    assert abs(abs(j1["fy"]) - 100.0) < 1e-6
    assert abs(abs(mot["torque"]) - 30.0) < 1e-6


def test_statics_loads_also_in_dynamics():
    data = _slider_crank_dict()
    data["external_loads"] = [{"body": "s", "point": "C", "force": [0.0, -50.0], "torque": 0.0}]
    res = kin.run_mechanism(data, steps=60)
    assert res["ok"] is True, res.get("error")
    assert all(np.isfinite(res["motor_torque"]))


def test_analyze_warns_without_ground():
    data = {
        "bodies": [{"id": "a"}, {"id": "b"}],
        "joints": [{"type": "revolute", "a": "a", "b": "b"}],
        "motor": {"body": "a", "omega": 1.0, "theta0": 0.0},
    }
    s = kin.analyze_structure(data)
    assert any("bâti" in a.lower() for a in s["anomalies"])
