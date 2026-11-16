"""
Milestone 1 sanity check: continuously passes your real mic through to
BlackHole 16ch, which Google Meet should have set as its microphone input.

Run this, join a (real or test) Meet call with Meet's mic set to
"BlackHole 16ch", and confirm the other participant hears you normally.
Ctrl+C to stop.
"""
import sounddevice as sd

import audio_io
import config


def callback(indata, outdata, frames, time, status):
    if status:
        print(status)
    outdata.fill(0)
    outdata[:, 0:1] = indata
    outdata[:, 1:2] = indata


def main():
    output_device = audio_io.find_output_device_index(config.BLACKHOLE_16CH)
    print(f"Mic -> BlackHole 16ch (device {output_device}). Ctrl+C to stop.")
    with sd.Stream(
        device=(sd.default.device[0], output_device),
        channels=(1, 16),
        samplerate=config.SAMPLE_RATE,
        callback=callback,
    ):
        while True:
            sd.sleep(1000)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
