export const RESET_SENT_MESSAGE =
  "If an account exists, we've sent a reset link. Signed up with Google? " +
  "You don't need a password: use Continue with Google above.";

// Failures that depend on the network or on rate limits, never on whether the
// account exists, so reporting them reveals nothing about who has signed up.
const RETRY_MESSAGES: Record<string, string> = {
  "auth/network-request-failed": "Couldn't reach the server. Check your connection and try again.",
  "auth/too-many-requests": "Too many attempts. Wait a few minutes and try again.",
};

/**
 * Request a reset link and return what to show. Every outcome that could depend
 * on the address, including "no such account", gets the same message, and Google
 * accounts are addressed in that message because looking them up would reveal them.
 */
export async function requestPasswordReset(
  email: string,
  send: (email: string) => Promise<void>,
): Promise<{ sent: boolean; message: string }> {
  try {
    await send(email);
  } catch (err: unknown) {
    const retry = RETRY_MESSAGES[(err as { code?: string })?.code ?? ""];
    if (retry) return { sent: false, message: retry };
  }
  return { sent: true, message: RESET_SENT_MESSAGE };
}
