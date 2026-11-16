"""
Real-time mixer for the outgoing leg: a single duplex stream that
continuously passes the real mic through to BlackHole 16ch (so classmates
always hear the user's raw English voice) while additively mixing in
synthesized Mandarin TTS clips on top as they become ready via inject().
Mix, not replace, per CLAUDE.md - both signals must reach Meet simultaneously.

Also fans out each raw mic frame to frame_queue so the ASR pipeline can
consume the same capture without opening a second stream on the mic.
"""

import queue

import numpy as np
import sounddevice as sd

import audio_io
import config

FRAME_MS = 20
FRAME_SAMPLES = int(config.SAMPLE_RATE * FRAME_MS / 1000)
NUM_OUTPUT_CHANNELS = 16


class Mixer:
    def __init__(self, mic_device=None, output_device=None):
        self.mic_device = mic_device if mic_device is not None else sd.default.device[0]
        self.output_device = (
            output_device
            if output_device is not None
            else audio_io.find_output_device_index(config.BLACKHOLE_16CH)
        )
        self.frame_queue = queue.Queue()
        self._pending_clips = queue.Queue()
        self._current_clip = np.zeros(0, dtype=np.float32)
        self._current_pos = 0

    def inject(self, samples):
        """Queue a mono float32 array (range -1..1, at config.SAMPLE_RATE) to mix on top of the mic passthrough."""
        if len(samples):
            self._pending_clips.put(samples)

    def _callback(self, indata, outdata, frames, time_info, status):
        if status:
            print(status)

        self.frame_queue.put(bytes(indata))

        mic = indata[:, 0].astype(np.int32)
        remaining = frames
        pos = 0
        while remaining > 0:
            if self._current_pos >= len(self._current_clip):
                try:
                    self._current_clip = self._pending_clips.get_nowait()
                    self._current_pos = 0
                except queue.Empty:
                    break
            take = min(remaining, len(self._current_clip) - self._current_pos)
            clip_chunk = self._current_clip[self._current_pos : self._current_pos + take]
            mic[pos : pos + take] += (clip_chunk * 32767).astype(np.int32)
            self._current_pos += take
            pos += take
            remaining -= take

        mixed = np.clip(mic, -32768, 32767).astype(np.int16)
        outdata.fill(0)
        outdata[:, 0] = mixed
        outdata[:, 1] = mixed

    def stream(self):
        return sd.Stream(
            device=(self.mic_device, self.output_device),
            channels=(1, NUM_OUTPUT_CHANNELS),
            samplerate=config.SAMPLE_RATE,
            blocksize=FRAME_SAMPLES,
            dtype="int16",
            callback=self._callback,
        )


if __name__ == "__main__":
    """
    Standalone checkpoint: runs the mixer, records what actually lands on
    BlackHole 16ch (ch 0/1), injects a TTS clip partway through, and plays
    the recording back - so you can hear your own passthrough voice AND the
    injected Mandarin clip mixed together, without needing a live Meet call.
    """
    import sys
    import time
    import wave

    import tts

    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0
    out_path = sys.argv[2] if len(sys.argv) > 2 else "mixer_test.wav"

    mixer = Mixer()
    capture_device = audio_io.find_input_device_index(config.BLACKHOLE_16CH)

    print(f"Recording BlackHole 16ch for {seconds:.0f}s - talk into your mic now.")
    recorded = sd.rec(
        int(seconds * config.SAMPLE_RATE),
        samplerate=config.SAMPLE_RATE,
        channels=2,
        dtype="int16",
        device=capture_device,
    )

    with mixer.stream():
        time.sleep(1.5)
        print("Injecting TTS clip...")
        mixer.inject(tts.synthesize("你好，这是一个测试。", sample_rate=config.SAMPLE_RATE))
        sd.wait()

    with wave.open(out_path, "wb") as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(config.SAMPLE_RATE)
        wav_file.writeframes(recorded.tobytes())

    print(f"Wrote {out_path}")
