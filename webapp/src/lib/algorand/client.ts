'use server';

import { createHash } from 'node:crypto';
import { AlgorandClient } from '@algorandfoundation/algokit-utils';
import algosdk from 'algosdk';

export interface BlockchainResult {
  success: boolean;
  transactionId?: string;
  userExists?: boolean;
  error?: string;
}

export interface RecyclerState {
  points: bigint;
  totalPet: bigint;
}

const APP_ENV = 'ALGORAND_GREENAFRICA_APP_ID';
const OPERATOR_ENV = 'GREENAFRICA_OPERATOR_MNEMONIC';

function makeAlgorandClient(): AlgorandClient {
  const network = (process.env.ALGORAND_NETWORK || 'testnet').toLowerCase();

  // Custom Algod/Indexer endpoints take priority when configured.
  if (process.env.ALGOD_SERVER || process.env.INDEXER_SERVER) {
    return AlgorandClient.fromEnvironment();
  }

  if (network === 'mainnet') {
    return AlgorandClient.mainNet();
  }

  if (network === 'localnet') {
    return AlgorandClient.defaultLocalNet();
  }

  return AlgorandClient.testNet();
}

function getAppId(): bigint {
  const raw = process.env[APP_ENV];
  if (!raw) {
    throw new Error(`${APP_ENV} is not configured`);
  }

  try {
    return BigInt(raw);
  } catch {
    throw new Error(`${APP_ENV} must be a valid Algorand application ID`);
  }
}

function toBytes(value: string): Uint8Array {
  return new TextEncoder().encode(value);
}

function hashBytes(value: string): Uint8Array {
  return new Uint8Array(createHash('sha256').update(value).digest());
}

async function getContext() {
  if (!process.env[OPERATOR_ENV]) {
    throw new Error(`${OPERATOR_ENV} is not configured`);
  }

  const algorand = makeAlgorandClient();
  // AccountManager automatically registers this signer with AlgorandClient.
  const operator = await algorand.account.fromEnvironment('GREENAFRICA_OPERATOR');

  return {
    algorand,
    operator,
    appId: getAppId(),
  };
}

async function callMethod(
  signature: string,
  args: unknown[],
): Promise<{ transactionId: string; returnValue?: unknown }> {
  const { algorand, operator, appId } = await getContext();
  const method = algosdk.ABIMethod.fromSignature(signature);

  const result = await algorand
    .newGroup()
    .addAppCallMethodCall({
      sender: operator,
      appId,
      method,
      args,
    })
    .send({ populateAppCallResources: true });

  return {
    transactionId: result.txIds[0],
    returnValue: result.returns?.[0]?.returnValue,
  };
}

function isAlreadyRegisteredError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return message.includes('Recycler exists');
}

export async function registerUserOnBlockchain(
  greenId: string,
  _referralCode?: string,
  _referredByCode?: string,
): Promise<BlockchainResult> {
  try {
    if (await checkUserExists(greenId)) {
      return { success: true, userExists: true };
    }

    const result = await callMethod('registerRecycler(byte[])void', [toBytes(greenId)]);
    return {
      success: true,
      transactionId: result.transactionId,
      userExists: false,
    };
  } catch (error) {
    if (isAlreadyRegisteredError(error)) {
      return { success: true, userExists: true };
    }

    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to register recycler on Algorand',
    };
  }
}

export async function checkUserExists(greenId: string): Promise<boolean> {
  try {
    const result = await callMethod('isRecyclerRegistered(byte[])bool', [toBytes(greenId)]);
    return result.returnValue === true;
  } catch (error) {
    console.error('Error checking recycler on Algorand:', error);
    return false;
  }
}

export async function registerRVMOnBlockchain(
  rvmId: string,
  _lat?: number,
  _lng?: number,
  _name?: string,
  _metaURI?: string,
): Promise<BlockchainResult> {
  try {
    const result = await callMethod('registerRvm(byte[])void', [toBytes(rvmId)]);
    return { success: true, transactionId: result.transactionId };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (message.includes('RVM exists')) {
      return { success: true };
    }

    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to register RVM on Algorand',
    };
  }
}

export async function recordDepositOnAlgorand(
  recyclerId: string,
  rvmId: string,
  petCount: number,
  pointsAwarded: number,
  receiptPayload: string,
  sessionId: string,
): Promise<BlockchainResult> {
  try {
    const result = await callMethod(
      'recordDeposit(byte[],byte[],uint64,uint64,byte[],byte[])(uint64,uint64)',
      [
        toBytes(recyclerId),
        toBytes(rvmId),
        BigInt(petCount),
        BigInt(pointsAwarded),
        toBytes(sessionId),
        hashBytes(receiptPayload),
      ],
    );

    return { success: true, transactionId: result.transactionId };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to record deposit on Algorand',
    };
  }
}

export async function redeemPointsOnAlgorand(
  recyclerId: string,
  points: number,
  rewardType: string,
  destination: string,
  redemptionId: string,
): Promise<BlockchainResult> {
  try {
    const result = await callMethod(
      'redeemPoints(byte[],uint64,byte[],byte[])uint64',
      [
        toBytes(recyclerId),
        BigInt(points),
        toBytes(redemptionId),
        hashBytes(`${rewardType}:${destination}`),
      ],
    );

    return { success: true, transactionId: result.transactionId };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to redeem points on Algorand',
    };
  }
}

export async function adjustPointsOnAlgorand(
  recyclerId: string,
  points: number,
  add: boolean,
): Promise<BlockchainResult> {
  try {
    const result = await callMethod('adjustPoints(byte[],uint64,bool)uint64', [
      toBytes(recyclerId),
      BigInt(points),
      add,
    ]);
    return { success: true, transactionId: result.transactionId };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to adjust points on Algorand',
    };
  }
}

export async function getRecyclerOnAlgorand(greenId: string): Promise<RecyclerState | null> {
  try {
    const result = await callMethod('getRecycler(byte[])(uint64,uint64)', [toBytes(greenId)]);
    const value = result.returnValue;

    if (!Array.isArray(value) || value.length < 2) {
      return null;
    }

    return {
      points: BigInt(value[0] as bigint | number | string),
      totalPet: BigInt(value[1] as bigint | number | string),
    };
  } catch (error) {
    console.error('Error reading recycler from Algorand:', error);
    return null;
  }
}

export async function isBlockchainConfigured(): Promise<boolean> {
  return Boolean(process.env[APP_ENV] && process.env[OPERATOR_ENV]);
}
