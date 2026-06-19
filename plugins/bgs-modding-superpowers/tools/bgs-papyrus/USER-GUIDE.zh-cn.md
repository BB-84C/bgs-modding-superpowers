# bgs-papyrus 使用手册

`bgs-papyrus` 用于把 Papyrus 源码文件（`.psc`）编译成游戏读取的字节码（`.pex`），也可以把 `.pex` 反编译回 `.psc`，适用于 Skyrim、Fallout 4 和 Starfield。

本工具不包含 Bethesda 的 Creation Kit。用户需要先从 Steam 安装官方 Creation Kit，本工具只负责检测并调用其中的编译器。

## 支持的游戏

- Skyrim 传奇版：`skyrimle`
- Skyrim 特别版 / 周年版：`skyrimse`
- Fallout 4：`fallout4`
- Starfield：`starfield`

Fallout 3、Fallout: New Vegas 和 Oblivion 没有 Papyrus，不属于本工具范围。

## 1. 安装官方 Creation Kit

先从 Steam 安装目标游戏对应的 Creation Kit。

Starfield 的编译器通常在这里：

```text
<Starfield>\Tools\Papyrus Compiler\PapyrusCompiler.exe
```

Skyrim 和 Fallout 4 的编译器通常在游戏目录下的 `Papyrus Compiler` 文件夹里。

Bethesda 的编译器不会随 `bgs-papyrus` 分发。不要把官方编译器复制进本仓库或插件目录。

## 2. 检测工具链

编译或反编译前先运行检测：

```powershell
bgs-papyrus detect-toolchain --json --game starfield
```

也可以检测所有可识别的工具链：

```powershell
bgs-papyrus detect-toolchain --json
```

如果没有找到编译器，先确认 Creation Kit 已安装，并且工具能识别到游戏安装路径。

## 3. 编译脚本

编译单个 `.psc` 文件：

```powershell
bgs-papyrus compile "D:\work\Scripts\Source\MyQuestScript.psc" --json --game starfield --out "D:\work\compiled" --import "D:\work\Scripts\Source"
```

如果脚本之间互相引用，需要用多个 `--import` 把相关源码目录都加入导入路径。Chronomark 的 Starfield 验证样例就需要把样例自己的源码目录加入导入路径，因为两个脚本互相引用。

编译目录中的全部脚本：

```powershell
bgs-papyrus compile "D:\work\Scripts\Source" --json --game fallout4 --out "D:\work\compiled" --all
```

最终要进游戏使用的 `.pex` 应放进 MO2 覆盖层：

```text
<MO2_Root>\mods\My Script Patch\Scripts\
```

不要把编译结果直接写进游戏本体的 `Data` 目录。

## 4. 反编译脚本

反编译单个 `.pex` 文件：

```powershell
bgs-papyrus decompile "D:\mods\Example\Scripts\MyQuestScript.pex" --json --game starfield --out "D:\work\decompiled"
```

反编译整个目录：

```powershell
bgs-papyrus decompile "D:\mods\Example\Scripts" --json --game skyrimse --out "D:\work\decompiled" --recursive
```

反编译使用 Champollion。`bgs-papyrus` 只检测 Champollion，不会自动下载。请把 `Champollion.exe` 放到：

```text
~\.bgs-modding-superpowers\tools\champollion\Champollion.exe
```

也可以通过 `BGS_PAPYRUS_CHAMPOLLION` 指向已有的 Champollion 可执行文件。

从 `Orvid/Champollion` releases 安装 Champollion v1.3.2 的 PowerShell 一行命令示例：

```powershell
$root = "$HOME\.bgs-modding-superpowers\tools\champollion"; New-Item -ItemType Directory -Force -Path $root | Out-Null; $zip = Join-Path $root "Champollion.v1.3.2.zip"; Invoke-WebRequest "https://github.com/Orvid/Champollion/releases/download/v1.3.2/Champollion.v1.3.2.zip" -OutFile $zip; Expand-Archive -Force $zip $root
```

## 5. Starfield Guard 语法

Starfield 增加了 Guard 语法，但 Champollion v1.3.2 输出的写法不是官方 Creation Kit 接受的写法。`bgs-papyrus` 会在 Starfield 反编译后修正已经验证过的情况：

```text
Guard ... EndGuard       -> LockGuard ... EndLockGuard
TryGuard ... EndGuard    -> TryLockGuard ... EndTryLockGuard
```

Starfield Creation Kit 编译时原生支持这些官方语法。本工具的修正结果已经通过真实 CK 重新编译验证。

## 6. 需要手工修正的情况

Champollion v1.3.2 仍有一些与 Guard 无关的反编译问题，例如某些远程事件类型转换。这类问题可能导致复杂的原版脚本无法直接重新编译。

所以反编译结果应视为很好的起点，而不是保证所有脚本都能无修改发布。Guard 修正已经验证；剩余风险来自 Champollion 上游输出，遇到编译器报错时需要人工修正具体语句。

## 7. Agent 工作流程

让 Agent 执行时，推荐按这个顺序：

1. 运行 `bgs-papyrus capabilities --json`。
2. 运行 `bgs-papyrus detect-toolchain --json --game <game>`。
3. 使用带 `--json` 的编译或反编译命令。
4. 编译产物需要进游戏时，放入 MO2 覆盖层，不写入游戏 `Data`。
5. 如果要发布反编译源码，先重新编译验证，并报告仍需手工修正的内容。
