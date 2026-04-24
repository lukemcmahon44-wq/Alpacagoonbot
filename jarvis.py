"""JARVIS: a clap-triggered Windows automation agent.

Listens to the default microphone for a double clap and, on detection,
speaks a greeting and launches Discord, Claude, and Edge (at D2L).

Usage:
    python jarvis.py              # normal listening mode
    python jarvis.py --test       # run the trigger actions once, no clap
    python jarvis.py --calibrate  # print mic RMS for 30s to help tune
"""

import argparse
import os
import queue
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import numpy as np
import sounddevice as sd
import pyttsx3


# ---------- Configuration ----------

SAMPLE_RATE = 44_100
BLOCK_SIZE = 1024           # ~23 ms per block at 44.1 kHz
CHANNELS = 1

# A block counts as a clap if its RMS is above an absolute floor
# AND significantly louder than a rolling background estimate.
CLAP_RMS_FLOOR = 0.15       # 0.0-1.0; microphone-dependent, tune with --calibrate
CLAP_BG_MULTIPLIER = 6.0
BG_DECAY = 0.995            # higher = background adapts more slowly

# Timing between the two clap onsets that counts as a "double clap".
DOUBLE_CLAP_MIN_GAP = 0.12
DOUBLE_CLAP_MAX_GAP = 0.9

# Debounce within a single clap's decay envelope, and cooldown after triggers.
ONSET_REFRACTORY = 0.12
TRIGGER_COOLDOWN = 6.0

GREETING = "Good morning, sir. Initializing your systems."

CLAUDE_URL = "https://claude.ai"
D2L_URL = "https://desiretolearn.msu.edu"


# ---------- Text to speech ----------

def speak(text: str) -> None:
    """Blocking SAPI5 TTS. Prefers a deep male voice when available."""
    engine = pyttsx3.init()
    engine.setProperty("rate", 175)
    engine.setProperty("volume", 1.0)

    preferred = ("David", "Guy", "Mark", "Zira")
    try:
        voices = engine.getProperty("voices")
        chosen = None
        for pref in preferred:
            for v in voices:
                if pref.lower() in (v.name or "").lower():
                    chosen = v.id
                    break
            if chosen:
                break
        if chosen:
            engine.setProperty("voice", chosen)
    except Exception:
        pass

    engine.say(text)
    engine.runAndWait()
    engine.stop()


# ---------- App launchers ----------

def _popen_detached(args) -> None:
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(args, creationflags=flags, close_fds=True)


def _start_via_shell(command_tail):
    # `cmd /c start "" <...>` resolves App Paths and protocol handlers
    # the same way the Run dialog does, without opening a visible window.
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    subprocess.Popen(["cmd", "/c", "start", "", *command_tail], creationflags=flags)


def open_discord() -> None:
    local = os.environ.get("LOCALAPPDATA", "")
    updater = Path(local) / "Discord" / "Update.exe"
    if updater.is_file():
        _popen_detached([str(updater), "--processStart", "Discord.exe"])
        return
    _start_via_shell(["discord:"])


def open_claude() -> None:
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        Path(local) / "AnthropicClaude" / "Claude.exe",
        Path(local) / "Programs" / "claude" / "Claude.exe",
        Path(local) / "Programs" / "Claude" / "Claude.exe",
    ]
    for c in candidates:
        if c.is_file():
            _popen_detached([str(c)])
            return
    webbrowser.open(CLAUDE_URL)


def open_edge_d2l() -> None:
    _start_via_shell(["msedge", D2L_URL])


def run_actions() -> None:
    """Speak the greeting and launch all three targets concurrently."""
    t_tts = threading.Thread(target=speak, args=(GREETING,), daemon=True)
    t_tts.start()
    for fn in (open_discord, open_claude, open_edge_d2l):
        threading.Thread(target=fn, daemon=True).start()
    t_tts.join(timeout=8.0)


# ---------- Clap detection ----------

def listen() -> None:
    q: "queue.Queue[np.ndarray]" = queue.Queue()

    def cb(indata, frames, time_info, status):
        # status can indicate overflow; ignore so detection keeps running.
        q.put(indata[:, 0].copy())

    bg_rms = 0.001
    last_onset = 0.0
    first_clap_at = 0.0
    last_trigger = 0.0

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        channels=CHANNELS,
        dtype="float32",
        callback=cb,
    ):
        print("JARVIS is listening. Double-clap to activate.", flush=True)
        while True:
            block = q.get()
            rms = float(np.sqrt(np.mean(block * block) + 1e-12))
            now = time.monotonic()

            loud = rms >= CLAP_RMS_FLOOR and rms >= CLAP_BG_MULTIPLIER * bg_rms

            # Only let the background track quiet blocks, otherwise claps
            # would pull the floor up and mask themselves.
            if not loud:
                bg_rms = BG_DECAY * bg_rms + (1.0 - BG_DECAY) * rms

            if now - last_trigger < TRIGGER_COOLDOWN:
                continue
            if not loud:
                continue
            if now - last_onset < ONSET_REFRACTORY:
                continue

            last_onset = now
            gap = now - first_clap_at
            if DOUBLE_CLAP_MIN_GAP <= gap <= DOUBLE_CLAP_MAX_GAP:
                last_trigger = now
                first_clap_at = 0.0
                print("[trigger] double clap detected", flush=True)
                threading.Thread(target=run_actions, daemon=True).start()
            else:
                first_clap_at = now


# ---------- Diagnostic modes ----------

def test_actions() -> None:
    print("Running trigger actions once (no clap required)...", flush=True)
    run_actions()
    time.sleep(2.0)


def calibrate(seconds: float = 30.0) -> None:
    print(f"Calibrating for {seconds:.0f}s. Clap normally a few times.", flush=True)
    q: "queue.Queue[np.ndarray]" = queue.Queue()

    def cb(indata, frames, time_info, status):
        q.put(indata[:, 0].copy())

    peak = 0.0
    start = time.monotonic()
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        channels=CHANNELS,
        dtype="float32",
        callback=cb,
    ):
        while time.monotonic() - start < seconds:
            block = q.get()
            r = float(np.sqrt(np.mean(block * block) + 1e-12))
            if r > peak:
                peak = r
            if r > 0.05:
                print(f"  rms={r:.3f}", flush=True)
    print(f"\nPeak observed: {peak:.3f}")
    print(f"Suggested CLAP_RMS_FLOOR: {max(peak * 0.6, 0.08):.3f}")


# ---------- Entry point ----------

def main() -> int:
    p = argparse.ArgumentParser(description="JARVIS clap-triggered automation.")
    p.add_argument("--test", action="store_true",
                   help="Run the trigger actions once (TTS + app launches).")
    p.add_argument("--calibrate", action="store_true",
                   help="Print microphone RMS for 30s to help tune thresholds.")
    args = p.parse_args()

    try:
        if args.test:
            test_actions()
        elif args.calibrate:
            calibrate()
        else:
            listen()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
