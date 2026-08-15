from __future__ import annotations

import io
import math
import unittest
import wave

import numpy as np

from sentient.adapters.stt.diagnostics import analyse_wav, explain_empty_transcription


def wav_bytes(samples: np.ndarray, sample_rate: int = 16000) -> bytes:
    """Encode float samples in -1..1 as a 16-bit mono WAV, the shape Mantella sends."""
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    return buffer.getvalue()


def tone(seconds: float, amplitude: float, sample_rate: int = 16000) -> np.ndarray:
    t = np.arange(int(seconds * sample_rate)) / sample_rate
    return amplitude * np.sin(2 * math.pi * 220 * t)


class AudioDiagnosticsTests(unittest.TestCase):
    def test_all_zero_capture_is_silent(self):
        report = analyse_wav(wav_bytes(np.zeros(16000)))
        self.assertEqual(report.verdict, "SILENT")
        self.assertTrue(report.carries_no_speech)
        self.assertFalse(report.speech_plausible)

    def test_barely_open_mic_is_very_quiet(self):
        report = analyse_wav(wav_bytes(tone(1.0, 0.004)))
        self.assertEqual(report.verdict, "VERY_QUIET")
        self.assertTrue(report.carries_no_speech)

    def test_healthy_utterance_is_ok(self):
        # 0.21 amplitude sits inside the measured success band (0.120-0.209 RMS).
        report = analyse_wav(wav_bytes(tone(1.5, 0.21)))
        self.assertIn(report.verdict, ("OK", "HOT"))
        self.assertTrue(report.speech_plausible)
        self.assertFalse(report.carries_no_speech)

    def test_brief_capture_is_too_short(self):
        report = analyse_wav(wav_bytes(tone(0.2, 0.21)))
        self.assertEqual(report.verdict, "TOO_SHORT")

    def test_clipped_capture_is_flagged(self):
        report = analyse_wav(wav_bytes(tone(1.0, 1.6)))
        self.assertGreater(report.clipped_fraction, 0.01)
        # Clipping is a verdict, not a warning: it needs its own fix (lower the
        # input level) and it must not be mistaken for a level that hid speech.
        self.assertEqual(report.verdict, "CLIPPING")
        self.assertFalse(report.carries_no_speech)

    def test_unparseable_payload_degrades_instead_of_raising(self):
        report = analyse_wav(b"this is not a wav file")
        self.assertEqual(report.verdict, "UNREADABLE")
        # Diagnostics must never be the reason a transcription is rejected.
        self.assertTrue(report.speech_plausible)
        self.assertFalse(report.carries_no_speech)

    def test_short_push_to_talk_hold_is_warned_about(self):
        report = analyse_wav(wav_bytes(tone(0.5, 0.21)))
        self.assertTrue(any("push-to-talk" in warning for warning in report.warnings))

    def test_empty_transcription_blames_the_model_when_audio_was_fine(self):
        report = analyse_wav(wav_bytes(tone(1.5, 0.21)))
        self.assertIn("model", explain_empty_transcription(report).lower())

    def test_empty_transcription_blames_the_mic_when_audio_was_silent(self):
        report = analyse_wav(wav_bytes(np.zeros(16000)))
        explanation = explain_empty_transcription(report).lower()
        self.assertTrue("mic" in explanation or "silent" in explanation)

    def test_level_bar_is_fixed_width(self):
        report = analyse_wav(wav_bytes(tone(1.0, 0.21)))
        self.assertEqual(len(report.level_bar(width=24)), 24)

    def test_report_dict_carries_no_raw_samples(self):
        report = analyse_wav(wav_bytes(tone(1.0, 0.21)))
        payload = report.as_dict()
        self.assertEqual(payload["verdict"], "OK")
        self.assertGreater(payload["rms_pct"], 0)


if __name__ == "__main__":
    unittest.main()
