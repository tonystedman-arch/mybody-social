#!/usr/bin/env python3
"""
My Body — Reel audio bed.

Synthesises an original, wholly-owned audio track for each Reel, timed to that
reel's own segment boundaries. No samples, no library music, no licence, no
takedown risk: every sample is generated here from sine stacks and filtered
noise, so the sound is ours and it can be labelled as our original audio.

Why bother, rather than using a trending song:
  Meta's Content Publishing API cannot attach music-library tracks. Audio must
  be inside the video file at upload, or added by hand in the app afterwards.
  A Reel with no audio stream at all is worse than either — it reads as an ad
  and gives the audio page nothing to point at. See AUDIO.md.

Design: a low warm pad in A minor under everything, a soft sub thump and a
tick on each cut, a small rise into the hook, and a resolve under the end card.
Peaks around -17 dBFS so on-screen speech or a voiceover would still sit on top.

  python3 build_audio.py --demo   # writes demo.wav to listen to the bed alone
"""
import math
import wave

import numpy as np

SR = 44100
PEAK = 0.14          # ≈ -17 dBFS. Deliberately quiet; this is a bed, not a track.

# A minor. Root A2, with the fifth and octaves above it.
ROOT = 110.0
PAD_PARTIALS = [(1.0, 0.55), (1.5, 0.28), (2.0, 0.22), (3.0, 0.10), (4.0, 0.06)]
RESOLVE_PARTIALS = [(1.0, 0.5), (1.2, 0.3), (1.5, 0.3), (2.0, 0.22), (2.5, 0.14)]


def _t(n):
    return np.arange(n, dtype=np.float64) / SR


def pad(dur, partials=PAD_PARTIALS, detune=0.12):
    """Slow, slightly detuned sine stack — the bed everything else sits on."""
    n = int(dur * SR)
    t = _t(n)
    out = np.zeros(n)
    for i, (mult, amp) in enumerate(partials):
        # a very slow LFO on pitch keeps it from sounding like a test tone
        lfo = np.sin(2 * math.pi * (0.05 + 0.017 * i) * t) * detune
        out += amp * np.sin(2 * math.pi * (ROOT * mult + lfo) * t)
    return out / max(1e-9, np.max(np.abs(out)))


def lowpass(x, cutoff=900.0):
    """One-pole lowpass. Takes the glassy edge off the sine stack."""
    a = math.exp(-2 * math.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(x.size):
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def thump(dur=0.42, f0=68.0, f1=41.0):
    """Soft sub sweep for a cut. Felt more than heard on a phone speaker."""
    n = int(dur * SR)
    t = _t(n)
    f = f0 * (f1 / f0) ** (t / max(1e-9, dur))
    phase = 2 * math.pi * np.cumsum(f) / SR
    env = np.exp(-t * 7.5)
    return np.sin(phase) * env


def tick(dur=0.055, cutoff=2600.0):
    """Filtered noise blip — the UI-click layer on top of each cut."""
    n = int(dur * SR)
    rng = np.random.default_rng(7)
    x = rng.standard_normal(n)
    x = lowpass(x, cutoff)
    env = np.exp(-_t(n) * 90.0)
    return x / max(1e-9, np.max(np.abs(x))) * env


def rise(dur=0.9):
    """Small upward sweep leading into the hook."""
    n = int(dur * SR)
    t = _t(n)
    f = 220.0 * (2.6 ** (t / max(1e-9, dur)))
    phase = 2 * math.pi * np.cumsum(f) / SR
    env = np.sin(math.pi * t / max(1e-9, dur)) ** 1.6
    return np.sin(phase) * env * 0.5


def _add(buf, sig, at):
    i = int(at * SR)
    if i >= buf.size:
        return
    j = min(buf.size, i + sig.size)
    buf[i:j] += sig[: j - i]


def render_bed(cuts, total, card_at=None):
    """
    cuts    — segment start times in seconds (the first is the hook at 0.0)
    total   — reel duration in seconds
    card_at — when the end card starts, so the pad can resolve under it
    """
    n = int(total * SR)
    buf = np.zeros(n)

    # the pad, in two parts: minor bed, then a resolve under the end card
    split = card_at if card_at is not None else total
    bed = lowpass(pad(split), 780.0)
    _add(buf, bed * 0.85, 0.0)
    if card_at is not None and total > card_at:
        res = lowpass(pad(total - card_at, RESOLVE_PARTIALS), 950.0)
        # crossfade the resolve in over 0.4s so the chord change is not a jolt
        f = min(res.size, int(0.4 * SR))
        if f:
            res[:f] *= np.linspace(0, 1, f)
        _add(buf, res * 0.9, card_at)

    # a rise into the hook, then a cut sound on every segment boundary
    _add(buf, rise(0.9) * 0.5, 0.05)
    for i, c in enumerate(cuts):
        if c <= 0.01:
            continue
        _add(buf, thump() * (0.85 if i else 0.6), c - 0.03)
        _add(buf, tick() * 0.30, c)

    # envelope: fade in, fade out, and a gentle duck under the end card entry
    fi = int(0.6 * SR)
    buf[:fi] *= np.linspace(0, 1, fi)
    fo = int(min(1.3, total * 0.25) * SR)
    buf[-fo:] *= np.linspace(1, 0, fo)

    peak = np.max(np.abs(buf))
    if peak > 0:
        buf *= PEAK / peak

    # light stereo width on the pad only — keeps the cuts centred
    left = buf.copy()
    right = np.roll(buf, int(0.008 * SR)) * 0.97
    return np.stack([left, right], axis=1)


def write_wav(path, stereo):
    data = np.clip(stereo, -1.0, 1.0)
    pcm = (data * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == '__main__':
    import sys
    if '--demo' in sys.argv:
        cuts = [0.0, 3.0, 6.2, 9.4, 12.6]
        write_wav('demo.wav', render_bed(cuts, 18.0, card_at=15.6))
        print('wrote demo.wav — 18s, cuts at', cuts)
