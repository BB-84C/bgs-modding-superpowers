$ErrorActionPreference = "Stop"

function Test-HasTransientPromptReference {
    param([string]$Content)

    return $Content -match '(?i)(docs[/\\][^\r\n`]*initial[^\r\n`]*p\w*mpt[^\r\n`]*\.md|initial\s+prompt\s+file)'
}

function Get-SectionContent {
    param(
        [string]$Content,
        [string]$Heading
    )

    $escapedHeading = [regex]::Escape($Heading)
    $match = [regex]::Match($Content, "(?sm)^$escapedHeading\s*(.*?)(?=^##\s|\z)")
    if (-not $match.Success) {
        throw "docs/roadmap.md is missing heading: $Heading"
    }

    return $match.Groups[1].Value
}

function Assert-ContainsSignals {
    param(
        [string]$SectionName,
        [string]$Content,
        [string[]]$Signals
    )

    foreach ($signal in $Signals) {
        if ($Content -notmatch [regex]::Escape($signal)) {
            throw "$SectionName is missing signal: $signal"
        }
    }
}

function Assert-ContainsNoSignals {
    param(
        [string]$SectionName,
        [string]$Content,
        [string[]]$Signals
    )

    foreach ($signal in $Signals) {
        if ($Content -match [regex]::Escape($signal)) {
            throw "$SectionName contains stale signal: $signal"
        }
    }
}

function Assert-MatchesAnyConcept {
    param(
        [string]$SectionName,
        [string]$Content,
        [object[]]$ConceptGroups
    )

    foreach ($group in $ConceptGroups) {
        $allMatched = $true
        foreach ($signal in $group) {
            if ($Content -notmatch [regex]::Escape($signal)) {
                $allMatched = $false
                break
            }
        }

        if ($allMatched) {
            return
        }
    }

    $expected = ($ConceptGroups | ForEach-Object { "[" + ($_ -join ", ") + "]" }) -join " or "
    throw "$SectionName is missing concept: $expected"
}

function Assert-ContainsPattern {
    param(
        [string]$SectionName,
        [string]$Content,
        [string]$Pattern
    )

    if ($Content -notmatch $Pattern) {
        throw "$SectionName is missing pattern: $Pattern"
    }
}

function Assert-ContainsAnyAnchorSet {
    param(
        [string]$SectionName,
        [string]$Content,
        [object[]]$AnchorSets
    )

    foreach ($set in $AnchorSets) {
        $matched = $true
        foreach ($anchor in $set) {
            if ($Content -notmatch [regex]::Escape($anchor)) {
                $matched = $false
                break
            }
        }

        if ($matched) {
            return
        }
    }

    $expected = ($AnchorSets | ForEach-Object { "[" + ($_ -join ", ") + "]" }) -join " or "
    throw "$SectionName is missing anchor set: $expected"
}

function Assert-ContainsConceptFamilies {
    param(
        [string]$SectionName,
        [string]$Content,
        [object[]]$Families
    )

    foreach ($family in $Families) {
        $familyMatched = $false

        foreach ($alternative in $family.Alternatives) {
            $alternativeMatched = $true
            foreach ($anchor in $alternative) {
                if ($Content -notmatch [regex]::Escape($anchor)) {
                    $alternativeMatched = $false
                    break
                }
            }

            if ($alternativeMatched) {
                $familyMatched = $true
                break
            }
        }

        if (-not $familyMatched) {
            $expected = ($family.Alternatives | ForEach-Object { "[" + ($_ -join ", ") + "]" }) -join " or "
            throw "$SectionName is missing concept family '$($family.Name)': $expected"
        }
    }
}

Assert-MatchesAnyConcept -SectionName "verifier self-check" -Content "future game-specific guidance and glossary planning" -ConceptGroups @(
    @("game-specific", "guidance"),
    @("glossary", "planning")
)

Assert-ContainsAnyAnchorSet -SectionName "verifier self-check" -Content "toolchain caution for Starfield and modpack docs" -AnchorSets @(
    @("Starfield", "toolchain"),
    @("modpack", "docs")
)

Assert-ContainsConceptFamilies -SectionName "verifier self-check" -Content "runtime setup and release baseline discipline" -Families @(
    @{ Name = "setup"; Alternatives = @(@("runtime", "setup")) },
    @{ Name = "baseline"; Alternatives = @(@("release", "baseline")) }
)

