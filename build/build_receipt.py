#!/usr/bin/env python3
"""
My Body — the receipt.

Renders the campaign's one artefact: a single frame that states what three
datasets say across one protocol window, and nothing else. No app chrome, no
dashboard, no logo lockup. A thing somebody screenshots and pastes into a group
chat.

    python3 build_receipt.py            # writes out/receipt.mp4 and out/receipt.png

Why this exists
---------------
Six Reels built from app captures produced ~1,100 Facebook views and zero
shares, zero saves, zero follows (5-7 Aug 2026). The build pipeline was not the
problem — the thing it was building was. `CLAUDE.md` already predicted it:
screens get visited, artefacts get sent. Every one of those Reels was a screen.

So this renders an artefact:

  * one frame, readable in full at a glance, sized for a phone screenshot
  * the protocol-start marker is the spine, not a detail on a chart
  * one line goes the WRONG WAY, on purpose — see HONEST_LINE below

Design rules this file is bound by (docs/product/Design Ruleset - Purple Cow)
----------------------------------------------------------------------------
  * No health claim, no diagnosis, no advice. Numbers are placed NEXT TO the
    protocol window, never attributed to it. There is no "because", no "caused",
    no compound named against an outcome.
  * No dosage-calculation language anywhere (App Review guideline 1.4.2).
  * No exclamation marks.
  * No price. Ever. Not in a hook, not on the card.
  * Sample data must be labelled as sample data, unmissably, in the frame
    itself — not in a caption that travels separately from the image. A
    screenshot must carry its own disclaimer or the artefact lies when shared.

Requires: Pillow, ffmpeg, and the Geist family
(`npm --prefix /tmp install geist`).
"""
import os, sys, subprocess, tempfile

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_music                                        # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get('OUT_DIR') or os.path.join(HERE, 'out')
NO_AUDIO = os.environ.get('NO_AUDIO') == '1'
MUSIC_DIR = os.environ.get('MUSIC_DIR') or os.path.join(HERE, 'music')

W, H, FPS = 1080, 1920, 30

BG      = (12, 12, 14)
INK     = (250, 250, 249)
MUTED   = (132, 132, 142)
ACCENT  = (139, 133, 240)
WARN    = (226, 155, 106)      # the line that goes the wrong way
RULE    = (44, 44, 50)

MONO = '/tmp/node_modules/geist/dist/fonts/geist-mono/GeistMono-{}.ttf'
SANS = '/tmp/node_modules/geist/dist/fonts/geist-sans/Geist-{}.ttf'
DEJA = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'


def font(family, weight, size):
    p = (MONO if family == 'mono' else SANS).format(weight)
    if not os.path.exists(p):
        p = DEJA
    return ImageFont.truetype(p, size)


# ── typography safety ────────────────────────────────────────────────────────
# The first cut of this file centred the hook without wrapping it, and the line
# rendered 1138px wide on a 1080px canvas — chopped off at both edges. Nothing
# in the build failed, because nothing was checking. So: everything that draws
# text goes through fit_lines(), and verify_widths() re-measures the finished
# layout and raises rather than writing a broken frame.

SAFE = 96                       # left/right margin; also the layout gutter
MAXW = W - SAFE * 2             # 888px of usable width


def _wrap(draw, text, f, maxw):
    out = []
    for para in text.split('\n'):
        if not para.strip():
            out.append('')
            continue
        cur = []
        for word in para.split():
            trial = ' '.join(cur + [word])
            if cur and draw.textlength(trial, font=f) > maxw:
                out.append(' '.join(cur)); cur = [word]
            else:
                cur.append(word)
        if cur:
            out.append(' '.join(cur))
    return out


def fit_lines(draw, text, family, weight, size, maxw=MAXW, min_size=44):
    """Wrap to maxw, shrinking the point size until every line fits. Returns
    (lines, font). Guarantees no line is wider than maxw."""
    s = size
    while s >= min_size:
        f = font(family, weight, s)
        lines = _wrap(draw, text, f, maxw)
        if all(draw.textlength(ln, font=f) <= maxw for ln in lines):
            return lines, f
        s -= 4
    f = font(family, weight, min_size)
    return _wrap(draw, text, f, maxw), f


def verify_widths(img, checks):
    """checks: list of (label, width). Raises if anything overflows the safe
    area. Called on every render so a chopped frame can never be written."""
    bad = [(lb, w) for lb, w in checks if w > MAXW]
    if bad:
        detail = '; '.join(f'{lb} = {w:.0f}px' for lb, w in bad)
        raise ValueError(
            f'text exceeds the {MAXW}px safe width and would be chopped: {detail}')


