# optimise. rebrand — social asset renderer (1080x1350), pure PIL
from PIL import Image, ImageDraw, ImageFont
import os

FD = '/tmp/node_modules/geist/dist/fonts/geist-sans'
OUT = '/tmp/render'
W, H = 1080, 1350
PX, PY = 84, 72

def F(weight, size):
    return ImageFont.truetype(f'{FD}/Geist-{weight}.ttf', size)

THEMES = {
    'light': dict(bg='#FAFAF9', ink='#17171A', muted='#5C5C63', accent='#4F46E5', count='#8A8A90'),
    'dark':  dict(bg='#17171A', ink='#FAFAF9', muted='#A8A8B0', accent='#8B85F0', count='#8A8A90'),
}

def tw(draw, text, font, tracking=0):
    if not text: return 0
    if tracking == 0:
        return draw.textlength(text, font=font)
    return sum(draw.textlength(ch, font=font) for ch in text) + tracking * (len(text) - 1)

def draw_tracked(draw, x, y, text, font, fill, tracking=0):
    if tracking == 0:
        draw.text((x, y), text, font=font, fill=fill)
        return
    cx = x
    for ch in text:
        draw.text((cx, y), ch, font=font, fill=fill)
        cx += draw.textlength(ch, font=font) + tracking

def word_w(draw, word, font, tracking):
    return sum(tw(draw, frag, font, tracking) for frag, _ in word) + tracking * (len(word) - 1)

def rich_wrap(draw, words, font, tracking, maxw):
    lines, cur, curw = [], [], 0
    spw = draw.textlength(' ', font=font) + tracking
    for word in words:
        ww = word_w(draw, word, font, tracking)
        add = ww if not cur else spw + ww
        if cur and curw + add > maxw:
            lines.append(cur); cur, curw = [word], ww
        else:
            cur.append(word); curw += add
    if cur: lines.append(cur)
    return lines

def rich_height(lines, lh): return len(lines) * lh