Assert-ContainsPattern -SectionName "verifier self-check" -Content "Phase 0 ... Phase 9 ... docs/plans/example.md" -Pattern "Phase\s+[0-9]"

if (-not (Test-HasTransientPromptReference "See docs/initial_prompt.md for context.")) {
    throw "Transient prompt guard should catch the standard initial prompt file reference"
}
if (-not (Test-HasTransientPromptReference "See docs/initial_pormpt.md for context.")) {
    throw "Transient prompt guard should catch the typo variant too"
}
if (Test-HasTransientPromptReference "See docs/plans/ for durable project docs.") {
    throw "Transient prompt guard should not flag normal supporting-doc references"
}

$requiredPaths = @(
    ".gitignore",
    ".opencode/INSTALL.md",
    ".opencode/README.md",
    "README.md",
    "docs/roadmap.md",
    "docs/standards/repo-hygiene.md"
)

$missing = $requiredPaths | Where-Object { -not (Test-Path $_) }
if ($missing.Count -gt 0) {
    throw "Missing required bootstrap files: $($missing -join ', ')"
}

$readme = Get-Content "README.md" -Raw
if ($readme -notmatch "BGS modpack curation" -or $readme -notmatch "not general mod authoring") {
    throw "README.md is missing the curation-vs-authoring scope statement"
}

$roadmap = Get-Content "docs/roadmap.md" -Raw
$missionSection = Get-SectionContent -Content $roadmap -Heading "## Mission"
$workflowSection = Get-SectionContent -Content $roadmap -Heading "## Systematic Modpack Workflow"
$capabilitySection = Get-SectionContent -Content $roadmap -Heading "## Capability Map"
$phaseLadderSection = Get-SectionContent -Content $roadmap -Heading "## Phase Ladder"
$dependencySection = Get-SectionContent -Content $roadmap -Heading "## Dependency / Blocker Map"
$notYetRealSection = Get-SectionContent -Content $roadmap -Heading "## Not Yet Real"
$gamePressureSection = Get-SectionContent -Content $roadmap -Heading "## Game-Specific Pressure Points"
$completedFoundationsSection = Get-SectionContent -Content $roadmap -Heading "## Completed Foundations"
$currentFocusSection = Get-SectionContent -Content $roadmap -Heading "## Current Focus"
$supportingDocsSection = Get-SectionContent -Content $roadmap -Heading "## Supporting Docs"

Assert-ContainsSignals -SectionName "docs/roadmap.md mission section" -Content $missionSection -Signals @(
    "BGS modpack curation",
    "Skyrim",
    "Fallout 4",
    "Starfield",
    "not general mod authoring",
    "workflow-first",
    "multi-session"
)

Assert-ContainsSignals -SectionName "docs/roadmap.md workflow section" -Content $workflowSection -Signals @(
    "MO2",
    "xEdit",
    "localization",
    "testing"
)

Assert-ContainsConceptFamilies -SectionName "docs/roadmap.md workflow section" -Content $workflowSection -Families @(
    @{ Name = "setup-runtime"; Alternatives = @(@("environment", "setup"), @("runtime", "toolchain")) },
    @{ Name = "evaluation"; Alternatives = @(@("mod", "evaluation"), @("discovery", "evaluation")) },
    @{ Name = "controlled-installation"; Alternatives = @(@("controlled", "installation"), @("incremental", "installation")) },
    @{ Name = "file-vs-plugin-order"; Alternatives = @(@("file", "plugin", "order"), @("deployment", "plugin", "order")) },
    @{ Name = "patch-vs-load-order"; Alternatives = @(@("load-order", "patch"), @("ordering", "patch")) },
    @{ Name = "diagnostics"; Alternatives = @(@("diagnostics", "troubleshooting"), @("logs", "crash")) },
    @{ Name = "documentation"; Alternatives = @(@("documentation", "modpack"), @("dev-log", "changelog")) }
)

Assert-MatchesAnyConcept -SectionName "docs/roadmap.md workflow section" -Content $workflowSection -ConceptGroups @(
    @("freeze", "release baseline"),
    @("document-and-freeze", "release-baseline"),
    @("validated state", "freeze")
)

