export interface DigestCommand {
  name: string;
  summary: string;
  mutating: boolean;
  /** Argument names that matter most; not a full schema. */
  keyArgs?: string[];
}

export interface DigestGroup {
  name: string;
  blurb: string;
  commands: DigestCommand[];
}

export interface CapabilitiesDigest {
  contractVersionExpected: string;
  groups: DigestGroup[];
}

export const CAPABILITIES_DIGEST: CapabilitiesDigest = {
  contractVersionExpected: "0.10",
  groups: [
    {
      name: "system",
      blurb: "Handshake & capability discovery; always available, no load required.",
      commands: [
        { name: "system.ping", summary: "Liveness check", mutating: false },
        { name: "system.describe", summary: "App / game mode / data path", mutating: false },
        { name: "system.capabilities", summary: "Live command list + supports.* tree", mutating: false },
      ],
    },
    {
      name: "session",
      blurb: "Dirty state, GUI blockers, save, navigate.",
      commands: [
        { name: "session.get_dirty_state", summary: "Which files have unsaved changes", mutating: false },
        { name: "session.get_gui_snapshot", summary: "Modal blocker probe", mutating: false },
        { name: "session.save", summary: "Save listed files; watch pendingShutdown", mutating: true, keyArgs: ["files"] },
        { name: "session.navigate_to_record", summary: "Drive GUI JumpTo", mutating: false, keyArgs: ["file", "formId"] },
      ],
    },
    {
      name: "files",
      blurb: "List/get/create plugins; header & masters hygiene.",
      commands: [
        { name: "files.list", summary: "List loaded files", mutating: false },
        { name: "files.get", summary: "Per-file summary", mutating: false, keyArgs: ["file"] },
        { name: "files.create", summary: "New plugin", mutating: true, keyArgs: ["name", "extension", "flags"] },
        { name: "files.add_required_masters", summary: "Add masters to a plugin", mutating: true, keyArgs: ["file", "masters"] },
        { name: "files.get_header", summary: "Read plugin header", mutating: false, keyArgs: ["file"] },
        { name: "files.get_masters", summary: "Read master list", mutating: false, keyArgs: ["file"] },
        { name: "files.set_header_flags", summary: "ESM/ESL flag toggle", mutating: true, keyArgs: ["file", "flags"] },
        { name: "files.sort_masters", summary: "Sort masters", mutating: true, keyArgs: ["file"] },
        { name: "files.clean_masters", summary: "Drop unused masters", mutating: true, keyArgs: ["file"] },
      ],
    },
    {
      name: "records",
      blurb: "Read/search + mutating create/copy/delete/mark_deleted (15 commands).",
      commands: [
        { name: "records.list", summary: "List records in a file/group", mutating: false, keyArgs: ["file", "signature"] },
        { name: "records.apply_filter", summary: "Server-side filter", mutating: false },
        { name: "records.base_record", summary: "Master record of an override", mutating: false, keyArgs: ["file", "formId"] },
        { name: "records.find_by_form_id", summary: "Locate by FormID", mutating: false, keyArgs: ["file", "formId"] },
        { name: "records.find_by_editor_id", summary: "Locate by EditorID", mutating: false, keyArgs: ["editorId"] },
        { name: "records.get", summary: "Get a record + fields", mutating: false, keyArgs: ["file", "formId"] },
        { name: "records.master_or_self", summary: "Resolve to master or self", mutating: false, keyArgs: ["file", "formId"] },
        { name: "records.winning_override", summary: "Which file wins for this record", mutating: false, keyArgs: ["file", "formId"] },
        { name: "records.conflict_status", summary: "Conflict label for a record", mutating: false, keyArgs: ["file", "formId"] },
        { name: "records.references", summary: "Refs out from this record", mutating: false, keyArgs: ["file", "formId"] },
        { name: "records.referenced_by", summary: "Refs in to this record", mutating: false, keyArgs: ["file", "formId"] },
        { name: "records.create", summary: "Create record (signature support is dynamic)", mutating: true, keyArgs: ["file", "signature"] },
        { name: "records.copy_into", summary: "Copy as override into target plugin", mutating: true, keyArgs: ["sourceFile", "formId", "targetFile"] },
        { name: "records.delete", summary: "Delete record", mutating: true, keyArgs: ["file", "formId"] },
        { name: "records.mark_deleted", summary: "Mark deleted flag", mutating: true, keyArgs: ["file", "formId"] },
      ],
    },
    {
      name: "elements",
      blurb: "Read/write sub-record element tree (8 commands).",
      commands: [
        { name: "elements.get", summary: "Get element value/struct", mutating: false, keyArgs: ["file", "formId", "path"] },
        { name: "elements.children", summary: "List children at path", mutating: false, keyArgs: ["file", "formId", "path"] },
        { name: "elements.conflict_status", summary: "Element-level conflict", mutating: false, keyArgs: ["file", "formId", "path"] },
        { name: "elements.required_masters", summary: "Masters required by this element", mutating: false },
        { name: "elements.set_value", summary: "Set element value", mutating: true, keyArgs: ["file", "formId", "path", "value"] },
        { name: "elements.add_child", summary: "Add child element", mutating: true },
        { name: "elements.remove_child", summary: "Remove child element", mutating: true },
        { name: "elements.copy_child_to", summary: "Copy a child into another record", mutating: true },
      ],
    },
    {
      name: "jobs",
      blurb: "Async work surface; 10 kinds. dryRun defaults true on start.",
      commands: [
        { name: "jobs.start", summary: "Queue a job of one of the 10 kinds", mutating: true, keyArgs: ["kind", "dryRun"] },
        { name: "jobs.get", summary: "Poll job state", mutating: false, keyArgs: ["jobId"] },
        { name: "jobs.findings", summary: "Page findings from a job", mutating: false, keyArgs: ["jobId"] },
        { name: "jobs.cancel", summary: "Request cancel", mutating: false },
        { name: "jobs.discard", summary: "Drop a finished job from history", mutating: false },
      ],
    },
    {
      name: "scripts",
      blurb: "Pascal scripting; Agent/ namespace writable.",
      commands: [
        { name: "scripts.list", summary: "List stored scripts", mutating: false },
        { name: "scripts.read", summary: "Read a script body", mutating: false, keyArgs: ["id"] },
        { name: "scripts.write", summary: "Write to Agent/<id>.pas", mutating: true, keyArgs: ["id", "source"] },
        { name: "scripts.delete", summary: "Delete from Agent/ namespace", mutating: true, keyArgs: ["id"] },
        { name: "scripts.run", summary: "Run a script synchronously", mutating: true, keyArgs: ["id", "targets", "timeoutMs"] },
      ],
    },
  ],
};

export function allDigestCommands(): string[] {
  return CAPABILITIES_DIGEST.groups.flatMap((g) => g.commands.map((c) => c.name));
}
