"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import {
  User,
  UserCredential,
  GoogleAuthProvider,
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  sendEmailVerification,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
  updateProfile,
} from "firebase/auth";
import { auth } from "@/lib/firebase";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  emailVerified: boolean;
  resendVerificationEmail: () => Promise<void>;
  refreshEmailVerified: () => Promise<boolean>;
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

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      setUser(firebaseUser);
      setEmailVerified(firebaseUser?.emailVerified ?? false);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  const signIn = (email: string, password: string) =>
    signInWithEmailAndPassword(auth, email, password);

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

  const logout = () => signOut(auth);

  const updateDisplayName = async (displayName: string) => {
    if (!auth.currentUser) throw new Error("No user signed in.");
    await updateProfile(auth.currentUser, { displayName });
    setUser((prev) => prev ? { ...prev, displayName } as User : prev);
  };

  return (
    <AuthContext.Provider
      value={{
        user, loading, emailVerified, resendVerificationEmail, refreshEmailVerified,
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
