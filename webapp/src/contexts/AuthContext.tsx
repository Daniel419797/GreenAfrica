'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { User, RecaptchaVerifier } from 'firebase/auth';
import { Timestamp } from 'firebase/firestore';
import {
  signInWithGoogle,
  signInWithFacebook,
  sendPhoneVerification,
  verifyPhoneCode,
  signOutUser,
  onAuthStateChange,
  updateUserProfile,
  createRecaptchaVerifier,
} from '@/lib/firebase/auth';
import {
  createUser,
  getUser,
  updateUser,
  subscribeToUser,
  processReferral,
  type GreenAfricaUser,
} from '@/lib/firebase/firestore';
import { registerUserOnAlgorand } from '@/actions/blockchain';
import { AuthContextType, PhoneVerificationState } from '@/types';

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: React.ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [greenAfricaUser, setGreenAfricaUser] = useState<GreenAfricaUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [phoneVerification, setPhoneVerification] = useState<PhoneVerificationState | null>(null);
  const [recaptchaVerifier, setRecaptchaVerifier] = useState<RecaptchaVerifier | null>(null);

  const initializeRecaptcha = () => {
    if (typeof window !== 'undefined' && !recaptchaVerifier) {
      const verifier = createRecaptchaVerifier('recaptcha-container');
      setRecaptchaVerifier(verifier);
      return verifier;
    }
    return recaptchaVerifier;
  };

  const handleUserData = async (firebaseUser: User, referralCode?: string) => {
    try {
      let userData = await getUser(firebaseUser.uid);

      if (!userData) {
        userData = await createUser(
          firebaseUser.uid,
          firebaseUser.email || '',
          firebaseUser.displayName || 'Anonymous User',
          firebaseUser.phoneNumber || undefined,
        );

        if (referralCode) {
          await processReferral(referralCode, firebaseUser.uid);
        }
      } else {
        const updates: Partial<GreenAfricaUser> = {};
        if (firebaseUser.displayName && firebaseUser.displayName !== userData.displayName) {
          updates.displayName = firebaseUser.displayName;
        }
        if (firebaseUser.phoneNumber && firebaseUser.phoneNumber !== userData.phoneNumber) {
          updates.phoneNumber = firebaseUser.phoneNumber;
        }

        if (Object.keys(updates).length > 0) {
          await updateUser(firebaseUser.uid, updates);
          userData = await getUser(firebaseUser.uid);
        }
      }

      if (userData) {
        try {
          const blockchainResult = await registerUserOnAlgorand(
            userData.greenId,
            userData.referralCode,
            referralCode,
          );

          if (!blockchainResult.success) {
            console.warn(
              `Algorand registration failed for ${userData.greenId}:`,
              blockchainResult.error,
            );
          }
        } catch (blockchainError) {
          console.error('Algorand registration error:', blockchainError);
        }

        setGreenAfricaUser(userData);
      }
    } catch (error) {
      console.error('Error handling user data:', error);

      if (error instanceof Error && error.message.includes('permission-denied')) {
        const fallbackUser: GreenAfricaUser = {
          uid: firebaseUser.uid,
          email: firebaseUser.email || '',
          displayName: firebaseUser.displayName || 'User',
          phoneNumber: firebaseUser.phoneNumber || undefined,
          greenId: 'GRN-TEMP-' + Date.now(),
          totalPoints: 0,
          referralCode: 'TEMP' + Date.now(),
          referralPoints: 0,
          createdAt: Timestamp.fromDate(new Date()),
          updatedAt: Timestamp.fromDate(new Date()),
        };
        setGreenAfricaUser(fallbackUser);
      }
    }
  };

  useEffect(() => {
    const unsubscribe = onAuthStateChange(async (firebaseUser) => {
      setUser(firebaseUser);

      if (firebaseUser) {
        const referralCode = localStorage.getItem('referralCode');
        if (referralCode) {
          localStorage.removeItem('referralCode');
        }
        await handleUserData(firebaseUser, referralCode || undefined);
      } else {
        setGreenAfricaUser(null);
      }

      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  useEffect(() => {
    let unsubscribe: (() => void) | null = null;

    if (user?.uid) {
      unsubscribe = subscribeToUser(user.uid, (userData) => {
        setGreenAfricaUser(userData);
      });
    }

    return () => {
      if (unsubscribe) unsubscribe();
    };
  }, [user?.uid]);

  const handleSignInWithGoogle = async () => {
    try {
      setLoading(true);
      await signInWithGoogle();
    } finally {
      setLoading(false);
    }
  };

  const handleSignInWithFacebook = async () => {
    try {
      setLoading(true);
      await signInWithFacebook();
    } finally {
      setLoading(false);
    }
  };

  const handleSignInWithPhone = async (phoneNumber: string) => {
    try {
      setLoading(true);
      const verifier = initializeRecaptcha();
      if (!verifier) throw new Error('Failed to initialize reCAPTCHA');

      const confirmationResult = await sendPhoneVerification(phoneNumber, verifier);
      setPhoneVerification({ confirmationResult, phoneNumber });
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyPhoneCode = async (code: string) => {
    try {
      if (!phoneVerification?.confirmationResult) {
        throw new Error('No phone verification in progress');
      }

      setLoading(true);
      await verifyPhoneCode(phoneVerification.confirmationResult, code);
      setPhoneVerification(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSignOut = async () => {
    try {
      setLoading(true);
      await signOutUser();
      setPhoneVerification(null);
      if (recaptchaVerifier) {
        recaptchaVerifier.clear();
        setRecaptchaVerifier(null);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateProfile = async (displayName?: string, phoneNumber?: string) => {
    if (!user) throw new Error('No user is currently signed in');

    try {
      setLoading(true);

      if (displayName !== undefined) {
        await updateUserProfile(displayName);
      }

      const updates: Partial<GreenAfricaUser> = {};
      if (displayName !== undefined) updates.displayName = displayName;
      if (phoneNumber !== undefined) updates.phoneNumber = phoneNumber;

      if (Object.keys(updates).length > 0) {
        await updateUser(user.uid, updates);
      }
    } finally {
      setLoading(false);
    }
  };

  const value: AuthContextType = {
    user,
    greenAfricaUser,
    loading,
    signInWithGoogle: handleSignInWithGoogle,
    signInWithFacebook: handleSignInWithFacebook,
    signInWithPhone: handleSignInWithPhone,
    verifyPhoneCode: handleVerifyPhoneCode,
    signOut: handleSignOut,
    updateProfile: handleUpdateProfile,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
      <div id="recaptcha-container" style={{ display: 'none' }} />
    </AuthContext.Provider>
  );
};

export default AuthContext;
