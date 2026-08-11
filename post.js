// ─── My Body — Instagram auto-poster (v2) ────────────────────────────────
// Publishes today's post to an Instagram Business/Creator account via Meta's
// official Content Publishing API. Driven by GitHub Actions cron (free).
//
// v2 adds:
//   • REELS (video) and STORIES media types alongside images and carousels
//   • a launch-status gate, so a post that names a price cannot publish
//     before the subscriptions are approved
//   • a rolling holding queue, so the account keeps posting while Apple
//     is still reviewing, without anyone editing a schedule by hand
//
// Env (GitHub repository secrets / workflow env):
//   IG_USER_ID        Instagram Business account id (numeric)
//   IG_ACCESS_TOKEN   long-lived token with instagram_content_publish
//   MEDIA_BASE_URL    public base URL where media/ is hosted (no trailing /)
//   IMAGE_BASE_URL    legacy alias for MEDIA_BASE_URL
//   LAUNCH_STATUS     "pro_live" once the subscriptions are approved.
//                     Anything else (or unset) blocks gated posts.
//   GRAPH_VERSION     e.g. v21.0 (optional)
//   DATE_OVERRIDE     YYYY-MM-DD to force a specific day (optional)
//   POST_ID_OVERRIDE  publish one specific schedule id, ignoring the date
//   DRY_RUN           "true" to log the API calls without publishing
//
// Node 20+ (global fetch). No dependencies.

import { readFile, appendFile } from 'node:fs/promises';

const GRAPH = `https://graph.facebook.com/${process.env.GRAPH_VERSION || 'v21.0'}`;
const IG_USER_ID = process.env.IG_USER_ID;
const TOKEN = process.env.IG_ACCESS_TOKEN;
const BASE = (process.env.MEDIA_BASE_URL || process.env.IMAGE_BASE_URL || '').replace(/\/$/, '');
const DRY_RUN = String(process.env.DRY_RUN || '').toLowerCase() === 'true';
const LAUNCH_STATUS = (process.env.LAUNCH_STATUS || 'unknown').trim().toLowerCase();

const log = (...a) => console.log(...a);
function fail(msg) { console.error('✗ ' + msg); process.exit(1); }

function londonToday() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London' }).format(new Date());
}

async function api(path, params) {
  const body = new URLSearchParams({ ...params, access_token: TOKEN });
  const res = await fetch(`${GRAPH}/${path}`, { method: 'POST', body });
  const json = await res.json();
  if (!res.ok || json.error) throw new Error(`Graph error on ${path}: ${JSON.stringify(json.error || json)}`);
  return json;
}

// Video containers take real time to transcode. Images are near-instant.
async function containerReady(id, { tries = 60, waitMs = 5000 } = {}) {
  for (let i = 0; i < tries; i++) {
    const res = await fetch(`${GRAPH}/${id}?fields=status_code,status&access_token=${TOKEN}`);
    const json = await res.json();
    if (json.status_code === 'FINISHED') return;
    if (json.status_code === 'ERROR' || json.error) {
      throw new Error(`Container ${id} failed: ${JSON.stringify(json.status || json.error || json)}`);
    }
    await new Promise(r => setTimeout(r, waitMs));
  }
  throw new Error(`Container ${id} not ready after ${tries} polls`);
}

// Meta's transcoder fails intermittently on media it will happily accept on the
// next attempt. Code 2207052 ("Media upload has failed") is the common one, and
// Meta's own guidance is to retry rather than to change the file. On 11 Aug 2026
// d01-the-sentence died on this with a file that is byte-for-byte the same shape
// as receipt.mp4, which had published fine 13 hours earlier — same encoder, same
// atom order, same codecs. One unlucky transcode cost the whole day's post.
//
// So: create the container, wait for it, and on a retryable failure throw the
// container away and build a fresh one. Non-retryable errors (bad token, a 404
// on the media URL, a rejected caption) still fail on the first attempt, because
// retrying those just wastes six minutes and hides the real cause.
const RETRYABLE = [2207052, 2207003, 2207001, 2207020, 2207026];

function isRetryable(err) {
  const m = String(err && err.message || '');
  return RETRYABLE.some(code => m.includes(String(code)));
}