Assert-ContainsSignals -SectionName "docs/roadmap.md capability map" -Content $capabilitySection -Signals @(
    "repository/standards",
    "OpenCode packaging",
    "repo-bootstrap agent",
    "mod evaluator",
    "install planner",
    "conflict auditor",
    "localization assistant",
    "test session guide",
    "native xEdit outer client",
    "safety hooks"
)

Assert-ContainsConceptFamilies -SectionName "docs/roadmap.md capability map" -Content $capabilitySection -Families @(
    @{ Name = "dev-log-changelog"; Alternatives = @(@("dev log", "workflow"), @("release", "changelog")) },
    @{ Name = "mcp-knowledge"; Alternatives = @(@("MCP", "integrations"), @("knowledge", "research")) },
    @{ Name = "archive-reasoning"; Alternatives = @(@("archive", "file"), @("loose-file", "reasoning")) },
    @{ Name = "diagnostics"; Alternatives = @(@("diagnostics", "triage"), @("crash", "triage")) },
    @{ Name = "save-safety"; Alternatives = @(@("save-safety", "automation"), @("save", "safety")) },
    @{ Name = "benchmark-smoke-test"; Alternatives = @(@("benchmark", "smoke-test"), @("smoke-test", "release baselines"), @("benchmark", "install batches")) }
)

Assert-MatchesAnyConcept -SectionName "docs/roadmap.md capability map" -Content $capabilitySection -ConceptGroups @(
    @("benchmark", "smoke-test"),
    @("benchmark", "install batches"),
    @("smoke-test", "release baselines")
)

Assert-MatchesAnyConcept -SectionName "docs/roadmap.md capability map" -Content $capabilitySection -ConceptGroups @(
    @("game-specific", "risk"),
    @("game-specific risk")
)

Assert-MatchesAnyConcept -SectionName "docs/roadmap.md capability map" -Content $capabilitySection -ConceptGroups @(
    @("mod-quality", "heuristics"),
    @("quality", "heuristics")
)

Assert-MatchesAnyConcept -SectionName "docs/roadmap.md capability map" -Content $capabilitySection -ConceptGroups @(
    @("localization", "glossary"),
    @("glossary", "translation")
)

Assert-ContainsSignals -SectionName "docs/roadmap.md phase ladder" -Content $phaseLadderSection -Signals @(
    "Phase 0",
    "Phase 9",
    "xEdit",
    "native xEdit outer client",
    "localization",
    "dev-log",
    "release changelog",
    "packaging"
)

Assert-ContainsNoSignals -SectionName "docs/roadmap.md phase ladder" -Content $phaseLadderSection -Signals @(
    "`xedit-cli` contract",
    "tools/xedit-cli/CONTRACT.md"
)

Assert-ContainsPattern -SectionName "docs/roadmap.md phase ladder" -Content $phaseLadderSection -Pattern "Phase\s+0"
Assert-ContainsPattern -SectionName "docs/roadmap.md phase ladder" -Content $phaseLadderSection -Pattern "Phase\s+9"

$phaseMatches = [regex]::Matches($phaseLadderSection, "Phase\s+[0-9]")
if ($phaseMatches.Count -lt 10) {
    throw "docs/roadmap.md phase ladder must include a multi-phase sequence through Phase 9"
}

Assert-ContainsSignals -SectionName "docs/roadmap.md dependency map" -Content $dependencySection -Signals @(
    "xEdit",
    "native xEdit outer client",
    "tools/mo2-vfs-launcher/xedit-client.md",
    "MCP",
    "localization"
)

Assert-ContainsNoSignals -SectionName "docs/roadmap.md dependency map" -Content $dependencySection -Signals @(
    "`xedit-cli` contract",
    "tools/xedit-cli/CONTRACT.md"
)

Assert-ContainsConceptFamilies -SectionName "docs/roadmap.md dependency map" -Content $dependencySection -Families @(
    @{ Name = "format-blocks-packaging"; Alternatives = @(@("plugin format", "OpenCode"), @("format", "packaging")) },
    @{ Name = "changelog-after-devlog"; Alternatives = @(@("release changelog", "dev-log"), @("changelog", "dev-log")) },
    @{ Name = "localization-after-stable-flows"; Alternatives = @(@("stable install", "conflict", "test"), @("install/conflict/test flows")) },
    @{ Name = "metadata-after-conflict-truth"; Alternatives = @(@("metadata integrations", "after", "conflict truth"), @("metadata", "conflict", "before")) },
    @{ Name = "save-safety-after-curator-loop"; Alternatives = @(@("save-safety", "follow", "real curator loop"), @("save-safety", "curator loop")) }
)

