"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import {
  EmailAuthProvider,
  User,
  UserCredential,
  GoogleAuthProvider,
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  reauthenticateWithCredential,
  reauthenticateWithPopup,
  sendEmailVerification,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
  updateProfile,
} from "firebase/auth";
import { auth } from "@/lib/firebase";
import { deleteMyAccount } from "@/lib/api";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  emailVerified: boolean;
  /** True after this tab deleted its account, so the sign-in page can confirm it. */
  accountDeleted: boolean;
  /** True from pressing Sign out until the next sign-in, so every redirect goes to the landing page. */
  signedOut: boolean;
  resendVerificationEmail: () => Promise<void>;
  refreshEmailVerified: () => Promise<boolean>;
  resetPassword: (email: string) => Promise<void>;
  hasPasswordSignIn: () => boolean;
  reauthenticate: (password?: string) => Promise<void>;
  deleteAccount: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<UserCredential>;
  signUp: (email: string, password: string, displayName?: string) => Promise<UserCredential>;
  signInWithGoogle: () => Promise<UserCredential>;
  logout: () => Promise<void>;
  updateDisplayName: (displayName: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [emailVerified, setEmailVerified] = useState(false);
  const [accountDeleted, setAccountDeleted] = useState(false);
  const [signedOut, setSignedOut] = useState(false);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      setUser(firebaseUser);
      setEmailVerified(firebaseUser?.emailVerified ?? false);
      if (firebaseUser) setSignedOut(false);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  const signIn = (email: string, password: string) =>
    signInWithEmailAndPassword(auth, email, password);

  const resetPassword = (email: string) => sendPasswordResetEmail(auth, email);

  const hasPasswordSignIn = () =>
    auth.currentUser?.providerData.some((p) => p.providerId === "password") ?? false;

  /** Re-confirm identity: with `password` for password accounts, otherwise via Google. */
  const reauthenticate = async (password?: string) => {
    const current = auth.currentUser;
    if (!current) throw new Error("No user signed in.");
    if (password !== undefined) {
      await reauthenticateWithCredential(
        current,
        EmailAuthProvider.credential(current.email ?? "", password),
      );
    } else {
      await reauthenticateWithPopup(current, new GoogleAuthProvider());
    }
  };

  const deleteAccount = async () => {
    if (!auth.currentUser) throw new Error("No user signed in.");
    await deleteMyAccount(await auth.currentUser.getIdToken(true));
    setAccountDeleted(true);
    await signOut(auth);
  };

  const signUp = async (email: string, password: string, displayName?: string) => {
    const cred = await createUserWithEmailAndPassword(auth, email, password);
    if (displayName?.trim()) {
      await updateProfile(cred.user, { displayName: displayName.trim() });
      setUser({ ...cred.user, displayName: displayName.trim() } as User);
    }
    // The account already exists, so a failed send must not fail sign-up;
    // the prediction page offers a resend.
    await sendEmailVerification(cred.user).catch(() => undefined);
    return cred;
  };

  const resendVerificationEmail = async () => {
    if (!auth.currentUser) throw new Error("No user signed in.");
    await sendEmailVerification(auth.currentUser);
  };

  // Clicking the emailed link happens outside this tab, so the local user is stale
  // until reloaded. The next forced token refresh then carries the new claim.
  const refreshEmailVerified = async () => {
    if (!auth.currentUser) return false;
    await auth.currentUser.reload();
    const verified = auth.currentUser.emailVerified;
    // signUp stores a plain copy without getIdToken; predicting needs the real user.
    setUser(auth.currentUser);
    setEmailVerified(verified);
    return verified;
  };

  const signInWithGoogle = () =>
    signInWithPopup(auth, new GoogleAuthProvider());

  const logout = async () => {
    setSignedOut(true);
    try {
      await signOut(auth);
    } catch (err) {
      setSignedOut(false);
      throw err;
    }
  };

  const updateDisplayName = async (displayName: string) => {
    if (!auth.currentUser) throw new Error("No user signed in.");
    await updateProfile(auth.currentUser, { displayName });
    setUser((prev) => prev ? { ...prev, displayName } as User : prev);
  };

  return (
    <AuthContext.Provider
      value={{
        user, loading, emailVerified, accountDeleted, signedOut,
        resendVerificationEmail, refreshEmailVerified,
        resetPassword, hasPasswordSignIn, reauthenticate, deleteAccount,
        signIn, signUp, signInWithGoogle, logout, updateDisplayName,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
