# My Body — Instagram auto-posting pipeline

Fully automated, free daily Instagram posting. A GitHub Actions cron runs each
morning, reads `schedule.json`, and publishes that day's post to your Instagram
Business account via Meta's official Content Publishing API. No monthly tool,
no manual step once it's set up.

**How it works:** GitHub Actions (free) → runs `post.js` at ~08:00 UK → finds
today's entry in `schedule.json` → uploads the image(s) from this repo (served
over `raw.githubusercontent.com`) → publishes with the caption + hashtags.

---

## What only you can do (one-time, ~30–40 min)

I can't do these — they need your Meta/Instagram/GitHub login. Do them once.

### 1. Make Instagram postable
- Instagram app → **Settings → Account type → switch to Business or Creator**.
- Create/connect a **Facebook Page** and link your Instagram to it
  (Page → Settings → Linked accounts → Instagram). The publishing API requires
  the IG account to be linked to a Page.

### 2. Create a Meta app + get the IDs and token
- Go to **developers.facebook.com** → My Apps → **Create App** → type
  **Business**.
- Add the **Instagram** product (Instagram Graph API / "Instagram content
  publishing").
- In the **Graph API Explorer** (or the app's tools), generate a **User access
  token** with these permissions: `instagram_basic`, `instagram_content_publish`,
  `pages_show_list`, `pages_read_engagement`, `business_management`.
- Exchange it for a **long-lived token** (lasts ~60 days). Quick way — open in a
  browser (fill in your values):
  ```
  https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=SHORT_LIVED_TOKEN
  ```
- Get your **Instagram Business account id** (numeric). One way:
  ```
  https://graph.facebook.com/v21.0/me/accounts?access_token=LONG_LIVED_TOKEN
  → gives your Page id, then:
  https://graph.facebook.com/v21.0/PAGE_ID?fields=instagram_business_account&access_token=LONG_LIVED_TOKEN
  ```

Keep the **long-lived token** and the **IG user id** — you'll paste them into
GitHub in step 4. (Never commit them to the repo; they go in Secrets only.)

### 3. Put this folder in a **public** GitHub repo
- Create a new repo (e.g. `mybody-social`), **public** (so the image URLs at
  `raw.githubusercontent.com` are reachable by Meta — the images are just
  marketing graphics, nothing sensitive).
- Push the entire `social-automation/` contents to the repo **root** (so
  `post.js`, `schedule.json`, `images/`, and `.github/workflows/` sit at the top
  level of the repo).

### 4. Add the secrets
Repo → **Settings → Secrets and variables → Actions → New repository secret**:
- `IG_USER_ID` → your Instagram Business account id
- `IG_ACCESS_TOKEN` → the long-lived token

That's the minimum. The daily workflow will now run on its own.

### 5. Test it before trusting it
- Repo → **Actions → Daily Instagram post → Run workflow**.
- First try with **dry_run = true** — it logs what it would post without
  publishing. Check the run's log.
- Then run once with **date_override = 2026-07-24** and dry_run off to publish
  the opener for real and confirm it lands on the account.

---

## Keeping it running (token expiry)

The token expires in ~60 days. Two options:
- **Manual (simplest):** every ~50 days, generate a fresh long-lived token
  (step 2) and update the `IG_ACCESS_TOKEN` secret.
- **Automatic (optional):** the included `refresh-token.yml` workflow refreshes
  it monthly. It needs three more secrets: `FB_APP_ID`, `FB_APP_SECRET`, and
  `GH_PAT` (a fine-grained Personal Access Token with *Secrets: read and write*
  on this repo). If you don't want this, delete `.github/workflows/refresh-token.yml`.

---

## Day-to-day: adding posts

`schedule.json` is the schedule. Each entry:
```json
{
  "date": "2026-07-31",
  "images": ["post-08.png"],
  "caption": "…",
  "hashtags": "#peptides #biohacking"
}
```
- Drop new PNGs into `images/`, add an entry per date, commit. Done.
- **Carousel:** list multiple files in `images` (2–10). They post in array order.
- **Skip a day:** add `"skip": true` to that entry (e.g. if you posted it
  manually).
- Render new graphics with the same template: `screenshot-rig/post-shot.html`
  (in the main project), style spec in
  `Marketing Restart - Bevel Teardown + Content System.md`.

**Tone rule:** apps are in App Store review — keep captions "coming soon / days
away", never "live", until launch. Then switch to the Multilaunch Kit copy.

---

## Local test (optional)
With Node 20+:
```
DRY_RUN=true DATE_OVERRIDE=2026-07-24 IG_USER_ID=x IG_ACCESS_TOKEN=y node post.js
```
Prints what it would publish for that date without calling Instagram.
