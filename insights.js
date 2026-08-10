// ─── My Body — weekly performance report ─────────────────────────────────
// Pulls Instagram insights for everything published and writes REPORT.md,
// ranked by the metric that actually predicts distribution: saves + shares.
// Likes are reported but not ranked on — they are the least useful signal.
//
// The point of this file is one decision: which post gets the £50 boost.
//
// Env: IG_USER_ID, IG_ACCESS_TOKEN, GRAPH_VERSION (optional), LIMIT (optional)

import { writeFile } from 'node:fs/promises';

const GRAPH = `https://graph.facebook.com/${process.env.GRAPH_VERSION || 'v21.0'}`;
const IG_USER_ID = process.env.IG_USER_ID;
const TOKEN = process.env.IG_ACCESS_TOKEN;
const LIMIT = Number(process.env.LIMIT || 40);

if (!IG_USER_ID || !TOKEN) { console.error('✗ IG_USER_ID and IG_ACCESS_TOKEN must be set.'); process.exit(1); }

async function get(path, params = {}) {
  const qs = new URLSearchParams({ ...params, access_token: TOKEN });
  const res = await fetch(`${GRAPH}/${path}?${qs}`);
  const json = await res.json();
  if (json.error) throw new Error(`${path}: ${JSON.stringify(json.error)}`);
  return json;
}

// Metric names differ by media type and Meta moves them around; ask for a
// generous set and keep whatever comes back rather than failing the run.
const METRICS = {
  VIDEO:    'reach,saved,shares,comments,likes,total_interactions,views',
  REELS:    'reach,saved,shares,comments,likes,total_interactions,views',
  IMAGE:    'reach,saved,shares,comments,likes,total_interactions',
  CAROUSEL_ALBUM: 'reach,saved,shares,comments,likes,total_interactions',
};

async function insightsFor(media) {
  const metric = METRICS[media.media_type] || METRICS.IMAGE;
  try {
    const r = await get(`${media.id}/insights`, { metric });
    const out = {};
    for (const m of r.data || []) out[m.name] = m.values?.[0]?.value ?? 0;
    return out;
  } catch (e) {
    console.warn(`  (no insights for ${media.id}: ${e.message.slice(0, 90)})`);
    return {};
  }
}

function firstLine(caption = '') {
  return caption.split('\n')[0].slice(0, 78);
}

async function main() {
  const media = await get(`${IG_USER_ID}/media`, {
    fields: 'id,caption,media_type,media_product_type,permalink,timestamp',
    limit: String(LIMIT),
  });

  const rows = [];
  for (const m of media.data || []) {
    const ins = await insightsFor(m);
    const saves = ins.saved || 0;
    const shares = ins.shares || 0;
    rows.push({
      date: (m.timestamp || '').slice(0, 10),
      type: m.media_product_type || m.media_type,
      hook: firstLine(m.caption),
      reach: ins.reach || 0,
      views: ins.views || 0,
      saves, shares,
      likes: ins.likes || 0,
      comments: ins.comments || 0,
      score: saves + shares,
      permalink: m.permalink,
    });
  }

  rows.sort((a, b) => b.score - a.score);

  const total = (k) => rows.reduce((s, r) => s + r[k], 0);
  const now = new Date().toISOString().slice(0, 10);

  let md = `# My Body — Instagram performance\n\n`;
  md += `Generated ${now}. Ranked by **saves + shares**, which is what the\n`;
  md += `recommendation engine actually rewards. Likes are shown but not ranked on.\n\n`;

  if (!rows.length) {
    md += `Nothing published yet.\n`;
  } else {
    const best = rows[0];
    md += `## The decision\n\n`;
    md += `Put the **£50 boost** behind:\n\n`;
    md += `> **${best.hook}**\n>\n`;
    md += `> ${best.saves} saves · ${best.shares} shares · ${best.reach} reach — ${best.permalink}\n\n`;
    md += `Target UK, 25–55, interests in strength training / weight loss / wellness.\n`;
    md += `If the top post has fewer than 10 saves, boost nothing this week — the\n`;
    md += `creative is not ready and paid spend will only buy you a wider audience\n`;
    md += `for something that is not landing.\n\n`;

    md += `## Totals\n\n`;
    md += `| Posts | Reach | Views | Saves | Shares | Likes | Comments |\n|---|---|---|---|---|---|---|\n`;
    md += `| ${rows.length} | ${total('reach')} | ${total('views')} | ${total('saves')} | ${total('shares')} | ${total('likes')} | ${total('comments')} |\n\n`;

    md += `## Every post\n\n`;
    md += `| # | Date | Type | Hook | Reach | Views | Saves | Shares | Score |\n|---|---|---|---|---|---|---|---|---|\n`;
    rows.forEach((r, i) => {
      md += `| ${i + 1} | ${r.date} | ${r.type} | ${r.hook.replace(/\|/g, '\\|')} | ${r.reach} | ${r.views} | ${r.saves} | ${r.shares} | **${r.score}** |\n`;
    });

    md += `\n## Reading this\n\n`;
    md += `- **Saves** mean someone intends to come back. On a product account that is\n`;
    md += `  the closest free proxy for purchase intent.\n`;
    md += `- **Shares** are the only metric that compounds — a share puts the post in\n`;
    md += `  front of an audience you did not have.\n`;
    md += `- **Reach with no saves** means the hook worked and the payoff did not.\n`;
    md += `  Rewrite the middle, keep the first three seconds.\n`;
    md += `- **No reach at all** means the hook failed. Rewrite the first line.\n`;
  }

  await writeFile(new URL('./REPORT.md', import.meta.url), md);
  console.log(`✓ REPORT.md written — ${rows.length} post(s), top score ${rows[0]?.score ?? 0}`);
}

main().catch(e => { console.error('✗ ' + e.message); process.exit(1); });
