"""
Milestone 4: incoming leg, captions only.

Captures whatever Meet plays (routed through "Meet Output (Multi)" into
BlackHole 2ch), runs it through Google STT streaming (cmn-Hans-CN) gated by
the same per-utterance VAD design as the outgoing leg, translates finalized
Mandarin transcripts to English via Claude, and prints both as captions.
No TTS/synthesis for this leg, per CLAUDE.md - captions only.
"""

import queue

import numpy as np
import sounddevice as sd

import asr
import audio_io
import config
import translate

FRAME_MS = 20
FRAME_SAMPLES = int(config.SAMPLE_RATE * FRAME_MS / 1000)


def run():
    config.check_required_env()

    device_index = audio_io.find_input_device_index(config.BLACKHOLE_2CH)
    frame_queue = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print(status)
        mono = indata.astype(np.int32).mean(axis=1).astype(np.int16)
        frame_queue.put(mono.tobytes())

    print("Listening to Meet audio (BlackHole 2ch)... Ctrl+C to stop.")

    stream = sd.InputStream(
        device=device_index,
        channels=2,
        samplerate=config.SAMPLE_RATE,
        blocksize=FRAME_SAMPLES,
        dtype="int16",
        callback=callback,
    )

    with stream:
        try:
            for response in asr.streaming_recognize(
                frame_queue, "cmn-Hans-CN", config.SAMPLE_RATE
            ):
                for result in response.results:
                    if not result.alternatives:
                        continue
                    transcript = result.alternatives[0].transcript
                    if result.is_final:
                        print(f"[ZH] {transcript}")
                        en = translate.translate(transcript, "zh->en")
                        print(f"[EN] {en}")
                    else:
                        print(f"[ZH interim] {transcript}", end="\r")
        except KeyboardInterrupt:
            pass

    print("\nStopped.")


if __name__ == "__main__":
    run()
