#!/usr/bin/env python3
"""
My Body — Reel builder.

Turns real app captures (from the screenshot rig) plus the campaign hook copy
into finished 1080x1920 MP4 Reels, brand-typed and ready to publish.

  python3 build_reels.py               # build every reel in reels.json
  python3 build_reels.py d01 d04       # build only matching ids
  python3 build_reels.py --list

Design notes
------------
* Motion is a slow vertical drift of a pre-scaled capture, not a per-frame
  resize. It reads as a deliberate camera move and costs almost nothing, so a
  full 18s reel builds in seconds and the whole campaign builds in CI.
* Frames are piped straight to ffmpeg as raw RGB. No intermediate PNGs.
* Every text layer is rendered once per segment and alpha-composited, so the
  per-frame cost is a crop, two pastes and a rectangle.

Requires: Pillow, ffmpeg on PATH, and the Geist font family
(`npm --prefix /tmp install geist`). Falls back to DejaVu if Geist is absent,
which is fine for a smoke test but is not the brand face — do not publish
fallback output.
"""
import json, os, subprocess, sys, math, tempfile

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_music                                   # noqa: E402

NO_AUDIO = os.environ.get('NO_AUDIO') == '1'         # silent build, for testing
# Drop a licensed track in here as <reel-id>.mp3 or default.mp3 and it is used
# instead of the generated arrangement. See AUDIO.md.
MUSIC_DIR = os.environ.get('MUSIC_DIR') or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'music')
# Snap segment durations to half-bars so every cut lands on the beat.
BEAT_ALIGN = os.environ.get('BEAT_ALIGN', '1') == '1'

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.environ.get('RAW_DIR') or os.path.join(HERE, 'raw')
OUT = os.environ.get('OUT_DIR') or os.path.join(HERE, 'out')
# End cards. In the project tree they live under marketing/assets; in the
# standalone poster repo the whole build is self-contained, so CARDS_DIR is set.
CARDS = os.environ.get('CARDS_DIR') or os.path.abspath(
    os.path.join(HERE, '..', '..', 'marketing', 'assets', 'Social Assets', 'pro-launch-v2'))
SPEC = os.environ.get('REELS_SPEC') or os.path.join(HERE, 'reels.json')

W, H, FPS = 1080, 1920, 30

THEMES = {
    'dark':  dict(bg=(23, 23, 26), ink=(250, 250, 249), muted=(168, 168, 176), accent=(139, 133, 240)),
    'light': dict(bg=(250, 250, 249), ink=(23, 23, 26), muted=(92, 92, 99), accent=(79, 70, 229)),
}

GEIST = '/tmp/node_modules/geist/dist/fonts/geist-sans/Geist-{}.ttf'
DEJAVU = {'SemiBold': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
          'Medium': '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
          'Regular': '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'}
USING_FALLBACK = not os.path.exists(GEIST.format('SemiBold'))


def font(weight, size):
    path = GEIST.format(weight)
    if not os.path.exists(path):
        path = DEJAVU.get(weight, DEJAVU['Regular'])
    return ImageFont.truetype(path, size)


# ── text helpers ─────────────────────────────────────────────────────────────

def wrap(draw, text, f, maxw):
    lines, cur = [], []
    for word in text.split():
        trial = ' '.join(cur + [word])
        if cur and draw.textlength(trial, font=f) > maxw:
            lines.append(' '.join(cur)); cur = [word]
        else:
            cur.append(word)
    if cur:
        lines.append(' '.join(cur))
    return lines


