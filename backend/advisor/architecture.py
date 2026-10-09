"""Clean up the architect's JSON before it is drawn and reported.

The model's output is treated as a proposal: ids are made unique, unknown
layers/kinds are corrected, flow steps and requirement mappings that point at
missing nodes are dropped, and a component whose technology appears nowhere in
the requirement or the reviewed specialist design is marked "recommended" so the
client can see it is our proposal, not their requirement. Every requirement in
the brief gets a traceability row; the ones no component delivers are listed
as unmapped.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import get_args

from .config import settings
from .schemas import Layer, NodeKind

LAYERS: list[str] = list(get_args(Layer))
KINDS: list[str] = list(get_args(NodeKind))

LAYER_TITLES = {
    "users": "Users & stakeholders",
    "application": "User / application layer",
    "api": "API & application services",
    "ai": "AI layer",
    "data": "Data layer",
    "integrations": "External integrations",
    "infrastructure": "Cloud infrastructure & networking",
    "security": "Security",
    "operations": "Monitoring & operations",
}
KIND_TITLES = {
    "actor": "User / stakeholder",
    "client_system": "Client system",
    "proposed": "Proposed solution component",
    "third_party": "Third-party system",
    "cloud_service": "Managed cloud service",
    "ai": "AI component",
    "data_store": "Data store",
}
# Layers drawn as horizontal bands; at most this many boxes per band keeps it high level.
MAX_PER_LAYER = 6


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_") or "node"


def _mentioned(tech: str, corpus: str) -> bool:
    """True if the technology (or each of its parts, e.g. 'Cloud Run + Cloud SQL') appears in the corpus."""
    parts = [p.strip().lower() for p in re.split(r"[+/,]| and ", tech) if p.strip()]
    return bool(parts) and all(p in corpus for p in parts)


def normalize(arch: dict, *, brief: dict, requirement_text: str = "", chosen: list[str] = ()) -> dict:
    """Return a cleaned copy of the architect output plus an 'unmapped' list."""
    corpus = " ".join([requirement_text, json.dumps(brief), *chosen]).lower()

    nodes: list[dict] = []
    id_map: dict[str, str] = {}
    per_layer: dict[str, int] = {}
    for raw in arch.get("nodes", []):
        layer = raw.get("layer") if raw.get("layer") in LAYERS else "api"
        if layer not in ("security", "integrations") and per_layer.get(layer, 0) >= MAX_PER_LAYER:
            continue
        per_layer[layer] = per_layer.get(layer, 0) + 1
        kind = raw.get("kind") if raw.get("kind") in KINDS else ("actor" if layer == "users" else "proposed")
        original = str(raw.get("id") or raw.get("label") or "node")
        nid = base = _slug(original)
        n = 2
        while nid in {x["id"] for x in nodes}:
            nid, n = f"{base}_{n}", n + 1
        id_map.setdefault(original, nid)
        id_map.setdefault(base, nid)
        tech = str(raw.get("technology") or "").strip()
        status = raw.get("status") if raw.get("status") in ("required", "recommended") else "recommended"
        if tech and status == "required" and not _mentioned(tech, corpus):
            status = "recommended"  # not asked for and not chosen by a specialist -> our proposal
        nodes.append({
            "id": nid,
            "label": str(raw.get("label") or original).strip(),
            "layer": layer,
            "kind": kind,
            "technology": tech,
            "status": status,
            "purpose": str(raw.get("purpose") or "").strip(),
        })

    def resolve(ref: str) -> str | None:
        ref = str(ref)
        return id_map.get(ref) or id_map.get(_slug(ref))

    flows = []
    for f in arch.get("flows", []):
        steps = []
        for s in f.get("steps", []):
            a, b = resolve(s.get("source", "")), resolve(s.get("target", ""))
            if a and b and a != b:
                steps.append({"source": a, "target": b, "label": str(s.get("label", "")).strip()})
        if steps:
            flows.append({"name": str(f.get("name") or "Flow"), "kind": "ai" if f.get("kind") == "ai" else "request",
                          "steps": steps})

    # Traceability: every brief requirement gets a row, matched by text.
    mapped: dict[str, list[str]] = {}
    for m in arch.get("requirement_mapping", []):
        comps = [c for c in (resolve(x) for x in m.get("components", [])) if c]
        key = " ".join(str(m.get("requirement", "")).split())
        if key:
            mapped[key.lower()] = list(dict.fromkeys(mapped.get(key.lower(), []) + comps))
    mapping = []
    for req in [*brief.get("functional_requirements", []), *brief.get("non_functional_requirements", [])]:
        key = " ".join(str(req).split())
        mapping.append({"requirement": key, "components": mapped.pop(key.lower(), [])})
    # Extra rows the architect added (e.g. requirements from the raw text) are kept too.
    mapping += [{"requirement": k, "components": v} for k, v in mapped.items()
                if not any(k == r["requirement"].lower() for r in mapping)]

    stack = [s for s in arch.get("technology_stack", []) if s.get("technology")]
    if not stack:
        stack = [{"layer": n["layer"], "technology": n["technology"], "purpose": n["purpose"], "status": n["status"]}
                 for n in nodes if n["technology"]]

    return {
        "title": str(arch.get("title") or brief.get("title") or "Solution architecture"),
        "overview": str(arch.get("overview") or ""),
        "cloud_provider": str(arch.get("cloud_provider") or "To be confirmed"),
        "nodes": nodes,
        "flows": flows,
        "requirement_mapping": mapping,
        "unmapped": [m["requirement"] for m in mapping if not m["components"]],
        "assumptions": list(arch.get("assumptions", [])),
        "technology_stack": stack,
        "security_considerations": list(arch.get("security_considerations", [])),
        "scalability_considerations": list(arch.get("scalability_considerations", [])),
        "future_enhancements": list(arch.get("future_enhancements", [])),
    }


# ------------------------------------------------------------------ storage
def path_for(run_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{8}", run_id):
        raise ValueError(f"Invalid run id: {run_id!r}")
    return Path(settings.output_dir) / f"architecture_{run_id}.json"


def save(run_id: str, arch: dict) -> str:
    path = path_for(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(arch, indent=2), encoding="utf-8")
    return str(path)


def load(run_id: str) -> dict | None:
    path = path_for(run_id)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
