# FHD OnlineChat 0.21 — FONT PREVIEW 1

Подготовленный комплект исходников для GitHub и проверки администрацией Nexus Mods. Все необходимые исходники клиентской DLL, шрифта и серверной логики включены. Ручное восстановление файлов не требуется. Оригинальные обозначения экспериментальной сборки сохранены.

This repository contains the supplied **0.21-font-preview1** experimental snapshot. Its original `EXPERIMENT_NOT_READY` metadata is preserved. Source preparation does not change the release status or certify approval by Nexus moderators.

## What is included

- `SOURCE/bridge.c` and `overlay.c`: native x86 client, WinHTTP transport, pilot identity reader and Direct3D9 overlay.
- All original C headers and linker DEF files, including the generated antialiased font data in `font16.h`.
- Original `server.js`: Cloudflare Worker / Durable Object chat service. Existing client fallback is preserved.
- Original font license, build notes, MSVC/Zig commands and offline QA scripts.
- A reproducible Python build entry point, original runtime hashes, provenance and a fresh verification report.

This mod is implemented in C and JavaScript; no SCR/RSON source conversion is needed. Game executables, the native loader and precompiled DLLs are excluded from this source archive. No game assets are required to compile the plugin.

## Rebuild the original client

The verified path uses **Python 3.12** and **ziglang 0.13.0**. On Linux, from the repository root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python build.py --verify-original
```

On Windows with Python 3.12 installed:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe build.py --verify-original
```

The Linux build was executed here. The Windows command path is supplied for reproducibility but was not run here. `build.py` invokes Zig's bundled C compiler and Windows import libraries; a separate Windows SDK is not needed for this path. Dependency installation needs package access. Compilation and local QA do not contact the chat services.

The output is `dist/FHD_OnlineChat-0.21-FONT-PREVIEW-1-install.zip`. It contains exactly four original runtime files under `Mods/OtherMods/FHD_OnlineChat/`: `ModuleInfo.txt`, the DLL, loader INI and `README_FIRST_RU.txt`. `SOURCE/ModuleInfo.txt` is editable UTF-8; the builder restores the original UTF-16LE BOM encoding losslessly.

The builder restores the recorded PE COFF `TimeDateStamp` (`0x6ae213a7`) after compiling. This is the only binary normalization. It does not alter code or data sections. With Zig 0.13.0, the resulting **entire 136704-byte DLL** matches the input SHA-256:

```text
02673522e654bb8d589c851cee15682b5677d8e3788739814ea708ac6590ee20
```

`--verify-original` checks all four runtime hashes and fails on any mismatch. It reads no original DLL and does not need the original archive. Original `BUILD_ZIG.cmd` remains available; by itself it does not normalize the timestamp. The supplied MSVC build route is retained but has not been verified.

## Install the rebuilt client

Close the game, extract the generated installation ZIP into the game directory, and restart. Preserve the supplied `Mods/OtherMods/FHD_OnlineChat/` location. The original package specifies XenoNativeLoader >= 0.6.5 and one of its two supported game builds. The loader and game EXEs must be installed separately; neither is replaced by this package. See the supplied Russian README for controls and behavior.

## Run offline verification

Install Node.js 24 in addition to the Python requirements, then run:

```sh
python tools/verify.py --report dist/verification.json
```

The runner compiles an instrumented DLL into a temporary directory and executes its x86 instructions in Unicorn. It exercises UI, input, font atlas, wrapping and connection/heartbeat logic through mocked WinAPI, WinHTTP and D3D. Server tests use Node's in-memory SQLite and mocked WebSockets. No actual chat messages are sent, no live server is queried, and nothing is deployed.

Optional compatibility verification uses the two separately supplied game EXEs:

```sh
python tools/verify.py --exe-a /path/to/Rangers.exe --exe-b /path/to/Rangers_second.exe --report dist/verification-with-exes.json
```

The runner requires these SHA-256 values, in order:

| Profile | SHA-256 |
| --- | --- |
| A | `83300344af802bc51e64389c58f047e5afdf195c133048098be3881fae29ed98` |
| B | `e43a4b15503c705eebe2d8ce5778c2a2fb090db515a3fd86d319e5c5aa692ebf` |

It maps both PE images at their original and relocated addresses, executes their selected render instructions and the plugin's hooks, and checks identity reads and rejection of altered signatures. This is CPU emulation with instrumented OS/graphics calls. It is **not** a Windows process or an in-game test. CI runs the standalone tests without bundling game EXEs.

`build-verification.json` records the freshly executed checks and logs for this preparation: **325 UI/compatibility checks, 125 wrapping/font checks, 28 mocked network checks and 5 server scenarios passed**. All four original runtime files were reproduced byte for byte. The original preview report and supplied Russian build notes are historical records; statements there about previous deployment or prior testing are not new verification results.

## QA fixture correction

Only one existing QA source file was adjusted: `emulate_font1.py`. The optional pilot identity test now calls the already existing `Test_HeartbeatStart(0)` before expecting another socket close after a new identity. This completes the previous reconnect in the synthetic worker, which has no real reconnect thread. Production C sources and `server.js` remain unchanged, and the production DLL still matches the original byte for byte.

## Font and backend scope

`font16.h` embeds all glyph alpha data required by the original build. Regeneration is optional: `make_font.py` needs Pillow and a separately available DejaVu Sans Mono TTF supplied with `--font`. Do not regenerate the header when checking exact reproduction. Preserve `SOURCE/FONT_LICENSE.txt` with the font data. No project-wide license grant has been invented.

The supplied backend source and client endpoints are preserved for review. Deployment configuration, account credentials and administration of the existing services are outside this source preparation. No Cloudflare or Supabase account settings were changed. The offline harness verifies the included server logic; availability and behavior of live infrastructure were not tested.

## Removed redundant material

The source package omits the prebuilt production DLL, 20 historical QA JSON files and 15 repeated screenshots. It retains the original font comparison image and replaces stale test output with one current report. The original input manifest is verified during preparation and summarized in `source-provenance.json`; it is not copied as an inaccurate manifest for the new tree. No production source, build header, linker definition or font license was removed.
