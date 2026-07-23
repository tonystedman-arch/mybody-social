// ─── Long-lived token refresh (optional) ─────────────────────────────────
// Meta long-lived tokens last ~60 days. This exchanges the current token for a
// fresh long-lived one and writes it to $GITHUB_OUTPUT (masked) so the workflow
// can store it back as the IG_ACCESS_TOKEN secret. Run it on a monthly cron.
//
// Env: IG_ACCESS_TOKEN (current), FB_APP_ID, FB_APP_SECRET, GRAPH_VERSION (opt).
// Node 20+.

import { appendFile } from 'node:fs/promises';

const GRAPH = `https://graph.facebook.com/${process.env.GRAPH_VERSION || 'v21.0'}`;

async function main() {
  const { IG_ACCESS_TOKEN, FB_APP_ID, FB_APP_SECRET, GITHUB_OUTPUT } = process.env;
  if (!IG_ACCESS_TOKEN || !FB_APP_ID || !FB_APP_SECRET) {
    console.error('✗ IG_ACCESS_TOKEN, FB_APP_ID and FB_APP_SECRET are required.');
    process.exit(1);
  }
  const url = `${GRAPH}/oauth/access_token?grant_type=fb_exchange_token`
    + `&client_id=${FB_APP_ID}&client_secret=${FB_APP_SECRET}`
    + `&fb_exchange_token=${IG_ACCESS_TOKEN}`;
  const res = await fetch(url);
  const json = await res.json();
  if (!res.ok || json.error || !json.access_token) {
    console.error('✗ Refresh failed: ' + JSON.stringify(json.error || json));
    process.exit(1);
  }
  // Mask in logs, then hand to the workflow step that updates the secret.
  console.log('::add-mask::' + json.access_token);
  if (GITHUB_OUTPUT) await appendFile(GITHUB_OUTPUT, `new_token=${json.access_token}\n`);
  console.log('✓ Token refreshed (expires in ~' + (json.expires_in || 5184000) + 's).');
}

main().catch(e => { console.error('✗ ' + e.message); process.exit(1); });
