# Deploying for a small, invited audience

The goal: a link you can put on a résumé or hand to a few people, where **anyone can
look around, only people you invite can generate predictions**, and Gemini usage stays
inside the free tier.

Everything below is on free plans. Budget about 45 minutes end to end.

---

## How access control works

Three layers, all already in the code:

| Layer | Where | What it stops |
|---|---|---|
| Firebase sign-in | `backend/main.py` → `get_current_user` | anonymous traffic hitting the prediction endpoint |
| Email allowlist | `backend/access.py` → `ALLOWED_EMAILS` | signed-in strangers spending your Gemini credit |
| Daily quotas | `backend/access.py` → `PREDICTIONS_PER_USER_PER_DAY`, `PREDICTIONS_PER_DAY_TOTAL` | one invited user (or a bug) burning the whole quota |

Everything else — browsing fixtures, the landing page, the analytics endpoints — stays
open and costs nothing, because it never calls Gemini.

**Quota caveat, so it is not a surprise:** the counters live in the API process's
memory and reset at 00:00 UTC *or* when the process restarts. On a free host that
sleeps when idle, a restart resets them. It is a spend guardrail, not an audit trail.
If you need a hard cap, also set a budget/limit in Google AI Studio, which is the only
place that can truly stop spend.

---

## Step 1 — Lock down the backend config

In your production environment (not in git), set:

```
GEMINI_API_KEY=...
FOOTBALL_DATA_API_KEY=...
FIREBASE_SERVICE_ACCOUNT_JSON={"type":"service_account", ... }   # whole file, one line
ALLOWED_EMAILS=you@gmail.com,friend@gmail.com
PREDICTIONS_PER_USER_PER_DAY=10
PREDICTIONS_PER_DAY_TOTAL=100
ALLOWED_ORIGINS=https://your-app.vercel.app
```

Notes:

- `FIREBASE_SERVICE_ACCOUNT_JSON` is the contents of `serviceAccountKey.json`. Use it
  instead of the file path on hosts where you cannot upload a file. Never commit either.
- `ALLOWED_EMAILS` accepts `*@example.com` to allow a whole domain.
- Leaving `ALLOWED_EMAILS` unset means *any* Google/email account that signs in can
  predict. Fine locally, not fine for a public link.
- `ALLOWED_ORIGINS` should be your exact frontend URL. Unset means any origin.

Blocked users get a clear message in the UI ("This account does not have prediction
access…"), and users past their cap get "You have used your N predictions for today."

---

## Step 2 — Deploy the API (Render free tier)

1. Push the repo to GitHub (see "Moving this to your own GitHub" below).
2. Render → **New → Web Service** → connect the repo.
3. Settings:
   - **Runtime:** Python 3
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - **Instance type:** Free
4. Add every environment variable from Step 1.
5. Deploy, then check `https://<your-api>.onrender.com/health` — it returns
   `{"status":"ok","quota":{...}}`.

The free instance sleeps after ~15 minutes idle and takes ~30 seconds to wake, so the
first prediction after a quiet period is slow. Mention that on the page or accept it.

The prediction history is a SQLite file at `scripts/data/predictions.db`. Free
container disks are ephemeral, so that history resets on redeploy — fine for a demo.
To keep it, attach a persistent disk and point `PREDICTIONS_DB_PATH` at it.

Fly.io and Railway work the same way if you prefer them.

---

## Step 3 — Deploy the frontend (Vercel free tier)

1. Vercel → **Add New → Project** → import the repo.
2. **Root directory:** `frontend`
3. Environment variables (Firebase Console → Project Settings → Your apps → SDK setup):

```
NEXT_PUBLIC_FIREBASE_API_KEY=...
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=...
NEXT_PUBLIC_FIREBASE_PROJECT_ID=...
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=...
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=...
NEXT_PUBLIC_FIREBASE_APP_ID=...
NEXT_PUBLIC_API_BASE_URL=https://<your-api>.onrender.com
```

4. Deploy. Then finish the loop:
   - Firebase Console → Authentication → Settings → **Authorized domains** → add your
     Vercel domain, or sign-in will fail.
   - Set `ALLOWED_ORIGINS` on Render to the Vercel URL and redeploy the API.

`NEXT_PUBLIC_*` values are visible in the browser by design — that is normal for
Firebase web config. Access is enforced by Firebase Auth rules and the backend
allowlist, not by hiding these.

---

## Step 4 — Invite people

1. They open the link and sign in (Firebase Auth).
2. You add their email to `ALLOWED_EMAILS` on Render and redeploy (~1 minute).
3. To revoke: remove the email, redeploy. Their sign-in still works; predictions stop.

---

## Step 5 — Keep an eye on spend

- `GET /health` shows today's usage: predictions used, distinct users, and the limits
  in force.
- Google AI Studio shows real Gemini usage; set a spending limit there as the backstop.
- football-data.org free tier is 10 requests/minute. The client caches fixtures for
  5 minutes and derives team stats from the standings response, so normal browsing
  stays well under it. Heavy simultaneous use can still hit 429s, which degrade to
  cached or mock data rather than errors.

---

## Moving this to your own GitHub

The repo currently points at the course organisation. Publish it under your own
account **with its history intact** — 69 commits read better on a résumé than a single
"initial commit".

Create an empty repo on GitHub first (no README, no licence, so nothing conflicts),
then:

```bash
git add -A
git commit -m "Retire World Cup feature and SportMonks integration; add access controls"
```

```bash
git switch main
git merge wc-accuracy-signals
```

Your local `main` is 3 commits behind `origin/main` (README edits made on GitHub), so
pull those in as well:

```bash
git pull origin main
```

If that conflicts on `README.md`, keep your local version — the rewritten README
already contains the demo-video link those commits added.

```bash
git remote rename origin upstream
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

`upstream` keeps the course remote available if you ever need it; nothing is pushed
there unless you name it explicitly.

Why not fork: a fork is permanently labelled "forked from UCR-CS180/…" and its stars,
issues and traffic belong to the parent. A normal repo is yours, and you can still
credit the coursework and your teammate in the README — which this one does.

Before making it public, confirm nothing sensitive is tracked:

```bash
git ls-files | grep -Ei "\.env$|serviceaccount|credential"
```

That should print nothing. `.env`, `serviceAccountKey.json` and `frontend/.env.local`
are in `.gitignore`, and no secret was ever committed to this history.
