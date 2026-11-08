# Startup performance

[繁體中文](startup-performance.md) | English

Windows now uses a PyInstaller onedir folder distributed as a ZIP. Extract the complete archive once, then launch `FShot/FShot.exe` while keeping `_internal` and `LICENSE` beside it. macOS retains its App/DMG format. Quit FShot before replacing the whole folder; update shortcuts and Start at login after moving it.

## Build and compare

```powershell
uv sync
uv run python scripts/build_app.py --windows-layout onefile
uv run python scripts/build_app.py
uv run python scripts/benchmark_startup.py --exe .\dist\FShot-0.1.12-windows-x64-onefile.exe --exe .\dist\FShot\FShot.exe --runs 5
```

Adjust the version to match your artifacts. Close existing FShot instances first to avoid hotkey conflicts. Onefile is retained as an instrumented comparison baseline; onedir is the default release artifact. The build validates `--version` and the packaged Qt GUI `--self-test` from a different working directory. The smoke check uses temporary settings and does not register hotkeys or capture the screen.

The benchmark alternates executable order each round. It launches each build from an unrelated working directory, writes per-run JSONL files and `build/startup-benchmark/results.json`, and reports the median `event_loop_ready` time. `--startup-probe` performs normal initialization, including hotkey registration, then shuts down and releases hotkeys after entering the event loop.

## Milestones

All times share an external monotonic start time. `python_entry` includes the bootloader, extraction, Python startup, and imports preceding the lightweight entry; it is not a measurement of extraction alone. `imports_ready` marks GUI/capture imports, `application_created` marks QApplication creation, and `controller_ready` includes editor/service/hotkey initialization. `tray_ready` means the tray show method returned, not that Explorer has finished painting the icon. `event_loop_ready` marks the first diagnostic callback in the running Qt loop.

For manual measurements, set `FSHOT_STARTUP_TRACE` to a writable absolute path and launch normally without `--startup-probe`. Open the editor or capture an image to record `editor_visible`, `first_document_ready`, and `first_capture_ready`. The benchmark also sets `FSHOT_STARTUP_STARTED_NS` using the launching process's `time.perf_counter_ns()` to include pre-Python costs. No trace is written unless explicitly enabled.

Cache state, antivirus scanning, and machine load affect results. A first sample is not a guaranteed cold boot. Keep individual samples, compare alternating runs on the same machine, and report medians rather than applying rePDF timings to FShot.

Subsequent stages may evaluate early single-instance forwarding and lazy editor/virtual-display initialization using these measurements.

## Local packaged results (2026-11-08)

Windows now forwards repeat launches to the existing editor using session-local native events and a mutex before importing Qt. Requests made during initialization remain pending. Process exit releases the handles without persistent lock files. Version and self-test commands remain independent; quit existing instances before running startup probes. macOS/Linux behavior and editor initialization are unchanged. The measurements below predate this single-instance change.

The same in-development 0.1.12 source, Python 3.14.6, and locked dependencies were used on one Windows machine, with five alternating runs per build. The folder executable was extracted from the release ZIP into a path containing spaces. Times measure external launch to event_loop_ready, not Explorer tray painting or first capture.

| Run | Onefile (seconds) | Onedir (seconds) |
| --- | ---: | ---: |
| 1 | 6.947 | 2.378 |
| 2 | 5.478 | 1.066 |
| 3 | 7.082 | 1.679 |
| 4 | 8.103 | 2.375 |
| 5 | 7.352 | 1.637 |
| Median | 7.082 | 1.679 |

The median decreased by about 76% in this sample. Median python_entry time decreased from 4.342 to 0.436 seconds, indicating lower pre-entry costs; these include extraction, bootloader, Python, and early imports, not extraction alone. This is not a cold-boot test or a guarantee for other systems. Raw JSONL and results are retained locally under `build/startup-benchmark/`.
