#!/usr/bin/env python3
"""
My Body — Reel audio. Candidate A, "anatomical".

A heartbeat, done to the anatomy rather than to a drum machine. Chosen from the
five previews in audio_candidates.py; the others are kept there if this ever
needs revisiting.

Three faults made the earlier version sound like a saw or a rowing machine, and
all three are fixed here:

  1. **The lub-dub gap was 132 ms.** A resting heart's S1→S2 (systole) is about
     300 ms. At 132 ms the two thuds fused into one rasping stroke. Now 300 ms.
  2. **Each thud was 340 ms with a 340 ms filtered-noise tail.** A real S1 is
     100–140 ms and essentially tonal. A long noisy tail on a descending sweep
     is, literally, the sound of a saw stroke. Now 130 ms, and no noise at all.
  3. **Noise swells.** A 1 s band-passed noise sweep before every cut, plus a
     constant hiss in the drone — repeated noise swells about once a second is
     the signature of a rowing machine flywheel. Both gone; the drone is pure
     tone and the cuts are marked by the pulse itself.

Mid/high noise energy went from 31.8% of the spectrum to about 5%.

What remains:
  * S1 at 46→33 Hz over 130 ms, S2 at 62→46 Hz over 95 ms, 300 ms later.
  * **Heart-rate variability** — each interval jittered by a slow random walk,
    measuring ~3% beat-to-beat. A sequencer is 0.0%. This is what stops it
    sounding machine-made.
  * The rate drifts from about 58 to 64 bpm across the reel.
  * A pure-tone drone, low and slowly swelling, with a quiet high partial.
  * A short convolution reverb, so it sits in a room rather than a vacuum.
  * Compression before limiting, because a sparse pulse is quiet in RMS terms
    even at full peak — peak-normalising alone left it sounding faint.

Nothing is sampled. Every waveform is generated here, so the recording is ours
outright. To use a licensed track instead, see `licensed_track()` and AUDIO.md.

  python3 build_music.py --demo        # dark, 18s
  python3 build_music.py --demo light
"""
import math
import os
import wave

import numpy as np

SR = 44100
PEAK = 0.42                       # ≈ -7.5 dBFS after compression
BPM_START, BPM_END = 58.0, 64.0
HRV = 0.030                       # interval jitter. Real hearts wander.

# The drone is off. Just the pulse, in a room. Set this above 0 to bring the
# low tone back — 0.42 was the level it shipped at.
DRONE_LEVEL = 0.0
CARD_TONE_LEVEL = 0.18            # the one struck note under the end card

KEYS = {
    'dark':  dict(root=55.00, fifth=82.41, air=220.00),    # A1 / E2 / A3
    'light': dict(root=65.41, fifth=98.00, air=261.63),    # C2 / G2 / C4
}


def _t(n):
    return np.arange(n, dtype=np.float64) / SR


def fft_convolve(x, ir):
    """
    FFT convolution. Direct np.convolve against a long kernel — a 1.4 s reverb
    tail, or the multi-second envelope kernels the compressor needs — is tens
    of billions of operations and takes minutes. This is the same result in
    well under a second.
    """
    n = 1 << int(np.ceil(np.log2(x.size + ir.size - 1)))
    return np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(ir, n), n)[:x.size]


def lowpass(x, cutoff):
    """One-pole, as an exponential-decay convolution kernel."""
    a = math.exp(-2 * math.pi * cutoff / SR)
    k = min(x.size, int(-6 / math.log(max(a, 1e-9))) + 1)
    kernel = (1 - a) * a ** np.arange(k)
    if k > 1024:
        return fft_convolve(x, kernel)
    return np.convolve(x, kernel)[:x.size]


def noise(dur, seed=0):
    return np.random.default_rng(seed).standard_normal(max(1, int(dur * SR)))


def reverb(x, decay=1.4, mix=0.16, seed=99):
    """Short convolution tail. Puts the pulse in a chest rather than a vacuum."""
    n = int(decay * SR)
    ir = lowpass(noise(decay, seed) * np.exp(-_t(n) * (5.0 / decay)), 2600)
    ir[0] = 1.0
    wet = fft_convolve(x, ir / np.abs(ir).sum() * 6.0)
    return x * (1 - mix) + wet * mix


