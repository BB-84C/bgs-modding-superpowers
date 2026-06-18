import { z } from "zod";
import { ok as okEnv, refuse } from "../envelope.js";
import { MCP_ERROR_CODES } from "../types.js";
import { validateArgs } from "../pipeline/validate.js";
import { precheck } from "../pipeline/state-precheck.js";
import { runRules } from "../pipeline/rules.js";
import { emitAudit } from "../audit-line.js";
// r6 supports.createParentSpec (contract 0.16; WRLD coords extension in 0.18).
// records.create accepts a `parent` object with three valid shapes (all field
// names match the daemon's records.create exactly — `file`, `formId`,
// `subGroup`, `coords` — so what the agent passes in is what the daemon sees,
// modulo a transparent "0x" prefix strip on formId):
//
//   CELL / DIAL / QUST child:
//     { file, formId, subGroup? }
//
//   WRLD persistent child:
//     { file, formId, subGroup: "Persistent" }
//
//   WRLD exterior child (cell at coords):
//     { file, formId, coords: [number, number] }
//
// Per AGENTS.md "MCP inputSchema Anthropic Compatibility (2026-06-17)" the
// inputSchema must NOT use top-level anyOf/oneOf/allOf — and we extend that
// rule pragmatically here: parent's fields live flat on a single object and
// Zod-side refinement enforces the discriminated-union shape (subGroup XOR
// coords). Bad shapes are rejected as `invalid_request` with a clear hint.
// Intent-tool parent spec MUST match the daemon's records.create parent
// shape — `{ file, formId, subGroup?, coords? }`. Empirically verified against
// FO4Edit 4.1.6r6 daemon 2026-06-18. The KB record
// `xedit-records-create-parent-spec.v1.md` documents the same shape; agents
// reading the KB and calling this wrapper should not need to remap anything.
//
// Earlier drafts of this schema used `parentFile`/`parentFormId` (inherited
// from issue #4's initial wording) which mismatched both the daemon AND the
// KB; the wrapper never produced a successful records.create call against
// the live daemon until this alignment landed.
const ParentSpec = z
    .object({
    file: z.string().min(1),
    formId: z.string().regex(/^(0x)?[0-9a-fA-F]{1,8}$/),
    subGroup: z.string().min(1).optional(),
    coords: z.tuple([z.number(), z.number()]).optional(),
})
    .refine((p) => !(p.subGroup && p.coords), {
    message: "parent.subGroup and parent.coords are mutually exclusive. Use subGroup for CELL/DIAL/QUST/WRLD-persistent and coords for WRLD-exterior cells.",
});
const Args = z.object({
    targetFile: z.string().min(1),
    signature: z
        .string()
        .regex(/^[A-Z0-9_]{4}$/, { message: "signature must be a 4-char xEdit record signature, e.g. REFR, NPC_, ACHR" }),
    parent: ParentSpec,
    editorId: z.string().min(1).optional(),
    formData: z.record(z.unknown()).optional(),
});
/**
 * Normalize the parent spec for daemon forwarding: strip "0x" prefix from
 * `formId` so the daemon sees plain hex. The schema and daemon already agree
 * on `{ file, formId, subGroup?, coords? }`; no key renaming needed.
 */
function normalizeParentSpec(args) {
    const parent = args.parent;
    if (!parent || typeof parent !== "object")
        return args;
    const p = parent;
    if (typeof p.formId !== "string")
        return args;
    const f = p.formId;
    if (!(f.startsWith("0x") || f.startsWith("0X")))
        return args;
    return { ...args, parent: { ...p, formId: f.slice(2) } };
}
export function makeCreateChildRecordHandler(opts) {
    return async (args) => {
        const ctx = opts.getContext();
        if (!ctx) {
            return refuse({
                tool: "xedit_create_child_record",
                summary: "Session not established",
                code: MCP_ERROR_CODES.STATE_VIOLATION,
                hint: "Call xedit_session first.",
            });
        }
        // Validate first so structurally bad args never reach the consent gate
        // (the agent gets a clearer `invalid_request` than `mutation_requires_*`).
        const v = validateArgs(Args, args, { tool: "xedit_create_child_record" });
        if (v) {
            await emitAudit({ audit: opts.audit, tool: "xedit_create_child_record", args, env: v, ctx });
            return v;
        }
        // MUTATING: gate on supports.iKnowWhatImDoing. The standard precheck path
        // would return state_violation; this tool surfaces a more specific
        // `mutation_requires_iknowwhatimdoing` code so agents can route into the
        // setup skill instead of conflating it with a missing daemon.
        if (ctx.consentEnabled !== true) {
            const env = refuse({
                tool: "xedit_create_child_record",
                summary: "Mutating call requires xEdit -IKnowWhatImDoing consent",
                code: "mutation_requires_iknowwhatimdoing",
                hint: "Relaunch the xEdit daemon with the -IKnowWhatImDoing flag set, then retry. " +
                    "See xedit_session output: data.consentEnabled must be true.",
            });
            await emitAudit({ audit: opts.audit, tool: "xedit_create_child_record", args, env, ctx });
            return env;
        }
        const p = precheck({ tool: "xedit_create_child_record", args }, { ctx, needs: { daemon: true } });
        if (p) {
            await emitAudit({ audit: opts.audit, tool: "xedit_create_child_record", args, env: p, ctx });
            return p;
        }
        const r = await runRules({
            tool: "xedit_create_child_record",
            args,
            ctx,
            registry: opts.registry,
        });
        if (r.refusal) {
            await emitAudit({
                audit: opts.audit,
                tool: "xedit_create_child_record",
                args,
                env: r.refusal,
                ctx,
                ruleHits: r.ruleHits,
            });
            return r.refusal;
        }
        const daemonArgs = normalizeParentSpec(args);
        const native = await opts.adapter.call({ command: "records.create", args: daemonArgs });
        if (!native.ok) {
            const env = refuse({
                tool: "xedit_create_child_record",
                summary: `records.create failed: ${native.error.code}`,
                code: MCP_ERROR_CODES.DAEMON_ERROR,
                hint: native.error.message,
                detail: { daemonCode: native.error.code, daemonDetails: native.error.details },
            });
            await emitAudit({ audit: opts.audit, tool: "xedit_create_child_record", args, env, ctx });
            return env;
        }
        const env = okEnv({
            tool: "xedit_create_child_record",
            summary: `created ${String(args.signature)} in ${String(args.targetFile)}`,
            status: "completed",
            data: native.result,
            warnings: r.warnings,
        });
        await emitAudit({
            audit: opts.audit,
            tool: "xedit_create_child_record",
            args,
            env,
            ctx,
            ruleHits: r.ruleHits.length ? r.ruleHits : undefined,
        });
        return env;
    };
}
//# sourceMappingURL=create-child-record.js.map