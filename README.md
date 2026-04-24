# JARVIS — Clap-triggered Windows automation

A background Python service that listens for a **double clap** on the default
microphone and, when detected:

1. Speaks a greeting via Windows SAPI5 ("Good morning, sir. Initializing your systems.")
2. Launches the **Discord** desktop app
3. Opens **Claude** (desktop app if installed, otherwise `https://claude.ai`)
4. Opens **Microsoft Edge** to `https://desiretolearn.msu.edu`

All four actions kick off concurrently the moment a double clap is detected.

## Requirements

- Windows 10 or 11
- Python 3.9+ on `PATH` (`python --version` should work in PowerShell)
- A working microphone

## Install

From a PowerShell prompt in this folder:

```powershell
.\install_startup.ps1
```

The script will:

1. `pip install` the dependencies (`sounddevice`, `numpy`, `pyttsx3`)
2. Drop a `JARVIS.lnk` shortcut into your user **Startup** folder so it
   launches automatically at every login
3. Start JARVIS immediately, hidden (no console window)

If PowerShell blocks the script, run it once with:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_startup.ps1
```

## Verify each component

Before trusting the listener, prove the pieces work in isolation.

**1. Test TTS + app launches without needing to clap:**

```powershell
python jarvis.py --test
```

You should hear the greeting and see Discord, Claude, and Edge (at D2L) open.

**2. Calibrate the clap threshold for your mic:**

```powershell
python jarvis.py --calibrate
```

Clap normally several times during the 30-second window. The script prints
a suggested `CLAP_RMS_FLOOR` value at the end. If it differs significantly
from the default `0.15`, edit the constant near the top of `jarvis.py`.

**3. Live test:**

```powershell
python jarvis.py
```

Double-clap. You should see `[trigger] double clap detected` in the console
and the actions should fire.

## Tuning

All thresholds live at the top of `jarvis.py`:

| Constant | Default | What it controls |
| --- | --- | --- |
| `CLAP_RMS_FLOOR` | `0.15` | Absolute loudness floor. Raise if false triggers, lower if claps are missed. |
| `CLAP_BG_MULTIPLIER` | `6.0` | How much louder than the rolling background a block must be. |
| `DOUBLE_CLAP_MIN_GAP` | `0.12` s | Minimum spacing between the two claps. |
| `DOUBLE_CLAP_MAX_GAP` | `0.9` s | Maximum spacing between the two claps. |
| `TRIGGER_COOLDOWN` | `6.0` s | Refractory period after a successful trigger. |

## Stop / uninstall

- **Stop the running instance**: open Task Manager and end the `pythonw.exe`
  process running `jarvis.py`.
- **Disable autostart**: delete `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\JARVIS.lnk`
  (or simply: `shell:startup` in Run, then delete `JARVIS.lnk`).

## Notes & limitations

- This was authored from a Linux sandbox — you (sir) are the first to run it
  on Windows hardware. Use `--test` and `--calibrate` to verify before relying
  on it.
- The Discord launcher tries `%LOCALAPPDATA%\Discord\Update.exe` first, then
  falls back to the `discord:` URI handler. The Claude launcher checks a few
  common install paths and falls back to the web app.
- `pythonw.exe` runs JARVIS without a console window. If you need to see logs,
  launch with `python jarvis.py` from a terminal instead.
