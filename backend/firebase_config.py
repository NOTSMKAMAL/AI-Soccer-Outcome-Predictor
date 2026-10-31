import json
import os

import firebase_admin
from firebase_admin import auth, credentials
from firebase_admin.auth import (
    ExpiredIdTokenError,
    InvalidIdTokenError,
    RevokedIdTokenError,
    UserNotFoundError,
)
from backend.config import FIREBASE_SERVICE_ACCOUNT_PATH

_app: firebase_admin.App | None = None
_init_attempted: bool = False

# Seconds of clock difference tolerated between Google (which stamps the token's
# issued-at time) and this server. The SDK default is 0, so a server clock even
# one second behind rejects a freshly issued token as "Token used too early" —
# and the frontend force-refreshes the token right before every prediction.
# Firebase allows up to 60; 10 covers normal drift between OS time syncs.
TOKEN_CLOCK_SKEW_SECONDS = 10


def _get_app() -> firebase_admin.App | None:
    """Initialize Firebase Admin SDK once and cache the result.

    Tries three strategies in order:
      1. Inline service account JSON (FIREBASE_SERVICE_ACCOUNT_JSON) — the one
         that works on hosts where you can set env vars but not upload a file.
      2. Service account JSON file (FIREBASE_SERVICE_ACCOUNT_PATH in .env,
         default ./serviceAccountKey.json).
      3. Application Default Credentials + FIREBASE_PROJECT_ID env var
         (requires `gcloud auth application-default login` or running on GCP).

    Prints safe diagnostics so the issue is visible in the uvicorn terminal.
    """
    global _app, _init_attempted
    if _app is not None:
        return _app
    if _init_attempted:
        # Already tried and failed — don't spam on every request.
        return None
    _init_attempted = True

    # ── Strategy 1: inline service account JSON (hosting-friendly) ───────────
    inline = (os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON") or "").strip()
    if inline:
        try:
            cred = credentials.Certificate(json.loads(inline))
            _app = firebase_admin.initialize_app(cred)
            print("[Firebase] Initialized from FIREBASE_SERVICE_ACCOUNT_JSON — token verification ready")
            return _app
        except Exception as exc:
            print(f"[Firebase] ERROR initializing from FIREBASE_SERVICE_ACCOUNT_JSON: {exc}")

    # ── Strategy 2: service account JSON file ────────────────────────────────
    sa_path = FIREBASE_SERVICE_ACCOUNT_PATH or "./serviceAccountKey.json"
    sa_exists = os.path.exists(sa_path)
    print(f"[Firebase] Service account path: '{sa_path}', file exists: {sa_exists}")

    if sa_exists:
        try:
            cred = credentials.Certificate(sa_path)
            _app = firebase_admin.initialize_app(cred)
            print("[Firebase] Initialized with service account file — token verification ready")
            return _app
        except Exception as exc:
            print(f"[Firebase] ERROR initializing with service account file: {exc}")

    # ── Strategy 3: Application Default Credentials + project ID ─────────────
    project_id = os.getenv("FIREBASE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    print(
        f"[Firebase] Trying Application Default Credentials, "
        f"FIREBASE_PROJECT_ID set: {bool(project_id)}"
    )
    if project_id:
        try:
            _app = firebase_admin.initialize_app(options={"projectId": project_id})
            print(
                f"[Firebase] Initialized with Application Default Credentials "
                f"(project: {project_id}) — token verification ready"
            )
            return _app
        except Exception as exc:
            print(f"[Firebase] ERROR initializing with Application Default Credentials: {exc}")

    # ── No strategy worked ────────────────────────────────────────────────────
    print(
        "[Firebase] CRITICAL: Firebase Admin SDK could not be initialized.\n"
        "  Token verification will reject ALL requests with 401.\n"
        "  Fix ONE of the following:\n"
        "  Option A (local): Download serviceAccountKey.json from Firebase Console\n"
        "    → Firebase Console → Project Settings → Service Accounts\n"
        "    → 'Generate new private key' → save as ./serviceAccountKey.json\n"
        "  Option B (hosting): paste that same JSON into FIREBASE_SERVICE_ACCOUNT_JSON\n"
        "  Option C: Set FIREBASE_PROJECT_ID=your-project-id in .env\n"
        "    then run: gcloud auth application-default login"
    )
    return None


def _log_verify_failure(exc: Exception, token: str) -> None:
    """Print why a token was rejected, without ever printing the token itself.

    Every failure surfaces to the client as the same 401, so this line in the
    uvicorn terminal is the only way to tell a bad token from a broken server
    (wrong project, bad service account key, clock skew, network).
    """
    message = str(exc).replace(token, "<token>")
    print(f"[Firebase] Token verification failed: {type(exc).__name__}: {message}")


def verify_id_token(token: str) -> dict | None:
    """Verify a Firebase ID token and return the decoded claims, or None on failure.

    Failures are logged server-side (exception type and message, never the token).
    """
    if not token:
        return None
    app = _get_app()
    if app is None:
        return None
    try:
        decoded = auth.verify_id_token(
            token, app=app, check_revoked=True, clock_skew_seconds=TOKEN_CLOCK_SKEW_SECONDS
        )
        return decoded
    except (ExpiredIdTokenError, InvalidIdTokenError, RevokedIdTokenError) as exc:
        _log_verify_failure(exc, token)
        return None
    except Exception as exc:
        _log_verify_failure(exc, token)
        return None


def get_user_by_uid(uid: str) -> dict | None:
    """Fetch a Firebase user record by UID, or None if not found."""
    app = _get_app()
    if app is None:
        return None
    try:
        user = auth.get_user(uid, app=app)
        return {
            "uid": user.uid,
            "email": user.email,
            "display_name": user.display_name,
            "email_verified": user.email_verified,
            "disabled": user.disabled,
        }
    except UserNotFoundError:
        return None
    except Exception:
        return None
