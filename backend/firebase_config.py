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


def _get_app() -> firebase_admin.App | None:
    """Initialize Firebase Admin SDK once and cache the result.

    Tries two strategies in order:
      1. Service account JSON file (FIREBASE_SERVICE_ACCOUNT_PATH in .env,
         default ./serviceAccountKey.json).
      2. Application Default Credentials + FIREBASE_PROJECT_ID env var
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

    # ── Strategy 1: service account JSON file ────────────────────────────────
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

    # ── Strategy 2: Application Default Credentials + project ID ─────────────
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

    # ── Neither strategy worked ───────────────────────────────────────────────
    print(
        "[Firebase] CRITICAL: Firebase Admin SDK could not be initialized.\n"
        "  Token verification will reject ALL requests with 401.\n"
        "  Fix ONE of the following:\n"
        "  Option A (recommended): Download serviceAccountKey.json from Firebase Console\n"
        "    → Firebase Console → Project Settings → Service Accounts\n"
        "    → 'Generate new private key' → save as ./serviceAccountKey.json\n"
        "  Option B: Set FIREBASE_PROJECT_ID=your-project-id in .env\n"
        "    then run: gcloud auth application-default login"
    )
    return None


def verify_id_token(token: str) -> dict | None:
    """Verify a Firebase ID token and return the decoded claims, or None on failure."""
    if not token:
        return None
    app = _get_app()
    if app is None:
        return None
    try:
        decoded = auth.verify_id_token(token, app=app, check_revoked=True)
        return decoded
    except (ExpiredIdTokenError, InvalidIdTokenError, RevokedIdTokenError):
        return None
    except Exception:
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