def text_layer(text, weight, size, colour, maxw, align_y, theme, scrim=None,
               tracking=0.0, line_gap=1.16):
    """Render a transparent 1080x1920 layer with wrapped text and an optional
    gradient scrim behind it, so type stays legible over any screenshot."""
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = font(weight, size)

    paras = text.split('\n')
    lines = []
    for p in paras:
        lines += wrap(d, p, f, maxw) if p.strip() else ['']
    lh = int(size * line_gap)
    block_h = lh * len(lines)

    if align_y == 'top':
        y0 = 250
    elif align_y == 'bottom':
        y0 = H - 420 - block_h
    else:
        y0 = (H - block_h) // 2

    if scrim:
        # vertical gradient scrim, strongest at the text block
        top = max(0, y0 - 190)
        bot = min(H, y0 + block_h + 190)
        grad = Image.new('L', (1, bot - top), 0)
        gp = grad.load()
        n = bot - top
        for i in range(n):
            t = i / max(1, n - 1)
            # ease in and out so the scrim has no hard edges
            a = math.sin(math.pi * t) ** 0.7
            gp[0, i] = int(255 * a * scrim)
        mask = grad.resize((W, bot - top))
        block = Image.new('RGBA', (W, bot - top), THEMES[theme]['bg'] + (255,))
        block.putalpha(mask)
        layer.alpha_composite(block, (0, top))

    y = y0
    for line in lines:
        if tracking:
            wdt = sum(d.textlength(c, font=f) for c in line) + tracking * max(0, len(line) - 1)
            x = (W - wdt) / 2
            for c in line:
                d.text((x, y), c, font=f, fill=colour + (255,))
                x += d.textlength(c, font=f) + tracking
        else:
            wdt = d.textlength(line, font=f)
            d.text(((W - wdt) / 2, y), line, font=f, fill=colour + (255,))
        y += lh
    return layer


# ── device layer ─────────────────────────────────────────────────────────────

