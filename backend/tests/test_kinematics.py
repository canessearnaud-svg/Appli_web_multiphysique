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