async function createAndWait(params, pollOpts, { attempts = 3, backoffMs = 20000 } = {}) {
  for (let attempt = 1; ; attempt++) {
    const c = await api(`${IG_USER_ID}/media`, params);
    try {
      await containerReady(c.id, pollOpts);
      return c.id;
    } catch (err) {
      if (attempt >= attempts || !isRetryable(err)) throw err;
      log(`  ⟳ attempt ${attempt} failed (${err.message}). Rebuilding the container in ${backoffMs / 1000}s.`);
      await new Promise(r => setTimeout(r, backoffMs));
    }
  }
}

async function publishImage(url, caption) {
  if (DRY_RUN) { log('  DRY_RUN image →', url); return 'dry-run'; }
  const id = await createAndWait({ image_url: url, caption }, { tries: 30, waitMs: 3000 });
  return (await api(`${IG_USER_ID}/media_publish`, { creation_id: id })).id;
}

async function publishCarousel(urls, caption) {
  if (DRY_RUN) { log('  DRY_RUN carousel →', urls.join(', ')); return 'dry-run'; }
  const children = [];
  for (const url of urls) {
    children.push(await createAndWait({ image_url: url, is_carousel_item: 'true' },
                                      { tries: 30, waitMs: 3000 }));
  }
  const id = await createAndWait({ media_type: 'CAROUSEL', children: children.join(','), caption },
                                 { tries: 30, waitMs: 3000 });
  return (await api(`${IG_USER_ID}/media_publish`, { creation_id: id })).id;
}

// Meta's Content Publishing API cannot attach music-library tracks — audio has
// to be inside the video file at upload. What it does allow is naming your own
// embedded audio, which gives it an audio page others can reuse. Every Reel
// here carries an original bed generated by build/build_audio.py, so the name
// is honest and the track is ours. See AUDIO.md.
async function publishReel(videoUrl, caption, coverUrl, audioName) {
  if (DRY_RUN) {
    log('  DRY_RUN reel →', videoUrl, coverUrl ? `(cover ${coverUrl})` : '',
        audioName ? `(audio "${audioName}")` : '');
    return 'dry-run';
  }
  const params = { media_type: 'REELS', video_url: videoUrl, caption, share_to_feed: 'true' };
  if (coverUrl) params.cover_url = coverUrl;
  if (audioName) params.audio_name = audioName;
  const id = await createAndWait(params, {});     // transcode, be patient
  return (await api(`${IG_USER_ID}/media_publish`, { creation_id: id })).id;
}

async function publishStory(url, isVideo) {
  if (DRY_RUN) { log('  DRY_RUN story →', url); return 'dry-run'; }
  const params = isVideo
    ? { media_type: 'STORIES', video_url: url }
    : { media_type: 'STORIES', image_url: url };
  const id = await createAndWait(params, isVideo ? {} : { tries: 30, waitMs: 3000 });
  return (await api(`${IG_USER_ID}/media_publish`, { creation_id: id })).id;
}

// ── the gate ────────────────────────────────────────────────────────────────
// A post whose copy names a price, or claims Pro is live, must not publish
// before Apple has approved the subscriptions. The workflow reads
// store/submissions/launch-status.txt into LAUNCH_STATUS; anything other than
// pro_live blocks a gated post. Failing closed is deliberate: an unset
// variable blocks, it does not publish.
function gateAllows(entry) {
  const need = entry.requires || 'none';
  if (need === 'none') return true;
  if (need === 'pro_live') return LAUNCH_STATUS === 'pro_live';
  return false;
}

// Some posts carry a real-world deadline. The grandfather cutoff is hard-coded
// in all three apps as 2026-08-08, so a post advertising it must stop rotating
// once that date passes — otherwise a slow App Review leaves the account
// promising something the product no longer honours.
function notExpired(entry, today) {
  if (!entry.until) return true;
  const live = today <= entry.until;
  if (!live) log(`⌛ ${entry.id} expired on ${entry.until}; skipping.`);
  return live;
}

const eligible = (entry, today) => !entry.skip && gateAllows(entry) && notExpired(entry, today);

function mediaUrl(file) { return `${BASE}/${file}`; }

