# My Body Pro launch v2 — Reel end cards (1080x1350)
# Hook-first campaign. These are END FRAMES for Reels, not standalone posts.
#
#   npm --prefix /tmp install geist
#   python3 render-pro-launch-v2.py
#
# Output: ../Social Assets/pro-launch-v2/  (override with CARDS_OUT)
#
# RULE: no price on a card unless the card's whole job is the price. The reel
# has already earned the viewer's attention by this point; the card closes on
# the feeling, not the invoice. Only d12 carries money, because that post is
# explicitly about not charging three times.
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, 'render-social-assets.py')
OUTDIR = os.environ.get('CARDS_OUT') or os.path.abspath(
    os.path.join(HERE, '..', 'Social Assets', 'pro-launch-v2'))

src = open(ENGINE, encoding='utf-8').read()
src = src.split("I, A, M = 'ink', 'accent', 'muted'")[0]
src = src.replace("OUT = '/tmp/render'", f"OUT = {OUTDIR!r}")
g = {'__name__': 'engine'}
exec(compile(src, ENGINE, 'exec'), g)
render = g['render']

I, A, M = 'ink', 'accent', 'muted'
S = []

def card(name, theme, eyebrow, rich, sub, size=92, count=None):
    blocks = []
    if eyebrow:
        blocks.append(dict(type='eyebrow', text=eyebrow))
    blocks.append(dict(type='h1', size=size, rich=rich))
    if sub:
        blocks.append(dict(type='body', rich=[(sub, M)]))
    S.append((name, theme, count, blocks))

# ── holding ──────────────────────────────────────────────────────────────────
card('h1-three-apps.png', 'dark', 'Three apps, one account',
     [('The proof was never in ', I), ('one app', A), ('.', A)],
     'Free on the App Store.')

card('h2-three-seconds.png', 'light', 'Move',
     [('Tracking you will actually ', I), ('keep up', A), ('.', A)],
     'Three seconds a set. Free on the App Store.')

card('h3-deadline.png', 'dark', 'Before 8 August',
     [('Six months of Pro, ', I), ('free', A), ('.', A)],
     'No code. If your account exists before that date, it is applied.')

# ── D1–D14 ───────────────────────────────────────────────────────────────────
card('d01-the-sentence.png', 'dark', 'Three datasets, one account',
     [('The sentence ', I), ('writes itself', A), ('.', A)],
     'Three apps, one account. The core of each stays free.')

card('d02-receipts.png', 'light', 'You think you will remember',
     [('March is gone unless something ', I), ('wrote it down', A), ('.', A)],
     'Free to start.', size=86)

card('d03-scan-label.png', 'dark', 'Optimise',
     [('Set up in seconds, not an ', I), ('evening', A), ('.', A)],
     'On-device. The image never leaves your phone.')

card('d04-overlay.png', 'dark', 'Move',
     [('Before and after, on the ', I), ('same chart', A), ('.', A)],
     'The protocol overlay is the reason these apps share an account.')

card('d05-it-knew.png', 'dark', 'Fuel',
     [('I never turned this on', I), ('.', A), (' It just ', I), ('knew', A), ('.', A)],
     'It saw a GLP-1 protocol in Optimise and switched to muscle retention.')

card('d06-stop-calories.png', 'light', 'On a GLP-1',
     [('Lose the fat. Keep the ', I), ('muscle', A), ('.', A)],
     'You are already eating under. Protein is what decides the rest.')

card('d07-receipts-week1.png', 'dark', 'Week one of charging',
     [('Including the number I would rather ', I), ('not post', A), ('.', A)],
     'Subscribers, downloads, refunds, cancellations.')

card('d08-alignment.png', 'dark', 'You cannot see it yet',
     [('One number for everything you are ', I), ('already doing', A), ('.', A)],
     'Weight, strength and protein against the goal you actually set.')

card('d09-airplane-mode.png', 'light', 'Private by design',
     [('Yours. ', I), ('Only yours', A), ('.', A)],
     'No ads. No data sales. Photos never leave the device.')

card('d10-only-one.png', 'light', 'I only want the workout one',
     [('Then take ', I), ('just that one', A), ('.', A)],
     'Every app has its own plan. Add the others any time, never charged twice.')

card('d11-one-fortnight.png', 'dark', 'Same two weeks',
     [('One timeline, and suddenly you can ', I), ('read it', A), ('.', A)],
     'Every insight in the product comes from that and nothing else.')

card('d12-priced-against.png', 'light', 'One body, one subscription',
     [('Two apps’ worth of money. ', I), ('Three apps', A), ('.', A)],
     '£49.99 a year. First week free. The core of each app stays free.')

card('d13-couldnt-answer.png', 'dark', 'A doctor asked what I had been doing',
     [('Now it takes about ', I), ('four seconds', A), ('.', A)],
     'Three apps, one account. Free to start.')

card('d14-what-changed.png', 'dark', 'Nothing was taken away',
     [('Everything free is ', I), ('still free', A), ('.', A)],
     'Pro added the deeper end on top. That is the whole of what changed.')

for file, theme, count, blocks in S:
    render(file, theme, count, blocks)
print('ALL DONE:', len(S), '->', OUTDIR)
