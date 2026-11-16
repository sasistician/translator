"""
Runs both legs together for a live Meet call: outgoing (mic -> EN ASR ->
ZH translate -> TTS -> mixed into BlackHole 16ch) and incoming (BlackHole
2ch -> ZH ASR -> EN translate -> captions), each as its own subprocess so
one leg's audio stream setup can't interfere with the other's (matches the
two-process pattern already proven safe in testing). Output from each is
tagged and interleaved on this terminal.

Usage: python main.py
Requires Meet's device pickers already set per CLAUDE.md (speaker -> "Meet
Output (Multi)", mic -> "BlackHole 16ch") and headphones worn to avoid echo.
"""

import os
import signal
import subprocess
import sys
import threading
import time

_DIR = os.path.dirname(os.path.abspath(__file__))
_stop = threading.Event()


def _on_sigint(signum, frame):
    _stop.set()


def _stream_output(proc, tag):
    for line in proc.stdout:
        print(f"[{tag}] {line.rstrip()}")


def run():
    signal.signal(signal.SIGINT, _on_sigint)
    env = dict(os.environ, PYTHONUNBUFFERED="1")

    outgoing = subprocess.Popen(
        [sys.executable, os.path.join(_DIR, "pipeline_outgoing.py")],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    incoming = subprocess.Popen(
        [sys.executable, os.path.join(_DIR, "pipeline_incoming.py")],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )

    threads = [
        threading.Thread(target=_stream_output, args=(outgoing, "OUT"), daemon=True),
        threading.Thread(target=_stream_output, args=(incoming, "IN"), daemon=True),
    ]
    for t in threads:
        t.start()

    print("Both legs running. Ctrl+C to stop.")
    while not _stop.is_set() and outgoing.poll() is None and incoming.poll() is None:
        time.sleep(0.2)

    print("\nStopping both legs...")
    for p in (outgoing, incoming):
        if p.poll() is None:
            p.send_signal(signal.SIGINT)
    for p in (outgoing, incoming):
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()

    print("Stopped.")


if __name__ == "__main__":
    run()
