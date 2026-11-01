# Deploying publicly

The goal: a link anyone can use, where **each verified account gets 3 predictions a day,
everyone together gets 50, and you are unlimited**, so Gemini usage stays inside your
budget.

Everything below is on free plans. Budget about 45 minutes end to end.

---

## How access control works

Five layers, all already in the code:

| Layer | Where | What it stops |
|---|---|---|
| Firebase sign-in | `backend/main.py` → `get_current_user` | anonymous traffic hitting the prediction endpoint |
| Verified email | `backend/access.py` → `enforce` | throwaway email/password accounts. Google sign-in already counts as verified |
| Owner | `backend/access.py` → `OWNER_EMAILS` | you being capped. Needs an exact, *verified* email |
| Email allowlist (optional) | `backend/access.py` → `ALLOWED_EMAILS` | everyone not listed, if you want an invite-only app |
| Daily quotas | `backend/access.py` → `PREDICTIONS_PER_USER_PER_DAY`, `PREDICTIONS_PER_DAY_TOTAL` | one user, many accounts, or a bug burning the budget |

Everything else — browsing fixtures, the landing page, the analytics endpoints — stays
open and costs nothing, because it never calls Gemini.

**How the caps hold:** counts live in Firestore and update in a transaction, so a
sleeping or restarted instance can't reset them, and two requests at once can't slip
past. Days are UTC. If Firestore can't be reached, the public gets "Predictions are
temporarily unavailable" rather than uncounted predictions; owners keep working.

A prediction already stored for that matchup is free: it calls neither Gemini nor
football-data.org, and doesn't use up one of the user's predictions.

**The real ceiling is the global cap.** One person can open several verified accounts,
so `PREDICTIONS_PER_DAY_TOTAL` is what limits spend. Set it to what you can afford, and
also set a budget in Google AI Studio, the only place that can truly stop spend.

---

## Step 1 — Set up Firestore

The counts need a Firestore database in the same Firebase project as sign-in. The Admin
SDK already installed reaches it with your existing service account.

1. Firebase Console → **Build → Firestore Database → Create database**.
2. Choose **Production mode** and a location near your API. The location can't be
   changed later. Stay on the free **Spark** plan so Firestore itself can't bill you.
3. Open the **Rules** tab, paste the contents of [`firestore.rules`](firestore.rules)
   and click **Publish**. Browsers then have no access; the backend isn't affected.
4. Firebase Console → **Authentication → Sign-in method**: confirm **Email/Password**
   and **Google** are enabled. Verification emails work out of the box; the wording is
   under **Authentication → Templates**.

Each prediction uses about 4 reads and 2 writes, and refunds about the same. The free
tier allows 50,000 reads and 20,000 writes a day.

To reset a day's counts by hand, delete that day's document under
`prediction_quota_days` in the Firestore console, including its `users` subcollection.

**What deleting an account removes** (Account settings → Delete account, for your
privacy policy):

| Data | After deletion |
|---|---|
| Firebase account (email, name, password or Google link) | Deleted |
| That user's daily counter, on every stored day | Deleted |
| Day totals in `prediction_quota_days` (`total`, `users`) | Kept. Plain numbers with no user ID or email |
| Prediction history (SQLite) | Kept. It never stores who asked |
| API host logs (for example Render's request logs) | Kept for as long as the host retains them. They can include IP addresses. The app's own log lines avoid user IDs and emails, though a third-party error message could include one |
| Google's own Firebase backups and logs | Governed by Google's retention terms, not this app |

Deletion asks the user to sign in again if their last sign-in is over 5 minutes old.

**Troubleshooting:** predictions show "temporarily unavailable" and the API log says
`[Quota] check failed: ValueError: … transaction ID`. That message hides the real
cause, which is usually that the Firestore database doesn't exist yet, or the service
account belongs to a different Firebase project.

---

## Step 2 — Lock down the backend config

In your production environment (not in git), set:

```
GEMINI_API_KEY=...
FOOTBALL_DATA_API_KEY=...
FIREBASE_SERVICE_ACCOUNT_JSON={"type":"service_account", ... }   # whole file, one line
OWNER_EMAILS=you@gmail.com
PREDICTIONS_PER_USER_PER_DAY=3
PREDICTIONS_PER_DAY_TOTAL=50
ALLOWED_ORIGINS=https://your-app.vercel.app
```

Notes:

- `FIREBASE_SERVICE_ACCOUNT_JSON` is the contents of `serviceAccountKey.json`. Use it
  instead of the file path on hosts where you cannot upload a file. Never commit either.
- `OWNER_EMAILS` takes exact emails only, no wildcards. Sign in with that account using
  Google, or verify it, or you'll be treated as an unverified user.
- `ALLOWED_EMAILS` is optional. Leave it unset for a public app. Set it (`*@example.com`
  allows a whole domain) to restrict predictions to those accounts.
- A cap of `0` blocks everyone except owners; it does not mean "no limit".
- `ALLOWED_ORIGINS` should be your exact frontend URL. Unset means any origin.

Users see a clear message in each case: unverified accounts get a verify prompt with a
resend button, blocked accounts get "This account does not have prediction access…",
and users past their cap get "You have used your N predictions for today."

---

## Step 3 — Deploy the API (Render free tier)

1. Push the repo to GitHub.
2. Render → **New → Web Service** → connect the repo.
3. Settings:
   - **Runtime:** Python 3
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - **Instance type:** Free
4. Add every environment variable from Step 2.
5. Deploy, then check `https://<your-api>.onrender.com/health` — it returns
   `{"status":"ok","quota":{...}}`.

The free instance sleeps after ~15 minutes idle and takes ~30 seconds to wake, so the
first prediction after a quiet period is slow. Mention that on the page or accept it.

The prediction history is a SQLite file at `scripts/data/predictions.db`. Free
container disks are ephemeral, so that history resets on redeploy — fine for a demo.
To keep it, attach a persistent disk and point `PREDICTIONS_DB_PATH` at it.

Fly.io and Railway work the same way if you prefer them.

---

## Step 4 — Deploy the frontend (Vercel free tier)

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
Firebase web config. Access is enforced by the backend gates above, not by hiding these.

---

## Step 5 — Optional: make it invite-only

1. They open the link, sign in (Firebase Auth) and verify their email.
2. You add their email to `ALLOWED_EMAILS` on Render and redeploy (~1 minute).
3. To revoke: remove the email, redeploy. Their sign-in still works; predictions stop.

Once `ALLOWED_EMAILS` is set, only listed accounts and owners can predict.

---

## Step 6 — Keep an eye on spend

- `GET /health` shows today's usage: predictions used, distinct users, and the limits
  in force. The usage figures can lag by up to a minute.
- Google AI Studio shows real Gemini usage; set a spending limit there as the backstop.
- football-data.org free tier is 10 requests/minute. The client caches fixtures for
  5 minutes and derives team stats from the standings response, so normal browsing
  stays well under it. Heavy simultaneous use can still hit 429s, which degrade to
  cached or mock data rather than errors.
