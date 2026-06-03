---
id: xedit.add-required-masters-save-readback.v1
title: Adding required masters is a header mutation that needs save and readback
domains: [xedit, plugin-format]
appliesTo:
  games: [SkyrimLE, SkyrimSE, SkyrimAE, SkyrimVR, Fallout4, Fallout4VR, Fallout3, FalloutNV, Starfield]
canonical:
  answer: files.add_required_masters mutates the target plugin's master list, so the workflow is not complete until the file is saved, the daemon restarts if needed, and files.get_masters confirms the intended order.
  confidence: verified-project-doc
queryKeys: [files.add_required_masters, add_master, master rebuild, files.get_masters, MAST DATA]
severity: high
sources:
  - kind: project-skill
    ref: skills/xedit-automation/xedit-knowledgebase.md
    sectionPath: files.*
  - kind: wiki
    ref: UESP Skyrim Mod File Format / TES4
    url: https://en.uesp.net/wiki/Tes5Mod:Mod_File_Format/TES4
    sectionPath: MAST / DATA
lastReviewed: "2026-06-02"
schemaVersion: 1
---

# Adding required masters is a header mutation that needs save and readback

Adding a required master changes the plugin header's master list, not just an in-memory xEdit view.
The master order is load-order-sensitive because FormID master indices resolve against that list.

Use `files.add_required_masters` for the mutation, then `session.save` with the normal pending-shutdown caution.
After restart when required, call `files.get_masters` and confirm the expected master filenames and order.

Do not claim a copied record is durable until its required masters survive this readback.
