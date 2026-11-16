"""
Milestone 3: outgoing leg with TTS + mixer injection.

A single Mixer duplex stream continuously passes the real mic through to
BlackHole 16ch and fans mic frames out to Google STT streaming (en-US) ->
Claude translate (en->zh) -> Google TTS synth (cmn-CN) -> mixed back on top
of the live mic passthrough. Classmates hear both the user's raw English
voice and the synthesized Mandarin simultaneously (mix, not replace, per
CLAUDE.md). ~2-4s latency per utterance is expected (consecutive-
interpretation style), not a bug.
"""

import asr
import config
import mixer
import translate
import tts


def run():
    config.check_required_env()

    m = mixer.Mixer()
    print("Mixer running (mic -> BlackHole 16ch). Listening (English)... Ctrl+C to stop.")

    with m.stream():
        try:
            for response in asr.streaming_recognize(
                m.frame_queue, "en-US", config.SAMPLE_RATE
            ):
                for result in response.results:
                    if not result.alternatives:
                        continue
                    transcript = result.alternatives[0].transcript
                    if result.is_final:
                        print(f"[EN] {transcript}")
                        zh = translate.translate(transcript, "en->zh")
                        print(f"[ZH] {zh}")
                        m.inject(tts.synthesize(zh, sample_rate=config.SAMPLE_RATE))
                    else:
                        print(f"[EN interim] {transcript}", end="\r")
        except KeyboardInterrupt:
            pass

    print("\nStopped.")


if __name__ == "__main__":
    run()
