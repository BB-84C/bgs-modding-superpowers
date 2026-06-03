---
id: tooling-mo2.python-control-plane-is-real-plugin.v1
title: The MO2 control plane is the Python plugin, not a C++ DLL skeleton
domains: [debugging, engine]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: At v0.1 the usable MO2 control plane is tools/mo2-control-plane/live-bridge/mo2_agent_control.py plus its broker, while the old C++ skeleton is not a deployable MO2 plugin.
  confidence: verified-project-doc
queryKeys: [mo2_agent_control.py, Python plugin, C++ DLL skeleton, control plane]
severity: high
sources:
  - kind: project-skill
    ref: skills/setting-up-bgs-modding-environment/SKILL.md
    sectionPath: What the control plane actually is
  - kind: project-internal-doc
    ref: docs/internal/roadmap.md
    sectionPath: 2026-06-01 — Reshape closeout / Now known
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# The MO2 control plane is the Python plugin, not a C++ DLL skeleton

The deployable control plane is a Python MO2 plugin plus a PowerShell broker.
It publishes runtime bootstrap files and exposes the pipe the agent-side client uses.

The old C++ kernel material is design scaffolding, not something to build before setup can work.
Agents should stop if they find themselves trying to compile a `Mo2AgentControl.dll` for v0.1.

This record points setup debugging toward the actual integration file.
