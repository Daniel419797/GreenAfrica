'use server';

import {
  adjustPointsOnAlgorand,
  getRecyclerOnAlgorand,
  recordDepositOnAlgorand,
  redeemPointsOnAlgorand,
} from '@/lib/algorand/client';
import { getUserAdmin } from '@/lib/firebase/admin-firestore';

export interface GreenPointsResult {
  success: boolean;
  message?: string;
  transactionHash?: string;
  balance?: string;
  error?: string;
}

/**
 * Award Green Points for an accepted recycling session.
 * Algorand application state is the authoritative blockchain balance.
 */
export async function mintPointsForUser(
  uid: string,
  points: number,
  sessionId?: string,
): Promise<GreenPointsResult> {
  try {
    if (!uid || points <= 0) {
      return { success: false, error: 'Invalid parameters: uid and positive points required' };
    }

    const user = await getUserAdmin(uid);
    if (!user) {
      return { success: false, error: 'User not found' };
    }

    const finalSessionId =
      sessionId || `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;
    const rvmId = process.env.GREENAFRICA_DEFAULT_RVM_ID || 'RVM-IFITNESS-ORCHID-001';

    const result = await recordDepositOnAlgorand(
      user.greenId,
      rvmId,
      points,
      points,
      `${user.greenId}:${finalSessionId}`,
      finalSessionId,
    );

    if (!result.success) {
      return {
        success: false,
        error: `Failed to record Green Points on Algorand: ${result.error}`,
      };
    }

    return {
      success: true,
      message: `Successfully awarded ${points} Green Points on Algorand`,
      transactionHash: result.transactionId,
    };
  } catch (error) {
    console.error('Error awarding Green Points on Algorand:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to award Green Points',
    };
  }
}

/**
 * Deduct Green Points for a redemption through the Algorand application.
 */
export async function burnPointsForUser(
  uid: string,
  points: number,
  rewardType: string,
  destination: string,
  redemptionId: string,
): Promise<GreenPointsResult> {
  try {
    if (!uid || points <= 0 || !rewardType || !destination || !redemptionId) {
      return { success: false, error: 'Invalid parameters: all fields are required' };
    }

    const user = await getUserAdmin(uid);
    if (!user) {
      return { success: false, error: 'User not found' };
    }

    const state = await getRecyclerOnAlgorand(user.greenId);
    if (!state) {
      return { success: false, error: 'Recycler not found in Algorand application' };
    }

    if (state.points < BigInt(points)) {
      return {
        success: false,
        error: `Insufficient balance. Current: ${state.points}, Required: ${points}`,
      };
    }

    const result = await redeemPointsOnAlgorand(
      user.greenId,
      points,
      rewardType,
      destination,
      redemptionId,
    );

    if (!result.success) {
      return {
        success: false,
        error: `Failed to redeem Green Points on Algorand: ${result.error}`,
      };
    }

    return {
      success: true,
      message: `Successfully redeemed ${points} Green Points on Algorand`,
      transactionHash: result.transactionId,
    };
  } catch (error) {
    console.error('Error redeeming Green Points on Algorand:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to redeem Green Points',
    };
  }
}

export async function adjustPointsForUser(
  uid: string,
  points: number,
  add: boolean,
): Promise<GreenPointsResult> {
  try {
    if (!uid || points <= 0) {
      return { success: false, error: 'Invalid parameters' };
    }

    const user = await getUserAdmin(uid);
    if (!user) {
      return { success: false, error: 'User not found' };
    }

    const result = await adjustPointsOnAlgorand(user.greenId, points, add);
    return result.success
      ? {
          success: true,
          message: `Green Points ${add ? 'added' : 'deducted'} on Algorand`,
          transactionHash: result.transactionId,
        }
      : { success: false, error: result.error };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to adjust Green Points',
    };
  }
}

export async function getUserPointsFromBlockchain(uid: string): Promise<GreenPointsResult> {
  try {
    if (!uid) {
      return { success: false, error: 'User ID is required' };
    }

    const user = await getUserAdmin(uid);
    if (!user) {
      return { success: false, error: 'User not found' };
    }

    const state = await getRecyclerOnAlgorand(user.greenId);
    if (!state) {
      return { success: false, error: 'Recycler not found in Algorand application' };
    }

    return {
      success: true,
      balance: state.points.toString(),
      message: `Current balance: ${state.points} Green Points`,
    };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to get Green Points balance',
    };
  }
}

export async function getPointsBalanceByGreenId(greenId: string): Promise<GreenPointsResult> {
  try {
    if (!greenId) {
      return { success: false, error: 'Green ID is required' };
    }

    const state = await getRecyclerOnAlgorand(greenId);
    if (!state) {
      return { success: false, error: 'Recycler not found in Algorand application' };
    }

    return {
      success: true,
      balance: state.points.toString(),
      message: `Current balance: ${state.points} Green Points`,
    };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to get Green Points balance',
    };
  }
}

export async function getUserPointsComparison(uid: string): Promise<{
  blockchainPoints: GreenPointsResult;
  firestorePoints: { success: boolean; points?: number; error?: string };
}> {
  try {
    const user = await getUserAdmin(uid);
    if (!user) {
      return {
        blockchainPoints: { success: false, error: 'User not found' },
        firestorePoints: { success: false, error: 'User not found' },
      };
    }

    return {
      blockchainPoints: await getUserPointsFromBlockchain(uid),
      firestorePoints: { success: true, points: user.totalPoints },
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return {
      blockchainPoints: { success: false, error: message },
      firestorePoints: { success: false, error: message },
    };
  }
}
