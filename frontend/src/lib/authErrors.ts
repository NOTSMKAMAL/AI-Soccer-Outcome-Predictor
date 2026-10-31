const MESSAGES: Record<string, string> = {
  "auth/invalid-credential": "That email or password isn't right. Check them and try again, or use Forgot?",
  "auth/invalid-login-credentials": "That email or password isn't right. Check them and try again, or use Forgot?",
  "auth/wrong-password": "That email or password isn't right. Check them and try again, or use Forgot?",
  "auth/user-not-found": "That email or password isn't right. Check them and try again, or use Forgot?",
  "auth/email-already-in-use": "That email already has an account. Sign in instead.",
  "auth/invalid-email": "Enter a valid email address.",
  "auth/weak-password": "Choose a password with at least 6 characters.",
  "auth/popup-closed-by-user": "Google sign-in was closed before it finished. Try again when you're ready.",
  "auth/cancelled-popup-request": "Google sign-in was closed before it finished. Try again when you're ready.",
  "auth/popup-blocked": "Your browser blocked the Google window. Allow pop-ups for this site and try again.",
  "auth/too-many-requests": "Too many attempts. Wait a few minutes and try again.",
  "auth/network-request-failed": "We can't reach the sign-in service. Check your connection and try again.",
};

const FALLBACK = "We couldn't sign you in. Check your connection and try again.";

/** A sentence for the sign-in page. Firebase's own messages name error codes, not next steps. */
export function describeAuthError(err: unknown): string {
  return MESSAGES[(err as { code?: string })?.code ?? ""] ?? FALLBACK;
}
