'use server';

import {
  checkUserExists,
  registerRVMOnBlockchain,
  registerUserOnBlockchain,
} from '@/lib/algorand/client';
import { getUserByReferralCodeAdmin } from '@/lib/firebase/admin-firestore';

export interface BlockchainRegistrationResult {
  success: boolean;
  message: string;
  transactionId?: string;
  userExists?: boolean;
  error?: string;
}

/**
 * Register a recycler in the GreenAfrica Algorand application.
 * Firebase remains the identity/profile store; Algorand holds the auditable
 * recycling and reward state keyed by Green ID.
 */
export async function registerUserOnAlgorand(
  greenId: string,
  referralCode: string,
  referredByCode?: string,
): Promise<BlockchainRegistrationResult> {
  try {
    if (!greenId || !referralCode) {
      return {
        success: false,
        message: 'Missing required parameters: greenId and referralCode',
        error: 'Invalid parameters',
      };
    }

    let validatedReferredByCode: string | undefined = referredByCode;
    if (referredByCode) {
      const referrer = await getUserByReferralCodeAdmin(referredByCode);
      if (!referrer) {
        console.warn(`Referral code ${referredByCode} not found; registering without referrer`);
        validatedReferredByCode = undefined;
      }
    }

    const result = await registerUserOnBlockchain(
      greenId,
      referralCode,
      validatedReferredByCode,
    );

    if (!result.success) {
      return {
        success: false,
        message: 'Failed to register recycler on Algorand',
        error: result.error,
      };
    }

    if (result.userExists) {
      return {
        success: true,
        message: 'Recycler already registered on Algorand',
        userExists: true,
      };
    }

    return {
      success: true,
      message: 'Recycler successfully registered on Algorand',
      transactionId: result.transactionId,
      userExists: false,
    };
  } catch (error) {
    console.error('Unexpected Algorand recycler registration error:', error);
    return {
      success: false,
      message: 'Unexpected error during Algorand recycler registration',
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * Register an RVM in the GreenAfrica Algorand application.
 * Location and descriptive metadata remain off-chain; the application stores
 * the machine identifier and activation state used to authorize deposits.
 */
export async function registerRVMOnAlgorand(
  rvmId: string,
  lat: number,
  lng: number,
  name: string,
  metaURI?: string,
): Promise<BlockchainRegistrationResult> {
  try {
    if (!rvmId || !name || lat === undefined || lng === undefined) {
      return {
        success: false,
        message: 'Missing required parameters: rvmId, name, lat, lng',
        error: 'Invalid parameters',
      };
    }

    if (lat < -90 || lat > 90 || lng < -180 || lng > 180) {
      return {
        success: false,
        message: 'Invalid coordinates: lat must be -90 to 90, lng must be -180 to 180',
        error: 'Invalid coordinates',
      };
    }

    const result = await registerRVMOnBlockchain(rvmId, lat, lng, name, metaURI || '');

    if (!result.success) {
      return {
        success: false,
        message: 'Failed to register RVM on Algorand',
        error: result.error,
      };
    }

    return {
      success: true,
      message: result.transactionId
        ? 'RVM successfully registered on Algorand'
        : 'RVM already registered on Algorand',
      transactionId: result.transactionId,
    };
  } catch (error) {
    console.error('Unexpected Algorand RVM registration error:', error);
    return {
      success: false,
      message: 'Unexpected error during Algorand RVM registration',
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

export async function checkUserExistsOnAlgorand(greenId: string): Promise<{
  exists: boolean;
  error?: string;
}> {
  try {
    if (!greenId) {
      return { exists: false, error: 'Green ID is required' };
    }

    return { exists: await checkUserExists(greenId) };
  } catch (error) {
    console.error('Error checking recycler existence on Algorand:', error);
    return {
      exists: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}