def _add(buf, sig, at):
    i = int(at * SR)
    if i >= buf.size or i < 0:
        return
    j = min(buf.size, i + sig.size)
    buf[i:j] += sig[: j - i]


# ── the pulse ────────────────────────────────────────────────────────────────

def valve(dur, f0, f1, decay, level=1.0):
    """
    One valve sound: a short, damped, tonal thump with no noise tail. The
    absence of that tail is what stops it reading as a saw stroke.
    """
    n = int(dur * SR)
    t = _t(n)
    f = f0 * (f1 / f0) ** (t / max(1e-9, dur))
    x = np.sin(2 * math.pi * np.cumsum(f) / SR)
    x += 0.18 * np.sin(2 * math.pi * np.cumsum(f * 2.03) / SR)   # a little body
    env = (1 - np.exp(-t * 260)) * np.exp(-t * decay)
    return x * env * level


def heartbeat(strength=1.0, seed=0):
    """S1 then S2, 300 ms apart — one cardiac cycle."""
    s1 = valve(0.130, 46, 33, 26.0, 0.95)
    s2 = valve(0.095, 62, 46, 34.0, 0.55)
    gap = int(0.300 * SR)
    out = np.zeros(gap + s2.size)
    out[:s1.size] += s1
    out[gap:gap + s2.size] += s2
    return out * strength


def beat_times(total, seed=11):
    """Cycle onsets, rate drifting up, each interval jittered by a random walk."""
    rng = np.random.default_rng(seed)
    times, t, walk = [], 0.0, 0.0
    while t < total:
        times.append(t)
        bpm = BPM_START + (BPM_END - BPM_START) * min(1.0, t / max(1e-9, total))
        walk = 0.72 * walk + 0.28 * rng.normal()
        t += (60.0 / bpm) * (1.0 + HRV * walk)
    return times


# ── the bed ──────────────────────────────────────────────────────────────────

def drone(dur, key, level=DRONE_LEVEL):
    """Pure tone only. No noise layer — that was half the rowing machine."""
    n = int(dur * SR)
    t = _t(n)
    x = np.zeros(n)
    for f, a, det in ((key['root'], 0.9, 0.08), (key['root'] * 2, 0.30, 0.12),
                      (key['fifth'], 0.36, 0.10)):
        x += a * np.sin(2 * math.pi * (f + np.sin(2 * math.pi * 0.037 * t + f) * det) * t)
    air = key['air']
    x += 0.16 * np.sin(2 * math.pi * air * t) * (
        0.4 + 0.6 * (0.5 + 0.5 * np.sin(2 * math.pi * 0.03 * t)))
    x /= max(1e-9, np.abs(x).max())
    swell = 0.78 + 0.22 * (0.5 + 0.5 * np.sin(2 * math.pi * 0.055 * t - 1.0))
    return lowpass(x * swell, 380) * level


def struck(freq, dur=2.2, level=0.26):
    """A soft, slightly inharmonic note under the end card."""
    n = int(dur * SR)
    t = _t(n)
    x = (np.sin(2 * math.pi * freq * t) * 0.6
         + np.sin(2 * math.pi * freq * 2.01 * t) * 0.2
         + np.sin(2 * math.pi * freq * 3.02 * t) * 0.07)
    return lowpass(x * np.exp(-t * 1.7), 2400) * level


# ── mastering ────────────────────────────────────────────────────────────────

def compress(x, thresh=0.12, ratio=3.5, attack=0.012, release=0.28):
    """
    A sparse pulse holds almost all its energy in short transients, so peak
    normalising alone leaves it faint. Pull the transients down, then the
    make-up gain lifts everything underneath.
    """
    fast = lowpass(np.abs(x), 1.0 / (2 * math.pi * attack))
    slow = lowpass(np.abs(x), 1.0 / (2 * math.pi * release))
    env = np.maximum(fast, slow)
    gain = np.ones_like(env)
    over = env > thresh
    gain[over] = (thresh / np.maximum(env[over], 1e-9)) ** (1 - 1 / ratio)
    return x * lowpass(gain, 12.0)                 # smoothed: no pumping


