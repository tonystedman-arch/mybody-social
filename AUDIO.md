# Sound and music on the Reels

You were right to push. Every Reel now has **real background music** —
tempo-locked, with drums, bass, chords and an arpeggio, and the video cuts land
on the beat. What follows is why it is *our* music rather than a trending track,
and it turns out the reason is not the one I gave first.

---

## The correction

I conflated two separate limits. Untangled:

**1. The API cannot attach catalogue audio.** True, and it applies to everyone.
Meta's Content Publishing API cannot add trending sounds or library music. Audio
must be inside the video file at upload. The only audio parameter it accepts is
`audio_name`, which labels your own original audio.

**2. Business accounts cannot use the full catalogue at all** — not through the
API, and not by hand in the app either. Instagram treats every post from a
business account as commercial content, and the major-label deals do not cover
commercial use. Business accounts get the **Meta Sound Collection** and music
they have licensed themselves. Personal and *Creator* accounts get the full
library including chart music.

That second point is the one that actually matters, and it has a consequence for
your setup:

> **Switch the account to Creator, not Business.** Both types can publish
> through the API. Creator keeps the full music library available for anything
> you post by hand. The only real loss is Instagram Shopping, which you are not
> using. START-HERE has been corrected.

So "most Reels have background music" is true — most of those Reels are personal
or creator accounts pulling from a catalogue that a business account is not
licensed to touch. Embedding your own music in the file, which is what we now
do, is the route that is open to a company account and safe from a takedown.

---

## What we generate — a pulse, not a track

This took two passes. The first attempt had a saw-wave arpeggio and hi-hats on a
perfect grid, which is exactly what generated music sounds like. The second was
a heartbeat, but it **sounded like a saw or a rowing machine** — and the reason
turned out to be anatomy, not the idea:

1. **The lub-dub gap was 132 ms.** A resting heart's S1→S2 (systole) is about
   **300 ms**. At 132 ms the two thuds fuse into one rasping stroke.
2. **Each thud was 340 ms with a 340 ms filtered-noise tail.** A real S1 is
   100–140 ms and essentially tonal. A long noisy tail on a descending sweep is,
   literally, the sound of a saw stroke.
3. **Noise swells.** A 1 s band-passed noise sweep before every cut, plus a
   constant hiss in the drone. Repeated noise swells roughly once a second is
   the signature of a rowing machine flywheel.

Five candidates were built and auditioned before anything shipped
(`tools/reel-rig/audio_candidates.py` — anatomical, sub-pulse only, wood tap,
bowed with no pulse, and close-miked). **Candidate A, "anatomical", was chosen.**

What ships:

- **S1 at 46→33 Hz over 130 ms; S2 at 62→46 Hz over 95 ms, 300 ms later.**
  Short, damped, tonal, and with no noise tail anywhere.
- **Heart-rate variability** — every interval jittered by a slow random walk,
  measuring ~3% beat-to-beat. A sequencer is 0.0%. This is what stops it
  sounding machine-made.
- The rate **drifts from about 58 to 64 bpm** across the reel.
- **No drone.** The low sustained tone was removed on request — it is just the
  pulse in a room now. 76% of the spectrum is the beat itself. To bring the
  drone back, set `DRONE_LEVEL` in `build_music.py` to `0.42`, which is where it
  was.
- A short convolution reverb, so the pulse sits in a chest rather than a vacuum.
- A soft, slightly inharmonic struck note under the end card.
- **Compression before limiting.** A sparse pulse holds nearly all its energy in
  short transients, so peak-normalising alone left it sounding faint. The
  compressor pulls the transients down and the make-up gain lifts everything
  underneath — worth about 6 dB of perceived loudness. Final level is
  **-7.5 dBFS peak, -20.5 dB mean**.

Mid/high noise energy fell from **31.8% of the spectrum to about 5%**, which is
the measurable version of "stop sounding like a saw".

**The cuts land on the pulse.** Segment durations from `reels.json` are snapped
to actual heartbeat onsets — and because the pulse carries HRV, that is not grid
quantisation. The edit inherits the same wandering timing as the audio.

Hear it alone: `python3 build/build_music.py --demo` (or `--demo light`).
The four unused candidates stay in `audio_candidates.py` if this needs
revisiting.

---

## Using a licensed track instead

The generator steps aside if you give it something better. Drop a file in:

```
build/music/default.mp3            → every reel
build/music/d01-the-sentence.mp3   → that reel only
```

`build_reels.py` trims it to length, fades it in and out, and loudness-normalises
to -16 LUFS. Accepted: wav, mp3, m4a, aac, flac, ogg. Push, and CI rebuilds
every Reel with it.

Where to get tracks you can legally use on a company account:

- **Meta Sound Collection** — free, cleared for commercial use on Meta
  platforms, downloadable from Business Suite. The safest option by definition.
- **Uppbeat, Epidemic Sound, Artlist** — subscription, broad commercial licences.

Do not use a track that is merely "free for personal use". Instagram counts your
posts as commercial.

---

## The three routes, and what each costs

| Route | Trending audio | Automated | Cost |
|---|---|---|---|
| **A. Generated music (current)** | No | Fully | No catalogue-sound boost |
| **B. Licensed drop-in** | No | Fully | A subscription, or use Meta Sound Collection free |
| **C. Post key Reels by hand** | Yes, full library on a Creator account | No | Fifteen minutes per post |

**What I would do:** run A for everything. Switch the account to **Creator** so
route C is available at all, then hand-post **D1 and D14** from the phone with a
trending sound — those are the two where extra reach compounds. Everything else
publishes automatically with our own music.

The Instagram Audio API (attaching `audio_id` values programmatically) exists
since around May 2026, but it needs the account reconnected through Facebook
Login, exposes only a subset of the catalogue and gives no preview before
publishing. Not worth rewiring the account for until the campaign shows signs of
working.

---

## Sources

- [Publish Content using the Instagram Platform — Meta for Developers](https://developers.facebook.com/docs/instagram-platform/content-publishing/)
- [Music in Reels for Business Accounts — Tripepi Smith](https://tripepismith.com/insights/music-in-reels-business-accounts/)
- [Instagram Business Accounts & Music Copyright — SRIPLAW](https://sriplaw.com/blog/instagram-business-accounts-and-copyright/)
- [Instagram Creator vs Business Account 2026 — Shadowphone](https://www.shadowphone.io/blog/instagram-business-vs-creator-account-2026)
- [Instagram Reels API Publishing Guide (2026) — Postproxy](https://postproxy.dev/blog/instagram-reels-api-publishing-guide/)
- [Instagram Music API for Reels Audio IDs — bundle.social](https://bundle.social/instagram-music-api)
