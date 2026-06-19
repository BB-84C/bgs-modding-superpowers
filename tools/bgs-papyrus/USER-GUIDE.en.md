# bgs-papyrus User Guide

`bgs-papyrus` helps compile Papyrus source files (`.psc`) into game bytecode (`.pex`) and decompile `.pex` files back into `.psc` source for Skyrim, Fallout 4, and Starfield.

It does not include Bethesda's Creation Kit. You install the official Creation Kit from Steam, and this tool detects and drives the compiler.

## Supported games

- Skyrim Legendary Edition: `skyrimle`
- Skyrim Special Edition / Anniversary Edition: `skyrimse`
- Fallout 4: `fallout4`
- Starfield: `starfield`

Fallout 3, Fallout: New Vegas, and Oblivion do not use Papyrus and are not supported by this tool.

## 1. Install the official Creation Kit

Install the Creation Kit for your game from Steam.

For Starfield, the compiler is normally here:

```text
<Starfield>\Tools\Papyrus Compiler\PapyrusCompiler.exe
```

For Skyrim and Fallout 4, the compiler is normally under the game folder's `Papyrus Compiler` directory.

Bethesda's compiler is not redistributed with `bgs-papyrus`. Keep the official tools in the game or Creation Kit install location.

## 2. Detect the toolchain

Run detection before compiling or decompiling:

```powershell
bgs-papyrus detect-toolchain --json --game starfield
```

You can also ask for all detected toolchains:

```powershell
bgs-papyrus detect-toolchain --json
```

If the compiler is not found, confirm that the Creation Kit is installed and that the game path is discoverable by the tool.

## 3. Compile a script

Compile one `.psc` file:

```powershell
bgs-papyrus compile "D:\work\Scripts\Source\MyQuestScript.psc" --json --game starfield --out "D:\work\compiled" --import "D:\work\Scripts\Source"
```

For scripts that depend on each other, include every needed source directory with repeated `--import` options. For the Chronomark Starfield fixture, the fixture source directory itself had to be part of the import path because its scripts reference each other.

To compile all scripts in a directory:

```powershell
bgs-papyrus compile "D:\work\Scripts\Source" --json --game fallout4 --out "D:\work\compiled" --all
```

Compiled `.pex` files that will be used in game should go into an MO2 mod overlay:

```text
<MO2_Root>\mods\My Script Patch\Scripts\
```

Do not write compiled scripts directly into the game's `Data` folder.

## 4. Decompile a script

Decompile one `.pex` file:

```powershell
bgs-papyrus decompile "D:\mods\Example\Scripts\MyQuestScript.pex" --json --game starfield --out "D:\work\decompiled"
```

Decompile a directory tree:

```powershell
bgs-papyrus decompile "D:\mods\Example\Scripts" --json --game skyrimse --out "D:\work\decompiled" --recursive
```

Decompile uses Champollion. `bgs-papyrus` detects Champollion; it does not download it automatically. Install `Champollion.exe` here:

```text
~\.bgs-modding-superpowers\tools\champollion\Champollion.exe
```

You can also set `BGS_PAPYRUS_CHAMPOLLION` to an existing Champollion executable.

One PowerShell install shape for Champollion v1.3.2 from `Orvid/Champollion` releases:

```powershell
$root = "$HOME\.bgs-modding-superpowers\tools\champollion"; New-Item -ItemType Directory -Force -Path $root | Out-Null; $zip = Join-Path $root "Champollion.v1.3.2.zip"; Invoke-WebRequest "https://github.com/Orvid/Champollion/releases/download/v1.3.2/Champollion.v1.3.2.zip" -OutFile $zip; Expand-Archive -Force $zip $root
```

## 5. Starfield Guard syntax

Starfield added Guard syntax that Champollion v1.3.2 does not print in the official CK form. `bgs-papyrus` fixes the validated cases during Starfield decompile:

```text
Guard ... EndGuard       -> LockGuard ... EndLockGuard
TryGuard ... EndGuard    -> TryLockGuard ... EndTryLockGuard
```

The Starfield Creation Kit handles this syntax natively when compiling. The decompile post-processing was checked by recompiling the result with the real CK compiler.

## 6. Known manual-fixup cases

Champollion v1.3.2 still has unrelated decompile bugs, such as some remote-event casts. Those bugs can stop complex vanilla scripts from recompiling cleanly. Treat decompiled output as a strong starting point, then manually fix any remaining constructs that the compiler rejects.

The Starfield Guard rewrite is validated. The remaining caveat is about upstream Champollion output, not about the Guard post-processor.

## 7. Agent workflow

For agent-run work, a safe sequence is:

1. Run `bgs-papyrus capabilities --json`.
2. Run `bgs-papyrus detect-toolchain --json --game <game>`.
3. Compile or decompile with `--json`.
4. For compile output, place final `.pex` files in an MO2 overlay, never game `Data`.
5. If publishing decompiled source, recompile it first and report any manual fixes.
