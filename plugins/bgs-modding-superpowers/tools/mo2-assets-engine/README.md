# mo2-assets-engine

Offline analyzer for MO2 profile state, loose files, and BA2/BSA archives.
Reads modlist.txt + plugins.txt + mod directories directly from disk;
does not require MO2 to be running.

Computes the same 6-bucket loose-vs-archive conflict resolution as MO2's
internal `ModInfoWithConflictInfo::doConflictCheck()`:

- loose-vs-loose (decided by modlist priority)
- loose-vs-archive (loose always wins)
- archive-vs-archive (decided by archive load order)

Used by:
- `mo2-assets` CLI (this package)
- `mo2_assets_inspector` MO2 IPluginTool plugin (Plan B; planned)

## CLI quick start

    pip install -e tools/mo2-assets-engine/[dev]
    mo2-assets summary --profile <MO2_Root>/profiles/Default --game-data "<game>/Data"