def device_layer(path, target_w=880, radius=54):
    """Pre-scale a raw capture to the on-canvas width and round its corners."""
    img = Image.open(path).convert('RGB')
    scale = target_w / img.width
    img = img.resize((target_w, int(img.height * scale)), Image.LANCZOS)

    mask = Image.new('L', img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.width - 1, img.height - 1],
                                           radius=radius, fill=255)
    out = Image.new('RGBA', img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def fade(layer, alpha):
    if alpha >= 0.999:
        return layer
    if alpha <= 0.001:
        return None
    a = layer.getchannel('A').point(lambda v: int(v * alpha))
    out = layer.copy()
    out.putalpha(a)
    return out


# ── build ────────────────────────────────────────────────────────────────────

def build(reel):
    theme = THEMES[reel.get('theme', 'dark')]
    tname = reel.get('theme', 'dark')
    bg = Image.new('RGB', (W, H), theme['bg'])

    segments = []

    # 1. hook — the first three seconds, which carry most of the completion rate
    hook_src = reel['beats'][0]['src']
    segments.append(dict(
        kind='hook',
        dev=device_layer(os.path.join(RAW, hook_src)),
        text=text_layer(reel['hook'], 'SemiBold', 76, theme['ink'], 900, 'center',
                        tname, scrim=0.94),
        dur=reel.get('hookDur', 3.0),
    ))

    # 2. beats
    for b in reel['beats']:
        segments.append(dict(
            kind='beat',
            dev=device_layer(os.path.join(RAW, b['src'])),
            text=(text_layer(b['text'], 'Medium', 52, theme['ink'], 880, 'bottom',
                             tname, scrim=0.88) if b.get('text') else None),
            dur=b.get('dur', 3.4),
        ))

    # 3. end card
    card_path = os.path.join(CARDS, reel['endCard'])
    card = Image.open(card_path).convert('RGB')
    card = card.resize((W, int(card.height * W / card.width)), Image.LANCZOS)
    card_canvas = Image.new('RGB', (W, H), theme['bg'])
    card_canvas.paste(card, (0, (H - card.height) // 2))
    segments.append(dict(kind='card', flat=card_canvas, dur=reel.get('cardDur', 2.4)))

    total = sum(s['dur'] for s in segments)
    total_frames = int(total * FPS)

    XFADE = 0.35          # seconds of crossfade between segments
    DRIFT = 46            # pixels of vertical camera drift per segment

    # Snap every segment to a half-bar so the cuts land on the beat. This is
    # most of what separates a considered product film from a slideshow.
    if BEAT_ALIGN and not NO_AUDIO:
        snapped = build_music.quantise([s['dur'] for s in segments])
        for s, d in zip(segments, snapped):
            s['dur'] = d

    # segment start times
    starts, acc = [], 0.0
    for s in segments:
        starts.append(acc); acc += s['dur']
    total = acc
    total_frames = int(total * FPS)

    dest = os.path.join(OUT, reel['id'] + '.mp4')
    os.makedirs(OUT, exist_ok=True)

    # Audio. A licensed track wins if one has been dropped in; otherwise we
    # generate an original arrangement locked to this reel's own cuts. Either
    # way there is always an audio stream — a silent Reel reads as an advert
    # and gives the audio page nothing to point at.
    wav = licensed = None
    if not NO_AUDIO:
        licensed = build_music.licensed_track(reel['id'], MUSIC_DIR)
        if not licensed:
            # scratch file — the arrangement is regenerated on every build
            fd, wav = tempfile.mkstemp(suffix='.wav', prefix=reel['id'] + '-')
            os.close(fd)
            build_music.write_wav(wav, build_music.render_track(
                cuts=starts, total=total, card_at=starts[-1],
                mood=reel.get('theme', 'dark')))

    src = licensed or wav
    cmd = ['ffmpeg', '-y', '-loglevel', 'error',
           '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-']
    if src:
        cmd += ['-i', src]
    cmd += ['-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p']
    if src:
        cmd += ['-c:a', 'aac', '-b:a', '160k', '-ar', '44100']
        if licensed:
            # trim to length, fade the tail, and pull a hot master down to
            # roughly where the generated track sits
            cmd += ['-af', f'atrim=0:{total:.2f},afade=t=in:st=0:d=0.4,'
                            f'afade=t=out:st={max(0, total - 1.4):.2f}:d=1.4,'
                            f'loudnorm=I=-16:TP=-1.5:LRA=11']
        cmd += ['-shortest']
    cmd += ['-movflags', '+faststart', dest]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    for fi in range(total_frames):
        t = fi / FPS
        frame = bg.copy()

        for si, s in enumerate(segments):
            s0, s1 = starts[si], starts[si] + s['dur']
            if t < s0 - XFADE or t >= s1:
                continue
            # alpha: fade in over XFADE at the start of every segment after the first
            if si > 0 and t < s0:
                a = (t - (s0 - XFADE)) / XFADE
            elif si > 0 and t < s0 + XFADE:
                a = min(1.0, (t - s0) / XFADE + 0.999)
            else:
                a = 1.0
            a = max(0.0, min(1.0, a))

            local = (t - s0) / s['dur']

            if s['kind'] == 'card':
                layer = s['flat'].convert('RGBA')
                lf = fade(layer, a)
                if lf: frame.paste(lf, (0, 0), lf)
                continue

            dev = s['dev']
            # drift downward slowly; hook sits slightly lower and rises
            if s['kind'] == 'hook':
                y = 250 - int(DRIFT * local)
            else:
                y = 168 + int(DRIFT * (local - 0.5))
            x = (W - dev.width) // 2

            df = fade(dev, a)
            if df: frame.paste(df, (x, y), df)

            if s['text'] is not None:
                # text arrives just after the screen settles
                ta = a * min(1.0, max(0.0, (local * s['dur']) / 0.45))
                tf = fade(s['text'], ta)
                if tf: frame.paste(tf, (0, 0), tf)

        # progress hairline — small polish detail, reads as "there is an end"
        d = ImageDraw.Draw(frame)
        d.rectangle([0, H - 8, int(W * (fi / max(1, total_frames - 1))), H - 4],
                    fill=theme['accent'])

        ff.stdin.write(frame.tobytes())

    ff.stdin.close()
    ff.wait()
    if wav and os.path.exists(wav):
        try: os.remove(wav)
        except OSError: pass
    size = os.path.getsize(dest) / 1e6
    print(f"  {reel['id']:28} {total:5.1f}s  {size:5.2f} MB  -> out/{reel['id']}.mp4")
    return dest


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    reels = json.load(open(SPEC, encoding='utf-8'))['reels']

    if '--list' in sys.argv:
        for r in reels:
            print(f"{r['id']:28} gate={r.get('requires', 'none')}")
        return

    if USING_FALLBACK:
        print('WARNING: Geist not found, falling back to DejaVu. Run '
              '`npm --prefix /tmp install geist` before publishing.\n')

    todo = [r for r in reels if not args or any(a in r['id'] for a in args)]
    print(f'Building {len(todo)} reel(s) at {W}x{H} {FPS}fps\n')
    for r in todo:
        build(r)
    print(f'\nDone. {len(todo)} file(s) in {OUT}')


if __name__ == '__main__':
    main()