Assert-ContainsSignals -SectionName "docs/roadmap.md not yet real section" -Content $notYetRealSection -Signals @(
    "no functioning plugin package",
    "no working command entrypoints",
    "no real MCP adapters",
    "no completed read-only xEdit conflict-inspection workflow",
    "no usable end-to-end curator workflow",
    "no save-safety automation",
    "no write-capable patch generation"
)

Assert-ContainsSignals -SectionName "docs/roadmap.md game-specific pressure points section" -Content $gamePressureSection -Signals @(
    "Skyrim",
    "Fallout 4",
    "Starfield"
)

Assert-ContainsConceptFamilies -SectionName "docs/roadmap.md game-specific pressure points section" -Content $gamePressureSection -Families @(
    @{ Name = "skyrim-script-animation-behavior"; Alternatives = @(@("scripts", "animation"), @("behavior", "conflicts")) },
    @{ Name = "fo4-pressure"; Alternatives = @(@("precombine/previs", "Buffout"), @("BA2", "settlement"), @("precombine", "BA2")) },
    @{ Name = "starfield-toolchain-caution"; Alternatives = @(@("Starfield", "toolchain", "caution"), @("Starfield", "FO4/Skyrim", "assumptions"), @("Starfield", "evolving", "toolchain")) }
)

Assert-ContainsSignals -SectionName "docs/roadmap.md completed foundations section" -Content $completedFoundationsSection -Signals @(
    "docs/standards/repo-hygiene.md",
    "agents/repo-bootstrap/AGENT.md",
    "skills/conflict-auditor/SKILL.md",
    "hooks/runtime-compatibility.md",
    "templates/modpack/dev-log-template.md",
    "tools/mo2-vfs-launcher/xedit-client.md",
    "mcps/xedit-readonly.md",
    "tests/bootstrap/verify-all.ps1"
)

Assert-ContainsSignals -SectionName "docs/roadmap.md current focus section" -Content $currentFocusSection -Signals @(
    "first real workflow",
    "read-only xEdit conflict inspection",
    "conflict-auditor"
)

Assert-ContainsSignals -SectionName "docs/roadmap.md supporting docs section" -Content $supportingDocsSection -Signals @(
    "README.md",
    "docs/standards/repo-hygiene.md",
    "templates/README.md",
    "tools/README.md",
    "tools/mo2-vfs-launcher/xedit-client.md",
    "mcps/README.md",
    "tests/README.md"
)

Assert-ContainsPattern -SectionName "docs/roadmap.md supporting docs section" -Content $supportingDocsSection -Pattern "docs/plans/[^\s`]+\.md"

$planDocMatches = [regex]::Matches($supportingDocsSection, "docs/plans/[^\s`]+\.md")
if ($planDocMatches.Count -lt 2) {
    throw "docs/roadmap.md supporting docs section must include plan-doc support, not just README-style files"
}

if (Test-HasTransientPromptReference $roadmap) {
    throw "docs/roadmap.md should not treat the transient initial prompt file as a supporting source"
}

$gitignore = Get-Content ".gitignore" -Raw
foreach ($rule in @(".artifacts/*", "!.artifacts/.gitkeep", ".playwright-mcp/")) {
    if ($gitignore -notmatch [regex]::Escape($rule)) {
        throw ".gitignore is missing ignore rule: $rule"
    }
}

$repoHygiene = Get-Content "docs/standards/repo-hygiene.md" -Raw
foreach ($section in @("## Ignored Working Content", "## Artifact Lifecycle")) {
    if ($repoHygiene -notmatch [regex]::Escape($section)) {
        throw "docs/standards/repo-hygiene.md is missing section: $section"
    }
}

$install = Get-Content ".opencode/INSTALL.md" -Raw
foreach ($section in @("## Purpose", "## Bootstrap State", "## Later Work")) {
    if ($install -notmatch [regex]::Escape($section)) {
        throw ".opencode/INSTALL.md is missing section: $section"
    }
}
if ($install -notmatch "install commands" -or $install -notmatch "plugin metadata") {
    throw ".opencode/INSTALL.md is missing bootstrap install guidance"
}

Write-Host "Foundation bootstrap checks passed."