# ── arrangement ──────────────────────────────────────────────────────────────

def render_track(cuts, total, card_at=None, mood='dark'):
    """
    cuts    — segment start times in seconds (index 0 is the hook)
    total   — duration in seconds
    card_at — when the end card starts; the pulse eases there
    mood    — 'dark' or 'light'
    """
    key = KEYS.get(mood, KEYS['dark'])
    n = int(total * SR)
    card_at = card_at if card_at is not None else total

    x = drone(total, key, DRONE_LEVEL) if DRONE_LEVEL > 0 else np.zeros(n)

    hook_end = cuts[1] if len(cuts) > 1 else 3.0
    for i, b in enumerate(beat_times(total)):
        if b > total - 0.6:
            break
        if b < hook_end:
            s = 0.55                               # under the hook: felt, not heard
        elif b >= card_at:
            s = 0.50
        else:
            s = 1.0
        s *= 1 + 0.05 * np.random.default_rng(i).normal()
        _add(x, heartbeat(s * 0.95, seed=i), b)

    _add(x, struck(key['air'], level=CARD_TONE_LEVEL), card_at)

    x = reverb(x)
    fi = int(0.6 * SR)
    x[:fi] *= np.linspace(0, 1, fi) ** 1.3
    fo = int(min(1.6, total * 0.22) * SR)
    x[-fo:] *= np.linspace(1, 0, fo) ** 0.85

    x = compress(x)
    x = np.tanh(x * 1.35) / 1.35
    peak = np.abs(x).max()
    if peak > 0:
        x *= PEAK / peak

    return np.stack([x, np.roll(x, int(0.004 * SR)) * 0.98], axis=1)


# ── cut alignment ────────────────────────────────────────────────────────────

def snap_to_beats(durations, total_hint=None):
    """
    Snap segment boundaries onto actual cycle onsets, so every cut lands on a
    beat. Because the pulse carries HRV, this is not grid quantisation — the
    edit inherits the same wandering timing as the audio.
    """
    beats = beat_times(sum(durations) * 1.35)
    out, prev_t, acc = [], 0.0, 0.0
    for d in durations:
        target = acc + d
        cand = [b for b in beats if b > prev_t + 1.6]
        if not cand:
            out.append(d); acc += d; prev_t = acc; continue
        b = min(cand, key=lambda v: abs(v - target))
        out.append(round(b - prev_t, 4))
        prev_t = acc = b
    return out


def quantise(durations, unit=None, minimum=None):
    return snap_to_beats(durations)


# ── licensed drop-in ─────────────────────────────────────────────────────────

def licensed_track(reel_id, music_dir):
    """
    Prefer a real track if one is provided. Put an audio file at
    build/music/<reel-id>.<ext>, or build/music/default.<ext> for all of them,
    and it is used instead of the generated pulse — trimmed, faded and
    loudness-matched by build_reels.py.

    Only music you hold commercial rights to: Meta Sound Collection, Uppbeat,
    Epidemic Sound, Artlist. Instagram treats company posts as commercial, so
    "free for personal use" is not enough.
    """
    if not music_dir or not os.path.isdir(music_dir):
        return None
    for stem in (reel_id, 'default'):
        for ext in ('wav', 'mp3', 'm4a', 'aac', 'flac', 'ogg'):
            p = os.path.join(music_dir, f'{stem}.{ext}')
            if os.path.exists(p):
                return p
    return None


def write_wav(path, stereo):
    pcm = (np.clip(stereo, -1.0, 1.0) * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == '__main__':
    import sys
    if '--demo' in sys.argv:
        mood = 'light' if 'light' in sys.argv else 'dark'
        segs = snap_to_beats([3.0, 3.0, 3.0, 3.0, 3.6, 2.4])
        cuts, acc = [], 0.0
        for d in segs:
            cuts.append(acc); acc += d
        write_wav(f'demo-{mood}.wav', render_track(cuts, acc, cuts[-1], mood))
        print(f'wrote demo-{mood}.wav — {acc:.1f}s, {BPM_START:.0f}→{BPM_END:.0f} bpm, '
              f'{HRV*100:.1f}% HRV, cuts on the pulse')
