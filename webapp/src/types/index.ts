import type { Timestamp } from 'firebase/firestore';
import type { ConfirmationResult } from 'firebase/auth';

export interface User {
  uid: string;
  email: string | null;
  displayName: string | null;
  phoneNumber: string | null;
  photoURL: string | null;
}

export interface AuthContextType {
  user: User | null;
  greenAfricaUser: GreenAfricaUser | null;
  loading: boolean;
  signInWithGoogle: () => Promise<void>;
  signInWithFacebook: () => Promise<void>;
  signInWithPhone: (phoneNumber: string) => Promise<void>;
  verifyPhoneCode: (code: string) => Promise<void>;
  signOut: () => Promise<void>;
  updateProfile: (displayName?: string, phoneNumber?: string) => Promise<void>;
}

export interface GreenAfricaUser {
  uid: string;
  email: string;
  displayName: string;
  phoneNumber?: string;
  greenId: string;
  totalPoints: number;
  referralCode: string;
  referralPoints: number;
  createdAt: Timestamp;
  updatedAt: Timestamp;
}

export interface Transaction {
  id?: string;
  userId: string;
  type: 'earned' | 'redeemed' | 'referral';
  amount: number;
  description: string;
  date: Timestamp;
  location?: string;
  phone?: string;
  referral?: string;
  metadata?: Record<string, unknown>;
}

export interface Referral {
  id?: string;
  referrerUid: string;
  referredUid: string;
  referralCode: string;
  pointsAwarded: number;
  createdAt: Timestamp;
  status: 'pending' | 'completed';
}

export interface RedemptionRequest {
  id?: string;
  userId: string;
  type: 'airtime' | 'data';
  amount: string;
  points: number;
  phone: string;
  network?: string;
  detectedNetwork?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  createdAt: Timestamp;
  completedAt?: Timestamp;
  transactionId?: string;
  apiResponse?: {
    reference?: string;
    responseCode?: number;
    responseMsg?: string;
    status?: string;
    recipient?: string;
    provider?: string;
    errorMessage?: string;
  };
  failureReason?: string;
}

export interface PhoneVerificationState {
  confirmationResult: ConfirmationResult;
  phoneNumber: string;
}

export interface DeviceRequest {
  id?: string;
  name: string;
  email: string;
  phone: string;
  location: string;
  status: 'pending' | 'approved' | 'rejected';
  createdAt: Timestamp;
  updatedAt: Timestamp;
}
