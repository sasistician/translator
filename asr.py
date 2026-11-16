"""
Google Cloud Speech-to-Text streaming, gated by a local webrtcvad voice-activity
detector so only frames belonging to actual speech (plus a short pre/post-roll)
are billed as streamed minutes. This is the cost control described in CLAUDE.md —
without it, streaming runs the full call duration regardless of silence.
"""

import collections

import webrtcvad
from google.cloud import speech

FRAME_MS = 20  # webrtcvad requires 10/20/30ms frames
PRE_ROLL_FRAMES = 10  # ~200ms of audio kept before speech onset
# Google's own endpointer needs to see continued (silent) audio to decide an
# utterance is over and emit is_final - too short a post-roll and our local
# gate stops sending frames before Google ever gets enough trailing silence
# to close out the result, so it just stalls waiting for more input.
POST_ROLL_FRAMES = 50  # ~1000ms of trailing silence kept after speech offset


class VadGate:
    """Buffers raw frames and yields only frames belonging to speech segments."""

    def __init__(self, aggressiveness=2):
        self._vad = webrtcvad.Vad(aggressiveness)
        self._pre_roll = collections.deque(maxlen=PRE_ROLL_FRAMES)
        self._triggered = False
        self._silence_run = 0

    def process(self, frame_bytes, sample_rate):
        is_speech = self._vad.is_speech(frame_bytes, sample_rate)

        if not self._triggered:
            self._pre_roll.append(frame_bytes)
            if is_speech:
                self._triggered = True
                self._silence_run = 0
                out = list(self._pre_roll)
                self._pre_roll.clear()
                return out
            return []

        if is_speech:
            self._silence_run = 0
            return [frame_bytes]

        self._silence_run += 1
        if self._silence_run <= POST_ROLL_FRAMES:
            return [frame_bytes]

        self._triggered = False
        self._silence_run = 0
        return []


def streaming_recognize(frame_queue, language_code, sample_rate):
    """
    frame_queue: a queue.Queue yielding 20ms int16 mono PCM byte frames,
        with a None sentinel to signal end of stream.
    language_code: e.g. "en-US" or "cmn-Hans-CN".
    Yields google.cloud.speech.StreamingRecognizeResponse objects.

    Opens one bounded Google streaming session per detected utterance
    (pre-roll + speech + post-roll), rather than one session for the whole
    program run. This is required, not just a cost optimization: gRPC
    streaming_recognize expects continuous near-real-time audio and times
    out ("Audio Timeout Error") if nothing is sent during silence, so a
    single long-lived session fed only during speech would stall on the
    first gap. Per-utterance sessions also make Google emit a reliable
    is_final when we close the request stream, instead of it staying open
    indefinitely waiting for more input.
    """
    client = speech.SpeechClient()
    gate = VadGate()

    recognition_config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=sample_rate,
        language_code=language_code,
        model="latest_long",
    )
    streaming_config = speech.StreamingRecognitionConfig(
        config=recognition_config,
        interim_results=True,
    )

    def next_utterance_frames():
        """Blocks until speech begins, returning its pre-roll + first frame(s)."""
        while True:
            frame = frame_queue.get()
            if frame is None:
                return None
            gated = gate.process(frame, sample_rate)
            if gated:
                return gated

    def utterance_request_generator(first_frames):
        for f in first_frames:
            yield speech.StreamingRecognizeRequest(audio_content=f)
        while True:
            frame = frame_queue.get()
            if frame is None:
                return
            gated = gate.process(frame, sample_rate)
            if not gated:
                return  # post-roll elapsed - utterance is over, close this session
            for f in gated:
                yield speech.StreamingRecognizeRequest(audio_content=f)

    while True:
        first_frames = next_utterance_frames()
        if first_frames is None:
            return
        yield from client.streaming_recognize(
            streaming_config, utterance_request_generator(first_frames)
        )
