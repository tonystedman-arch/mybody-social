// ─── My Body — Instagram auto-poster ─────────────────────────────────────
// Publishes today's post to an Instagram Business/Creator account via Meta's
// official Content Publishing API. Driven by GitHub Actions cron (free).
// Reads schedule.json, finds the entry whose date == today (Europe/London),
// and posts a single image or a carousel. No-op if there's nothing for today.
//
// Env (set as GitHub repository secrets / workflow env):
//   IG_USER_ID        Instagram Business account id (numeric)
//   IG_ACCESS_TOKEN   long-lived access token with instagram_content_publish
//   IMAGE_BASE_URL    public base URL where images/ are hosted (no trailing /)
//   GRAPH_VERSION     e.g. v21.0 (optional; defaults below)
//   DATE_OVERRIDE     YYYY-MM-DD to force a specific day (testing; optional)
//   DRY_RUN           "true" to log the API calls without publishing (optional)
//
// Node 20+ (uses global fetch). No dependencies.

import { readFile } from 'node:fs/promises';

const GRAPH = `https://graph.facebook.com/${process.env.GRAPH_VERSION || 'v21.0'}`;
const IG_USER_ID = process.env.IG_USER_ID;
const TOKEN = process.env.IG_ACCESS_TOKEN;
const IMAGE_BASE_URL = (process.env.IMAGE_BASE_URL || '').replace(/\/$/, '');
const DRY_RUN = String(process.env.DRY_RUN || '').toLowerCase() === 'true';

function londonToday() {
  // 'en-CA' gives YYYY-MM-DD; timeZone pins it to UK local date.
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London' }).format(new Date());
}

function fail(msg) { console.error('✗ ' + msg); process.exit(1); }

async function api(path, params) {
  const body = new URLSearchParams({ ...params, access_token: TOKEN });
  const res = await fetch(`${GRAPH}/${path}`, { method: 'POST', body });
  const json = await res.json();
  if (!res.ok || json.error) {
    throw new Error(`Graph error on ${path}: ${JSON.stringify(json.error || json)}`);
  }
  return json;
}

async function containerReady(id, tries = 30) {
  // Poll until the media container is FINISHED (images are usually instant;
  // carousels/large media can take a few seconds).
  for (let i = 0; i < tries; i++) {
    const res = await fetch(`${GRAPH}/${id}?fields=status_code&access_token=${TOKEN}`);
    const json = await res.json();
    if (json.status_code === 'FINISHED') return;
    if (json.status_code === 'ERROR' || json.error) {
      throw new Error(`Container ${id} failed: ${JSON.stringify(json.error || json)}`);
    }
    await new Promise(r => setTimeout(r, 3000));
  }
  throw new Error(`Container ${id} not ready after ${tries} tries`);
}

async function publishSingle(imageUrl, caption) {
  if (DRY_RUN) { console.log('DRY_RUN single →', imageUrl); return 'dry-run'; }
  const c = await api(`${IG_USER_ID}/media`, { image_url: imageUrl, caption });
  await containerReady(c.id);
  const pub = await api(`${IG_USER_ID}/media_publish`, { creation_id: c.id });
  return pub.id;
}

async function publishCarousel(imageUrls, caption) {
  if (DRY_RUN) { console.log('DRY_RUN carousel →', imageUrls.join(', ')); return 'dry-run'; }
  const children = [];
  for (const url of imageUrls) {
    const child = await api(`${IG_USER_ID}/media`, { image_url: url, is_carousel_item: 'true' });
    await containerReady(child.id);
    children.push(child.id);
  }
  const c = await api(`${IG_USER_ID}/media`, {
    media_type: 'CAROUSEL', children: children.join(','), caption,
  });
  await containerReady(c.id);
  const pub = await api(`${IG_USER_ID}/media_publish`, { creation_id: c.id });
  return pub.id;
}

async function main() {
  if (!IG_USER_ID || !TOKEN) fail('IG_USER_ID and IG_ACCESS_TOKEN must be set.');
  if (!IMAGE_BASE_URL && !DRY_RUN) fail('IMAGE_BASE_URL must be set.');

  const schedule = JSON.parse(await readFile(new URL('./schedule.json', import.meta.url), 'utf8'));
  const today = process.env.DATE_OVERRIDE || londonToday();

  const entry = schedule.find(e => e.date === today);
  if (!entry) { console.log(`Nothing scheduled for ${today}. Exiting cleanly.`); return; }
  if (entry.skip) { console.log(`Entry for ${today} marked skip. Exiting.`); return; }

  const caption = [entry.caption, '', (entry.hashtags || '')].join('\n').trim();
  const urls = (entry.images || []).map(f => `${IMAGE_BASE_URL}/${f}`);
  if (!urls.length) fail(`Entry for ${today} has no images.`);

  console.log(`Posting ${today}: ${entry.images.length} image(s)${DRY_RUN ? ' [DRY_RUN]' : ''}`);
  const id = urls.length === 1
    ? await publishSingle(urls[0], caption)
    : await publishCarousel(urls, caption);
  console.log(`✓ Published. Media id: ${id}`);
}

main().catch(e => fail(e.message));
