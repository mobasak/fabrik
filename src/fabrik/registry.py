"""Project Registry - Track all projects in /opt folder."""

import fnmatch
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml


@dataclass
class Project:
    """Project metadata."""

    name: str
    path: str
    type: str = "service"  # service, library, tool
    status: str = "development"  # deployed, ready, development
    coolify_uuid: str | None = None
    coolify_name: str | None = None
    domain: str | None = None
    port: int | None = None

    def to_dict(self) -> dict:
        d = {"path": self.path, "type": self.type, "status": self.status}
        if self.coolify_uuid:
            d["coolify_uuid"] = self.coolify_uuid
        if self.coolify_name:
            d["coolify_name"] = self.coolify_name
        if self.domain:
            d["domain"] = self.domain
        if self.port:
            d["port"] = self.port
        return d

    @classmethod
    def from_dict(cls, name: str, data: dict) -> "Project":
        return cls(
            name=name,
            path=data.get("path", f"/opt/{name}"),
            type=data.get("type", "service"),
            status=data.get("status", "development"),
            coolify_uuid=data.get("coolify_uuid"),
            coolify_name=data.get("coolify_name"),
            domain=data.get("domain"),
            port=data.get("port"),
        )


DEFAULT_EXCLUDES = ["_*", ".*", "google", "apps", "__pycache__", "venv"]


class ProjectRegistry:
    """Manages project registry YAML file."""

    def __init__(self, path: Path = None):
        self.path = path or Path("/opt/fabrik/data/projects.yaml")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.projects: dict[str, Project] = {}
        self.excludes = DEFAULT_EXCLUDES.copy()
        self.last_scan: str | None = None
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        data = yaml.safe_load(self.path.read_text()) or {}
        self.excludes = data.get("exclude", DEFAULT_EXCLUDES)
        self.last_scan = data.get("last_scan")
        for name, d in data.get("projects", {}).items():
            self.projects[name] = Project.from_dict(name, d)

    def save(self):
        data = {
            "version": 1,
            "last_scan": self.last_scan,
            "exclude": self.excludes,
            "projects": {n: p.to_dict() for n, p in sorted(self.projects.items())},
        }
        self.path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def _excluded(self, name: str) -> bool:
        return any(fnmatch.fnmatch(name, p) for p in self.excludes)

    def scan(self, base: Path = Path("/opt")) -> list[str]:
        """Scan for projects. Returns newly discovered names."""
        new = []
        for item in sorted(base.iterdir()):
            if not item.is_dir() or self._excluded(item.name):
                continue
            name = item.name
            has_compose = any((item / f).exists() for f in ["compose.yaml", "docker-compose.yaml"])
            has_dockerfile = (item / "Dockerfile").exists()

            if name not in self.projects:
                ptype = "service" if has_compose else "tool"
                pstatus = "ready" if (has_compose and has_dockerfile) else "development"
                self.projects[name] = Project(name, str(item), ptype, pstatus)
                new.append(name)
            else:
                p = self.projects[name]
                if has_compose and has_dockerfile and p.status == "development":
                    p.status = "ready"
        self.last_scan = datetime.now().isoformat()
        return new

    def list(self, status: str = None) -> list[Project]:
        """List projects, optionally filtered by status."""
        projs = list(self.projects.values())
        if status:
            projs = [p for p in projs if p.status == status]
        return sorted(projs, key=lambda p: p.name)

    def get(self, name: str) -> Project | None:
        return self.projects.get(name)

    def update(self, name: str, **kwargs):
        if name in self.projects:
            for k, v in kwargs.items():
                if hasattr(self.projects[name], k):
                    setattr(self.projects[name], k, v)