# ── the content ──────────────────────────────────────────────────────────────
#
# SAMPLE FIGURES. Tony chose sample over real user data deliberately, to avoid
# putting anyone's health record into marketing. That choice is only safe if the
# frame says so plainly — hence SAMPLE_BANNER, which is rendered inside the
# image and cannot be separated from it.

SAMPLE_BANNER = 'SAMPLE DATA — NOT A REAL USER'

WINDOW = '16-WEEK WINDOW'
PROTOCOL_FROM = '3 MAR'
PROTOCOL_TO = '23 JUN'

# label, before, after, delta, direction   (+1 improved, -1 worsened, 0 neutral)
ROWS = [
    ('WEIGHT',        '88.4 kg',  '81.1 kg',  '-7.3 kg', +1),
    ('SQUAT  1RM',    '120 kg',   '137 kg',   '+14%',    +1),
    ('PROTEIN / DAY', '118 g',    '147 g',    '+29 g',   +1),
    ('SESSIONS / WK', '2.1',      '3.4',      '+1.3',    +1),
    ('SLEEP',         '7.4 h',    '6.9 h',    '-0.5 h',  -1),   # HONEST_LINE
]

FOOTER = 'Three apps. One account. One timeline.'
DISCLAIM = '18+. Personal tracking, not medical advice.'

# The hook's job is to buy two seconds and give a reason to stay for the last
# row. "One of these numbers went the wrong way" does both, and it points at the
# amber sleep line — so the payoff is the honest bit rather than a tease. It is
# also not a claim about competitors, which keeps it inside "show, do not claim".
HOOK = 'One of these numbers\nwent the wrong way.'


def receipt_frame(reveal=99):
    """Render the artefact. `reveal` is how many body rows are visible, so the
    same function serves both the still and the animated build."""
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)

    f_eyebrow = font('mono', 'Medium', 30)
    f_window = font('mono', 'Bold', 62)
    f_label = font('mono', 'Medium', 34)
    f_val = font('mono', 'Medium', 40)
    f_delta = font('mono', 'Bold', 44)
    f_small = font('mono', 'Regular', 27)
    f_foot = font('sans', 'Medium', 36)

    L, R = 96, W - 96
    y = 250

    # sample banner — inside the frame, always
    bw = d.textlength(SAMPLE_BANNER, font=f_small)
    d.rounded_rectangle([L - 10, y - 14, L + bw + 26, y + 42], radius=10,
                        outline=WARN, width=2)
    d.text((L + 8, y), SAMPLE_BANNER, font=f_small, fill=WARN)
    y += 108

    d.text((L, y), WINDOW, font=f_window, fill=INK)
    y += 96

    # ── the protocol marker: the spine of the whole thing ────────────────────
    # This is the element that passed all five Purple Cow tests. It is drawn
    # first and given room, because it is the reason the numbers mean anything.
    d.text((L, y), 'PROTOCOL RUNNING', font=f_eyebrow, fill=ACCENT)
    y += 46
    band_top = y
    d.rectangle([L, y, R, y + 78], fill=(26, 24, 46))
    for x in range(L, R, 3):                       # dashed start marker
        pass
    dash_y0, dash_y1 = band_top - 8, band_top + 86
    for yy in range(dash_y0, dash_y1, 14):
        d.line([(L, yy), (L, min(yy + 8, dash_y1))], fill=ACCENT, width=4)
    d.text((L + 28, y + 20), f'{PROTOCOL_FROM}   →   {PROTOCOL_TO}',
           font=f_val, fill=INK)
    y += 78 + 78

    # ── the rows ─────────────────────────────────────────────────────────────
    for i, (label, before, after, delta, direction) in enumerate(ROWS):
        if i >= reveal:
            break
        d.line([(L, y - 26), (R, y - 26)], fill=RULE, width=2)
        d.text((L, y), label, font=f_label, fill=MUTED)
        line = f'{before}  →  {after}'
        d.text((L, y + 46), line, font=f_val, fill=INK)
        colour = WARN if direction < 0 else INK
        dw = d.textlength(delta, font=f_delta)
        d.text((R - dw, y + 30), delta, font=f_delta, fill=colour)
        y += 148

    if reveal >= len(ROWS):
        y += 26
        d.line([(L, y), (R, y)], fill=RULE, width=2)
        y += 54
        d.text((L, y), FOOTER, font=f_foot, fill=INK)
        y += 62
        d.text((L, y), DISCLAIM, font=f_small, fill=MUTED)

    # Nothing leaves this function unmeasured.
    checks = [
        ('sample banner', d.textlength(SAMPLE_BANNER, font=f_small) + 36),
        ('window title', d.textlength(WINDOW, font=f_window)),
        ('protocol dates',
         d.textlength(f'{PROTOCOL_FROM}   →   {PROTOCOL_TO}', font=f_val) + 28),
        ('footer', d.textlength(FOOTER, font=f_foot)),
        ('disclaimer', d.textlength(DISCLAIM, font=f_small)),
    ]
    for label, before, after, delta, _ in ROWS:
        value = d.textlength(f'{before}  →  {after}', font=f_val)
        checks.append((f'row "{label}" value', value))
        # value and delta share the line — they must not collide either
        checks.append((f'row "{label}" value+delta',
                       value + d.textlength(delta, font=f_delta) + 40))
    verify_widths(img, checks)

    return img


