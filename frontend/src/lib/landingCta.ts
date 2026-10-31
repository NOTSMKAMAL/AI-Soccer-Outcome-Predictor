export interface LandingCta {
  /** False until Firebase has restored the session; hide the button rather than flash the wrong one. */
  ready: boolean;
  signedIn: boolean;
  href: string;
  label: string;
}

/**
 * The landing page's call to action. It's a link, never a redirect: sending
 * signed-in users away from "/" automatically would trap the Back button.
 */
export function landingCta(loading: boolean, signedIn: boolean): LandingCta {
  const isSignedIn = !loading && signedIn;
  return {
    ready: !loading,
    signedIn: isSignedIn,
    href: isSignedIn ? "/dashboard" : "/auth",
    label: isSignedIn ? "Go to dashboard" : "Get started",
  };
}