def draw_rich(draw, lines, font, tracking, cy, lh, colors, align_cx=W//2):
    y = cy
    spw = draw.textlength(' ', font=font) + tracking
    for line in lines:
        total = sum(word_w(draw, w, font, tracking) for w in line) + spw * (len(line) - 1)
        x = align_cx - total / 2
        for word in line:
            for frag, ck in word:
                draw_tracked(draw, x, y, frag, font, colors[ck], tracking)
                x += tw(draw, frag, font, tracking) + tracking
            x += spw - tracking
        y += lh

def ring(size, ring_color, dot_color):
    S = 4
    img = Image.new('RGBA', (size*S, size*S), (0,0,0,0))
    d = ImageDraw.Draw(img)
    c = size*S/2
    r = 33/100 * size * S
    stroke = int(9/100 * size * S)
    d.ellipse([c-r, c-r, c+r, c+r], outline=ring_color, width=stroke)
    rd = 10/100 * size * S
    d.ellipse([c-rd, c-rd, c+rd, c+rd], fill=dot_color)
    return img.resize((size, size), Image.LANCZOS)

def parse_rich(spec):
    """spec -> list of words; each word = list of (frag, colorkey), split on spaces across segments"""
    words, cur = [], []
    for text, ck in spec:
        parts = text.split(' ')
        for i, p in enumerate(parts):
            if i > 0 and cur:
                words.append(cur); cur = []
            if p: cur.append((p, ck))
    if cur: words.append(cur)
    return words

def render(file, theme, count, blocks):
    T = THEMES[theme]
    colors = {'ink': T['ink'], 'accent': T['accent'], 'muted': T['muted']}
    img = Image.new('RGB', (W, H), T['bg'])
    d = ImageDraw.Draw(img)

    # header
    wm_f = F('Medium', 46); dot_f = F('SemiBold', 46)
    wm_track = -1.5
    wx = PX
    wmw = tw(d, 'optimise', wm_f, wm_track)
    draw_tracked(d, wx, PY, 'optimise', wm_f, T['ink'], wm_track)
    d.text((wx + wmw + 2, PY), '.', font=dot_f, fill=T['accent'])
    if count:
        cf = F('Medium', 26)
        cw = tw(d, count, cf, 4)
        draw_tracked(d, W - PX - cw, PY + 14, count, cf, T['count'], 4)

    # footer
    fr_y = H - PY - 76
    d.rounded_rectangle([W/2-32, fr_y, W/2+32, fr_y+4], radius=2, fill=T['accent'])
    hf = F('Medium', 28)
    htxt = '@mybodyoptimise'
    hw = tw(d, htxt, hf, 5)
    draw_tracked(d, (W-hw)/2, fr_y + 30, htxt, hf, T['muted'], 5)

    # measure blocks
    top = PY + 90
    bottom = fr_y - 40
    GAP = 42
    measured = []
    for b in blocks:
        k = b['type']
        if k == 'eyebrow':
            f = F('SemiBold', 28); trk = b.get('tracking', 9)
            measured.append((b, f, None, 34))
        elif k == 'bignum':
            f = F('SemiBold', 150)
            measured.append((b, f, None, 150))
        elif k == 'ring':
            measured.append((b, None, None, b.get('size', 96)))
        elif k == 'h1':
            size = b.get('size', 88); f = F('SemiBold', size); trk = size * -0.035
            toks = parse_rich(b['rich'])
            lines = rich_wrap(d, toks, f, trk, b.get('maxw', 880))
            lh = int(size * 1.14)
            measured.append((b, f, lines, rich_height(lines, lh) - int(size*0.14)))
        elif k == 'body':
            f = F('Regular', 40); trk = 0
            toks = parse_rich(b['rich'])
            lines = rich_wrap(d, toks, f, trk, b.get('maxw', 760))
            lh = 58
            measured.append((b, f, lines, rich_height(lines, lh) - 10))
        elif k == 'date':
            f = F('SemiBold', 168)
            measured.append((b, f, None, 168))
        elif k == 'year':
            f = F('Regular', 44)
            measured.append((b, f, None, 50))
        elif k == 'gap':
            measured.append((b, None, None, b['h'] - GAP))
    total = sum(m[3] for m in measured) + GAP * (len(measured) - 1)
    y = top + (bottom - top - total) / 2

    for b, f, lines, hh in measured:
        k = b['type']
        if k == 'eyebrow':
            trk = b.get('tracking', 9)
            txt = b['text'].upper()
            wdt = tw(d, txt, f, trk)
            draw_tracked(d, (W-wdt)/2, y, txt, f, colors[b.get('color','accent')], trk)
        elif k == 'bignum':
            trk = -6
            wdt = tw(d, b['text'], f, trk)
            draw_tracked(d, (W-wdt)/2, y - 20, b['text'], f, T['accent'], trk)
        elif k == 'ring':
            size = b.get('size', 96)
            rg = ring(size, T['ink'], T['accent'])
            img.paste(rg, (int((W-size)/2), int(y)), rg)
        elif k == 'h1':
            size = b.get('size', 88); trk = size * -0.035
            draw_rich(d, lines, f, trk, y, int(size*1.14), colors)
        elif k == 'body':
            draw_rich(d, lines, f, 0, y, 58, {'ink': T['muted'], 'accent': T['accent'], 'muted': T['muted']})
        elif k == 'date':
            trk = -5
            wdt = tw(d, b['text'], f, trk)
            draw_tracked(d, (W-wdt)/2, y - 24, b['text'], f, T['ink'], trk)
        elif k == 'year':
            trk = 10
            wdt = tw(d, b['text'], f, trk)
            draw_tracked(d, (W-wdt)/2, y, b['text'], f, T['muted'], trk)
        y += hh + GAP

    path = os.path.join(OUT, file)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    print('rendered', file)

I, A, M = 'ink', 'accent', 'muted'
S = []

# carousel 1 — tracking mistakes
c1 = 'carousel-1-tracking-mistakes'
S.append((f'{c1}/slide-01.png', 'light', '01 / 07', [
    dict(type='eyebrow', text='Swipe  →'),
    dict(type='h1', size=94, rich=[('5 things people get ', I), ('wrong', A), (' tracking your protocol', I)]),
]))
mistakes = [
    ('01', 'Relying on memory', 'If it isn’t written down, it didn’t happen. Memory is the first thing to slip.'),
    ('02', 'No record of sites', 'Rotating injection sites only works if you know where you’ve already been.'),
    ('03', 'Ignoring how you feel', 'Energy, sleep, recovery, mood — the signals that matter most are the easiest to forget.'),
    ('04', 'Guessing the maths', 'A decimal in the wrong place changes everything. Don’t eyeball reconstitution.'),
    ('05', 'No clean history', 'Without a record, every cycle starts from zero instead of building on the last.'),
]
for i, (n, t, b) in enumerate(mistakes):
    S.append((f'{c1}/slide-0{i+2}.png', 'light', f'0{i+2} / 07', [
        dict(type='bignum', text=n),
        dict(type='h1', rich=[(t, I)]),
        dict(type='body', rich=[(b, M)]),
    ]))
S.append((f'{c1}/slide-07.png', 'dark', '07 / 07', [
    dict(type='ring'),
    dict(type='h1', size=100, rich=[('Track it properly', I), ('.', A)]),
    dict(type='body', rich=[('My Body Optimise — coming to the App Store.', M)]),
]))

# carousel 2 — feature tour
c2 = 'carousel-2-feature-tour'
S.append((f'{c2}/slide-01.png', 'light', '01 / 07', [
    dict(type='eyebrow', text='Swipe  →'),
    dict(type='h1', size=94, rich=[('Everything My Body Optimise does', I), ('.', A)]),
]))
features = [
    ('Log doses in seconds', 'Fast enough that you’ll actually keep it up. With reminders and back-dating.'),
    ('Plan protocols & cycles', 'Map your on and off phases and always know where you are.'),
    ('Reconstitution calculator', 'The right units, every time — no second-guessing the maths.'),
    ('Progress + a clear score', 'Charts, milestones and an Optimisation Score that makes sense of your data.'),
    ('Apple Health sync', 'Your protocol and your health data, together in one picture.'),
]
for i, (t, b) in enumerate(features):
    S.append((f'{c2}/slide-0{i+2}.png', 'light', f'0{i+2} / 07', [
        dict(type='ring'),
        dict(type='h1', rich=[(t, I)]),
        dict(type='body', rich=[(b, M)]),
    ]))
S.append((f'{c2}/slide-07.png', 'dark', '07 / 07', [
    dict(type='eyebrow', text='Launching 28 July'),
    dict(type='h1', size=100, rich=[('Free on the App Store', I), ('.', A)]),
    dict(type='body', rich=[('Join the waitlist — link in bio.', M)]),
]))

# cards
S.append(('card-guessing-vs-knowing.png', 'light', None, [
    dict(type='ring'),
    dict(type='h1', size=96, rich=[('Tracking is the difference between ', I), ('guessing', A), (' and knowing', I), ('.', A)]),
]))
S.append(('card-privacy.png', 'light', None, [
    dict(type='ring'),
    dict(type='h1', size=96, rich=[('Your health data should be yours', I), ('.', A)]),
    dict(type='gap', h=10),
    dict(type='eyebrow', text='Private by design', color='muted', tracking=11),
]))
S.append(('card-launch-announcement.png', 'dark', None, [
    dict(type='eyebrow', text='Launching'),
    dict(type='date', text='28 JULY'),
    dict(type='year', text='2026'),
    dict(type='gap', h=20),
    dict(type='body', rich=[('Free on the App Store.', I)]),
]))
S.append(('card-coming-soon.png', 'dark', None, [
    dict(type='eyebrow', text='Coming soon'),
    dict(type='h1', size=96, rich=[('My Body Optimise on the ', I), ('App Store', A), ('.', A)]),
    dict(type='body', rich=[('Follow along for the launch.', M)]),
]))

for file, theme, count, blocks in S:
    render(file, theme, count, blocks)
print('ALL DONE:', len(S))
