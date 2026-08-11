"""Level analysis for microphone audio arriving at the STT proxy.

Mantella reports a single opaque `Could not detect speech from mic input` warning
whether the capture was silent, the speech was too quiet, or the STT model simply
returned nothing for perfectly good audio. Those three cases need completely
different fixes, so we measure the waveform ourselves before handing it upstream
and print the verdict next to the transcription.

Only the stdlib `wave` reader is used: Mantella records 16 kHz mono 16-bit PCM
WAV, so there is no need to pull in a decoder for compressed formats. Anything
unreadable degrades to an `UNREADABLE` verdict rather than failing the request --
diagnostics must never be the reason a transcription is lost.
"""

from __future__ import annotations

import io
import wave
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

# Tuned against real Mantella captures. Successful transcriptions measured
# 12-21% RMS; the captures that produced "Could not detect speech" measured
# either exactly 0.00% (buffer never filled) or ~0.1-1% (mic barely open).
#
# SILENT is deliberately near zero so it means *no signal at all* -- the observed
# dead captures peaked at exactly 0.0, while a mic that is merely turned down too
# far still peaked at 0.8-7.7%. Those need opposite fixes (wrong input device
# versus input level), so they must not collapse into one verdict.
SILENT_PEAK = 0.002
QUIET_RMS = 0.01
CLIPPING_FRACTION = 0.01
SHORT_DURATION_S = 0.35

# Push-to-talk holds shorter than this frequently capture a stream that has not
# finished opening, which is what produces the all-zero WAV files.
PTT_RACE_DURATION_S = 0.7


@dataclass
class AudioReport:
    """What the waveform looks like, and whether it can plausibly hold speech."""

    verdict: str = "UNREADABLE"
    detail: str = ""
    byte_size: int = 0
    duration_s: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    sample_width: int = 0
    rms: float = 0.0
    peak: float = 0.0
    clipped_fraction: float = 0.0
    warnings: list[str] = field(default_factory=list)

    @property
    def speech_plausible(self) -> bool:
        """False when the audio itself explains an empty transcription."""
        return self.verdict in ("OK", "HOT", "UNREADABLE")

    @property
    def carries_no_speech(self) -> bool:
        """True when the waveform cannot contain speech, so any text is invented.

        Whisper reliably hallucinates stock phrases ("Thank you.", "Thanks for
        watching!") when handed silence -- a real capture here measuring exactly
        0.0 peak came back as "Thank you.". Passing that on would make the NPC
        answer something the player never said, which is worse than staying quiet.
        """
        return self.verdict in ("SILENT", "VERY_QUIET")

    def level_bar(self, width: int = 24) -> str:
        """A coarse RMS meter, so mic level is readable at a glance in the console."""
        filled = int(min(self.rms / 0.25, 1.0) * width)
        return "#" * filled + "-" * (width - filled)

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "detail": self.detail,
            "byte_size": self.byte_size,
            "duration_s": round(self.duration_s, 3),
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "rms_pct": round(self.rms * 100, 2),
            "peak_pct": round(self.peak * 100, 2),
            "clipped_pct": round(self.clipped_fraction * 100, 2),
            "warnings": list(self.warnings),
        }


def _to_mono_float(frames: bytes, sample_width: int, channels: int) -> np.ndarray:
    """Decode PCM frames to mono floats in [-1, 1]."""
    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}.get(sample_width)
    if dtype is None:
        raise ValueError(f"unsupported sample width: {sample_width} bytes")

    samples = np.frombuffer(frames, dtype=dtype).astype(np.float32)
    if sample_width == 1:
        # 8-bit WAV is unsigned, centred on 128.
        samples = (samples - 128.0) / 128.0
    else:
        samples /= float(2 ** (8 * sample_width - 1))

    if channels > 1:
        usable = (samples.size // channels) * channels
        samples = samples[:usable].reshape(-1, channels).mean(axis=1)
    return samples


def analyse_wav(payload: bytes) -> AudioReport:
    """Measure a WAV payload and classify whether it could contain speech."""
    report = AudioReport(byte_size=len(payload))

    try:
        with wave.open(io.BytesIO(payload), "rb") as handle:
            report.sample_rate = handle.getframerate()
            report.channels = handle.getnchannels()
            report.sample_width = handle.getsampwidth()
            frame_count = handle.getnframes()
            frames = handle.readframes(frame_count)
        samples = _to_mono_float(frames, report.sample_width, report.channels)
    except Exception as exc:  # noqa: BLE001 - diagnostics must never block STT
        report.detail = f"could not parse as WAV ({exc}); level checks skipped"
        return report

    if report.sample_rate:
        report.duration_s = samples.size / float(report.sample_rate)

    if samples.size == 0:
        report.verdict = "SILENT"
        report.detail = "the capture contains no samples at all"
        return report

    report.rms = float(np.sqrt(np.mean(np.square(samples))))
    report.peak = float(np.max(np.abs(samples)))
    report.clipped_fraction = float(np.mean(np.abs(samples) > 0.99))

    if report.sample_rate and report.sample_rate < 16000:
        report.warnings.append(
            f"sample rate {report.sample_rate} Hz is below Whisper's 16 kHz working rate"
        )
    if report.duration_s and report.duration_s < PTT_RACE_DURATION_S:
        report.warnings.append(
            f"push-to-talk held only {report.duration_s:.2f}s - the input stream may "
            "not have opened in time; hold the key ~0.5s longer than you speak"
        )

    report.verdict, report.detail = _classify(report)
    return report


def _classify(report: AudioReport) -> tuple[str, str]:
    if report.peak < SILENT_PEAK:
        return (
            "SILENT",
            "no signal whatsoever (peak ~0) - the mic was muted, the wrong input "
            "device is selected, or the capture ended before the stream opened",
        )
    if report.rms < QUIET_RMS:
        return (
            "VERY_QUIET",
            f"signal present but far too quiet (RMS {report.rms * 100:.2f}%) - "
            "raise the Windows input level or move closer to the mic",
        )
    if report.duration_s < SHORT_DURATION_S:
        return (
            "TOO_SHORT",
            f"only {report.duration_s:.2f}s of audio - too brief to transcribe",
        )
    if report.clipped_fraction > CLIPPING_FRACTION:
        return (
            "CLIPPING",
            f"{report.clipped_fraction * 100:.1f}% of samples are clipped - lower "
            "the Windows input level or disable mic boost",
        )
    if report.peak > 0.98:
        return (
            "HOT",
            "peaks are touching full scale; audio is usable but the input level "
            "could come down a notch",
        )
    return "OK", f"healthy speech level (RMS {report.rms * 100:.1f}%)"


def explain_empty_transcription(report: Optional[AudioReport]) -> str:
    """Why the STT model returned nothing, phrased as the next thing to try."""
    if report is None or report.speech_plausible:
        return (
            "audio level looks fine, so the STT model itself heard no words. If this "
            "repeats, the model is the problem - prefer whisper-large-v3-turbo over "
            "Moonshine Tiny, and check the spoken language matches the STT language."
        )
    return report.detail