def hook_frame():
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    # HOOK keeps its explicit line breaks — fit_lines only re-wraps a line that
    # is genuinely too wide, so the intended phrasing survives.
    lines, f = fit_lines(d, HOOK, 'sans', 'SemiBold', 84)
    verify_widths(img, [(f'hook line {i}', d.textlength(ln, font=f))
                        for i, ln in enumerate(lines)])
    lh = int(f.size * 1.2)
    y = (H - lh * len(lines)) // 2
    for ln in lines:
        w = d.textlength(ln, font=f)
        d.text(((W - w) / 2, y), ln, font=f, fill=INK)
        y += lh
    return img


def build():
    os.makedirs(OUT, exist_ok=True)

    still = receipt_frame()
    png = os.path.join(OUT, 'receipt.png')
    still.save(png)

    # Timeline. The rows arrive one at a time — that is a retention mechanic
    # made of typography rather than a gimmick, and it gives the viewer a
    # reason to still be there for the last line, which is the honest one.
    HOOK_DUR, ROW_DUR, HOLD = 2.0, 0.9, 4.6
    frames = []
    frames += [('hook', HOOK_DUR)]
    for i in range(1, len(ROWS) + 1):
        frames.append((i, ROW_DUR))
    frames.append((len(ROWS), HOLD))

    total = sum(d for _, d in frames)
    cuts, acc = [], 0.0
    for _, d in frames:
        cuts.append(acc); acc += d

    wav = None
    if not NO_AUDIO:
        licensed = build_music.licensed_track('receipt', MUSIC_DIR)
        if licensed:
            wav = licensed
        else:
            fd, wav = tempfile.mkstemp(suffix='.wav', prefix='receipt-')
            os.close(fd)
            build_music.write_wav(wav, build_music.render_track(
                cuts=cuts, total=total, card_at=cuts[-1], mood='dark'))

    dest = os.path.join(OUT, 'receipt.mp4')
    cmd = ['ffmpeg', '-y', '-loglevel', 'error',
           '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
           '-r', str(FPS), '-i', '-']
    if wav:
        cmd += ['-i', wav]
    cmd += ['-c:v', 'libx264', '-preset', 'medium', '-crf', '19',
            '-pix_fmt', 'yuv420p']
    if wav:
        cmd += ['-c:a', 'aac', '-b:a', '160k', '-ar', '44100', '-shortest']
    cmd += ['-movflags', '+faststart', dest]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    cache = {}
    for kind, dur in frames:
        if kind not in cache:
            cache[kind] = (hook_frame() if kind == 'hook'
                           else receipt_frame(reveal=kind))
        buf = cache[kind].tobytes()
        for _ in range(int(dur * FPS)):
            ff.stdin.write(buf)
    ff.stdin.close(); ff.wait()

    if wav and wav.startswith(tempfile.gettempdir()):
        try: os.remove(wav)
        except OSError: pass

    print(f'  receipt.png   {os.path.getsize(png)/1e3:6.1f} KB')
    print(f'  receipt.mp4   {total:5.1f}s  {os.path.getsize(dest)/1e6:5.2f} MB')
    return dest, png


if __name__ == '__main__':
    print(f'Building the receipt at {W}x{H}\n')
    build()
    print(f'\nDone -> {OUT}')