async function publishEntry(entry) {
  const caption = [entry.caption, '', entry.hashtags || ''].join('\n').trim();
  const kind = entry.type || (entry.images && entry.images.length > 1 ? 'carousel' : 'image');

  log(`→ ${entry.id} [${kind}]${DRY_RUN ? ' (dry run)' : ''}`);

  switch (kind) {
    case 'reel': {
      const id = await publishReel(mediaUrl(entry.video), caption,
                                   entry.cover ? mediaUrl(entry.cover) : undefined,
                                   entry.audioName || process.env.DEFAULT_AUDIO_NAME);
      if (entry.story) await publishStory(mediaUrl(entry.story), /\.mp4$/.test(entry.story));
      return id;
    }
    case 'carousel':
      return publishCarousel(entry.images.map(mediaUrl), caption);
    case 'story':
      return publishStory(mediaUrl(entry.story || entry.images[0]), /\.mp4$/.test(entry.story || ''));
    default:
      return publishImage(mediaUrl(entry.images[0]), caption);
  }
}

// Which posts have already gone out. The workflow commits posted.log back to
// the repo after each run, so sequence position survives between runs.
async function alreadyPosted() {
  try {
    const raw = await readFile(new URL('./posted.log', import.meta.url), 'utf8');
    return new Set(raw.split('\n').filter(l => !l.startsWith('#'))
                      .map(l => l.split('\t')[1]).filter(Boolean));
  } catch { return new Set(); }
}

// Choose today's entry.
//
// mode "sequence" (the default, and the right one here): the campaign runs in
// order from whenever Apple approves, rather than against fixed dates that
// would silently expire if review runs long. Each day it publishes the first
// post in posts[] that has not been published and whose gate is open. Until
// then it rotates the holding queue, so the account never goes quiet.
//
// mode "dated": classic behaviour, posts[].date === today.
async function pickEntry(schedule, today) {
  const all = [...(schedule.posts || []), ...(schedule.holding || [])];

  if (process.env.POST_ID_OVERRIDE) {
    const e = all.find(x => x.id === process.env.POST_ID_OVERRIDE);
    if (!e) fail(`No entry with id ${process.env.POST_ID_OVERRIDE}`);
    return { entry: e, why: 'id override' };
  }

  if ((schedule.mode || 'sequence') === 'sequence') {
    const done = await alreadyPosted();
    const next = (schedule.posts || []).find(e => !e.skip && !done.has(e.id) && notExpired(e, today));
    if (next && gateAllows(next)) return { entry: next, why: `sequence (${done.size} already out)` };
    if (next) {
      log(`⏸ ${next.id} is gated on "${next.requires}" and LAUNCH_STATUS is "${LAUNCH_STATUS}".`);
      log('   Holding the campaign and rotating the holding queue instead.');
    } else if ((schedule.posts || []).length) {
      log('Campaign complete — every scheduled post has been published.');
    }
  } else {
    const dated = (schedule.posts || []).find(e => e.date === today && !e.skip);
    if (dated && gateAllows(dated)) return { entry: dated, why: 'scheduled date' };
    if (dated) log(`⏸ ${dated.id} gated on "${dated.requires}"; LAUNCH_STATUS is "${LAUNCH_STATUS}".`);
  }

  const holding = (schedule.holding || []).filter(e => eligible(e, today));
  if (!holding.length) return { entry: null, why: 'nothing eligible' };
  const day = Math.floor(Date.parse(today + 'T00:00:00Z') / 86400000);
  return { entry: holding[day % holding.length], why: 'holding queue' };
}

async function main() {
  if (!IG_USER_ID || !TOKEN) fail('IG_USER_ID and IG_ACCESS_TOKEN must be set.');
  if (!BASE && !DRY_RUN) fail('MEDIA_BASE_URL must be set.');

  const schedule = JSON.parse(await readFile(new URL('./schedule.json', import.meta.url), 'utf8'));
  const today = process.env.DATE_OVERRIDE || londonToday();

  log(`Date ${today} · launch status "${LAUNCH_STATUS}"`);
  const { entry, why } = await pickEntry(schedule, today);
  if (!entry) { log('Nothing eligible to post today. Exiting cleanly.'); return; }
  log(`Selected via ${why}.`);

  const id = await publishEntry(entry);
  log(`✓ Published ${entry.id}. Media id: ${id}`);

  // Append to a posted log so the insights workflow knows what to measure.
  if (!DRY_RUN && id !== 'dry-run') {
    // Not .catch(()=>{}) — if this write fails the sequence silently restarts
    // from d01 tomorrow and the same post goes out twice.
    await appendFile(new URL('./posted.log', import.meta.url),
                     `${today}\t${entry.id}\t${id}\n`);
  }
}

main().catch(e => fail(e.message));
