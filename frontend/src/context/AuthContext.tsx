"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import {
  User,
  UserCredential,
  GoogleAuthProvider,
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
  updateProfile,
} from "firebase/auth";
import { auth } from "@/lib/firebase";

interface AuthContextType {
  user: User | null;
  loading: boolean;
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

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      setUser(firebaseUser);
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
    return cred;
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
      value={{ user, loading, signIn, signUp, signInWithGoogle, logout, updateDisplayName }}
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
