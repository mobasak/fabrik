import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_compose_invariants():
    d = yaml.safe_load((ROOT / "compose.yaml").read_text())
    for name, svc in d["services"].items():
        assert "ports" not in svc, f"service {name} binds host ports"
        mem = (svc.get("deploy") or {}).get("resources", {}).get("limits", {}).get("memory")
        assert mem, f"service {name} missing deploy.resources.limits.memory"


def test_traefik_labels_kept():
    d = yaml.safe_load((ROOT / "compose.yaml").read_text())
    labels = d["services"]["api"].get("labels") or []
    assert any("traefik" in str(lbl) for lbl in labels)
