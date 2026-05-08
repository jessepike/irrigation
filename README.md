# Pike Irrigation

Single-page web app for managing the Pike property's irrigation schedule. 8 K-Rain BL-KR controllers + 3 Rainbird TBOS (being phased out). The K-Rain dashboard is the real source of truth — this app is a viewer, conflict checker, and seasonal checklist over a snapshot of that data.

---

## Why this exists (so future-you remembers)

The original Google Sheet was a hand-computed grid of stations × time slots. It was unreadable on a phone, didn't show overlaps, and was easy to get wrong because the actual run times had to be computed manually (a program starts at 2:00 AM with 4 zones × 20 min → station 4 actually runs 3:00–3:20). Anything you changed in K-Rain had to be re-transcribed.

The new model:

- **K-Rain dashboard** = source of truth. Edit there.
- **Gemini browser agent** = scrapes the dashboard → CSV.
- **`scripts/csv_to_json.py`** = converts CSV → canonical `data/controllers.json`.
- **Static SPA** = reads JSON, computes actual run events, finds conflicts, runs the seasonal checklist.
- **GitHub Pages** = hosts it. PWA installable on iPhone.

No database. No backend. Git history is your audit log.

---

## Stack decisions (and when to change them)

| Choice | Reasoning | Revisit if… |
|---|---|---|
| **GitHub-only**, no Supabase | 4 schedule changes/year, 11 controllers — DB is overkill. CSV in git = versioned source of truth. | You want multi-device checklist sync (phone + iPad), or you want the Gemini agent to write directly to a DB instead of producing a CSV you commit. |
| **Static SPA** (vanilla HTML/JS, no framework) | Single file, zero build step, deploys anywhere. | The app crosses ~50KB of JS or you want client-side routing. |
| **localStorage** for checklist state | Single-device fine for current use. | You forget on which device you marked things done. → Move to Supabase. |
| **Rainbird TBOS = manual entry** | 3 boxes, being phased out. Not worth scraping. | Adding new non-K-Rain controllers becomes routine. |
| **30-min buffer rule** for conflicts | User's stated minimum gap between different programs. | Pressure dynamics change (new pump, more zones). |

---

## What the app shows

- **Today** — chronological list (or Gantt timeline) of every run event today. Each event = (controller, program, zone, computed start, computed end, budgeted duration). Conflicts highlighted in red. NOW indicator on current/imminent events.
- **Conflicts** — pairwise list of programs/controllers that overlap or run < 30 min apart. Same-program sequential events are filtered out (S1→S2→S3 within one program is intentional, not a conflict).
- **Controllers** — card per physical controller with all programs, start times, days, water budget %, daily runtime, and zone durations.
- **Checklist** — seasonal tabs (Spring/Summer/Fall/Winter), items scoped global / per-controller / per-zone. State persisted by year+season — Spring 2026 doesn't bleed into Spring 2027.

---

## Refresh workflow (the only manual step)

Run this 4× a year (when seasonal budget shifts) or whenever you change schedules:

```bash
# 1. Run Gemini agent against K-Rain dashboard, save CSV to data/
# 2. Convert CSV → JSON
python3 scripts/csv_to_json.py data/irrigation_schedule_YYYY-MM-DD.csv

# 3. Commit + push
git add data/ && git commit -m "refresh schedule $(date +%Y-%m-%d)" && git push

# GitHub Pages updates in ~30 sec
```

The CSV stays in `data/` for history (it's small). Old CSVs become part of your audit trail — you can `git diff` between two refreshes to see what changed.

---

## Rainbird TBOS (3 controllers, manual)

Edit `data/rainbird.json` directly. Same shape as `controllers.json`. As you phase them out, delete entries from the `controllers` array.

---

## Seasonal checklist contents

Edit `data/checklist.json` to change items.

- **Spring**: turn on main, replace battery (per controller), test sprinklers (per zone), validate schedule, budget review
- **Summer**: budget → 100% (per controller), walk yard for dry spots
- **Fall**: budget → 50% (per controller), check for leaf blockage
- **Winter**: turn off main, drain system, remove batteries (per controller), pack valve boxes with insulation (per controller)

State key format: `pike-irrig:checklist:<year>:<season>` in localStorage.

---

## Local preview

```bash
cd <this folder>
python3 -m http.server 8000
# open http://localhost:8000/
```

Won't work from `file://` directly — the app uses `fetch()` for the JSON files. Host it.

---

## Deploy to GitHub Pages (one-time)

```bash
git init
git add .
git commit -m "init"
gh repo create pike-irrigation --public --source=. --push
gh repo edit --enable-pages --pages-branch=main
```

Or web UI: New repo → upload everything → Settings → Pages → Source `main` / root.

URL: `https://<your-username>.github.io/pike-irrigation/`

---

## Install on iPhone

1. Open the GitHub Pages URL in **Safari** (not Chrome — only Safari can install PWAs on iOS).
2. Tap Share → "Add to Home Screen".
3. App icon appears like any native app. Opens full-screen, no browser chrome. Offline cache via service worker.

---

## File map

```
.
├── index.html               # the app (single file: HTML+CSS+JS, ~30KB)
├── manifest.json            # PWA manifest
├── sw.js                    # service worker (offline cache)
├── icon-192.png             # PWA icon (192×192)
├── icon-512.png             # PWA icon (512×512)
├── data/
│   ├── controllers.json     # canonical K-Rain state (regenerated from CSV)
│   ├── rainbird.json        # manually maintained TBOS state
│   ├── checklist.json       # seasonal checklist template
│   └── irrigation_schedule_*.csv  # history of CSV exports from Gemini
├── scripts/
│   └── csv_to_json.py       # CSV → JSON converter
├── README.md                # this file
└── Pike - Watering Schedule.{csv,xlsx}  # original sheet (legacy reference, can delete)
```

---

## What's NOT in this app (yet)

- **Editing schedules in-app.** The K-Rain dashboard is the source of truth — edits go there, then re-scrape. If walk-around tactical edits become important again, see the v1 prototype's "Changes" button approach (overrides + diff to copy-paste).
- **Multi-device checklist sync.** Spring batteries marked done on your phone won't show as done on your laptop. Cross that bridge with Supabase if/when it matters.
- **Notifications / reminders.** "It's June 1, time to crank budgets to 100%." Could be added later via a scheduled GitHub Action that emails you.
- **Map/spatial view.** "Which valve is in the front yard?" If forgetting locations becomes a real problem, add property photos or a map overlay per controller.

---

## Open cleanup

`rt.js`, `node_modules/`, `package.json`, `package-lock.json` are leftover jsdom test artifacts from the build session. Safe to `rm` — they're not used by the app. Can't be removed by automation due to mount permissions; just delete in Finder.
