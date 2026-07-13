# Publishing

Deployment, atomic publish process, rollback, CDN configuration, and cache headers.

---

## Output Directory Structure

```
{OUTPUT_DIR}/
├── index.html                  ← live edition (current)
├── assets/
│   ├── daily-sports-page.css
│   └── daily-sports-page.js
├── data/
│   └── edition.json            ← structured data for the current edition
├── archive/
│   ├── 2026-07-13-0642.html
│   ├── 2026-07-13-1203.html
│   └── ...
└── .lkg                        ← last-known-good record (path + edition ID)
```

`OUTPUT_DIR` defaults to `./build/output`. Override with the `OUTPUT_DIR` environment variable or the `--output-dir` CLI flag.

---

## Atomic Publication Process

`Publisher` (`src/publisher/publisher.py`) never writes directly to the live output path. All work happens in a temp directory first, and the final promotion is a single atomic directory rename.

The full 11-step process:

1. **Allocate temp directory** — create `{OUTPUT_DIR}/.tmp-{run_id}/`
2. **Write assets** — copy `static/css/daily-sports-page.css` and `static/js/daily-sports-page.js` to `.tmp-{run_id}/assets/`
3. **Write edition JSON** — write `edition.json` to `.tmp-{run_id}/data/`
4. **Write index.html** — write rendered HTML to `.tmp-{run_id}/index.html`
5. **Validate staged output** — check that `index.html` exists, is non-empty (> 10 KB), and `edition.json` is valid JSON with the expected `edition.id`
6. **Archive current live edition** — if `{OUTPUT_DIR}/index.html` exists, copy it to `{OUTPUT_DIR}/archive/{YYYY-MM-DD-HHMM}.html`
7. **Atomic rename** — rename `.tmp-{run_id}/` to a new temp name, then rename `{OUTPUT_DIR}` out of the way and the new dir into place; on POSIX systems this is a single `os.rename()` call and is atomic
8. **Verify live URL** — if `PUBLIC_BASE_URL` is set, send a HEAD request to confirm the page is reachable
9. **Record last-known-good** — write `{OUTPUT_DIR}/.lkg` with the edition ID and timestamp
10. **Purge CDN** — POST to `CDN_PURGE_URL` if configured (see [CDN Configuration](#cdn-configuration))
11. **Clean up** — remove temp dirs from failed or superseded runs older than 24 hours

If any step 1–7 fails, the temp directory is left in place for debugging and the live edition is unchanged.

---

## Rollback

`Publisher.rollback()` restores the most recent archived edition to the live path.

**From the CLI:**

```bash
daily-sports-page publish --rollback
```

**What happens:**

1. Reads `{OUTPUT_DIR}/.lkg` to find the edition ID of the last known-good edition
2. Locates the corresponding archive entry in `{OUTPUT_DIR}/archive/`
3. Copies that HTML file to `{OUTPUT_DIR}/index.html` atomically
4. Triggers CDN purge if configured

**Note:** Rollback restores only `index.html`. If the edition JSON or assets also need to be rolled back (rare), use `daily-sports-page publish --rollback --full`, which restores a full archive snapshot if one is available.

---

## CDN Configuration

Set the `CDN_PURGE_URL` environment variable to a webhook URL that accepts a POST request. After each successful publish, `Publisher` sends:

```http
POST {CDN_PURGE_URL}
Content-Type: application/json

{
  "paths": ["/", "/data/edition.json"],
  "edition_id": "2026-07-13-morning-a3f8c1",
  "purged_at": "2026-07-13T06:42:55Z"
}
```

The publisher treats a CDN purge failure as a warning, not a hard error. The live edition is already published. The failure is logged and an alert is sent if `ALERT_WEBHOOK_URL` is set.

**CDN provider examples:**

| Provider                     | `CDN_PURGE_URL` format                                             |
| ---------------------------- | ------------------------------------------------------------------ |
| Cloudflare (cache purge API) | `https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache` |
| Fastly (surrogate key purge) | `https://api.fastly.com/service/{service_id}/purge_all`            |
| Custom webhook               | Any URL that accepts POST                                          |

---

## Cache Headers

Configure your web server or CDN origin rules to serve these headers:

| File                           | `Cache-Control`                       |
| ------------------------------ | ------------------------------------- |
| `index.html`                   | `public, max-age=60, must-revalidate` |
| `data/edition.json`            | `public, max-age=60, must-revalidate` |
| `assets/daily-sports-page.css` | `public, max-age=31536000, immutable` |
| `assets/daily-sports-page.js`  | `public, max-age=31536000, immutable` |
| `archive/*.html`               | `public, max-age=31536000, immutable` |

Assets are served with long-lived cache headers because they are versioned by filename. When assets change, the filename changes (via content hash). `index.html` and `edition.json` use short TTLs so the CDN edge picks up new editions promptly.

---

## Staging vs Production

Use the `--output-dir` flag or the `OUTPUT_DIR` environment variable to target a staging path:

```bash
# Publish to staging
OUTPUT_DIR=/var/www/staging/sports-page daily-sports-page run --edition morning --publish

# Or equivalently
daily-sports-page run --edition morning --publish --output-dir /var/www/staging/sports-page
```

To point the same build at production:

```bash
OUTPUT_DIR=/var/www/production/sports-page daily-sports-page publish \
  --edition-json build/2026-07-13-0600/edition.json
```

This re-publishes an already-rendered edition to a different output path without re-running the pipeline.

---

## Last-Known-Good File

`{OUTPUT_DIR}/.lkg` is a JSON file written after each successful publish:

```json
{
  "edition_id": "2026-07-13-morning-a3f8c1",
  "path": "/var/www/sports-page/index.html",
  "published_at": "2026-07-13T06:42:55Z",
  "archive_path": "/var/www/sports-page/archive/2026-07-13-0642.html"
}
```

To check the last successful publish:

```bash
cat {OUTPUT_DIR}/.lkg
```

If `.lkg` is missing or its `published_at` is older than the expected publish window, the monitoring health check will flag a stale edition. See [`docs/ops/monitoring.md`](../ops/monitoring.md).
