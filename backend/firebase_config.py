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


def _get_app() -> firebase_admin.App | None:
    global _app
    if _app is not None:
        return _app
    sa_path = FIREBASE_SERVICE_ACCOUNT_PATH
    if not sa_path or not os.path.exists(sa_path):
        return None
    try:
        cred = credentials.Certificate(sa_path)
        _app = firebase_admin.initialize_app(cred)
    except Exception:
        _app = None
    return _app


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
