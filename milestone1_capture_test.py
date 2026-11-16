"""
Milestone 1 sanity check: records a few seconds from BlackHole 2ch and saves
a WAV file, so you can confirm Meet's played audio (speaker output routed
through "Meet Output (Multi)") is actually arriving at BlackHole 2ch.

Usage: python milestone1_capture_test.py [seconds] [out_path]
"""
import sys
import wave

import sounddevice as sd

import audio_io
import config


def record(seconds, out_path):
    device_index = audio_io.find_input_device_index(config.BLACKHOLE_2CH)
    channels = 2
    print(f"Recording {seconds}s from BlackHole 2ch (device {device_index})...")
    audio = sd.rec(
        int(seconds * config.SAMPLE_RATE),
        samplerate=config.SAMPLE_RATE,
        channels=channels,
        dtype="int16",
        device=device_index,
    )
    sd.wait()
    with wave.open(out_path, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(config.SAMPLE_RATE)
        wav_file.writeframes(audio.tobytes())
    print(f"Wrote {out_path} — play it back and confirm it captured Meet's audio.")


if __name__ == "__main__":
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
    out_path = sys.argv[2] if len(sys.argv) > 2 else "milestone1_capture_test.wav"
    record(seconds, out_path)
