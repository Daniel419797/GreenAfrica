#!/usr/bin/env tsx

/**
 * Register the iFitness Orchid reverse vending machine in GreenAfrica's
 * Algorand application.
 *
 * Usage:
 *   npm run register-rvm -- --confirm
 */

import dotenv from 'dotenv';
dotenv.config({ path: '.env.local' });

import { registerRVMOnAlgorand } from '../src/actions/blockchain';

const RVM_DATA = {
  rvmId: 'RVM-IFITNESS-ORCHID-001',
  latitude: 6.433402,
  longitude: 3.541907,
  name: 'iFitness Orchid',
  metaURI: '',
};

function checkEnvironment() {
  console.log('Environment check');
  console.log(`  ALGORAND_NETWORK: ${process.env.ALGORAND_NETWORK || 'testnet'}`);
  console.log(
    `  ALGORAND_GREENAFRICA_APP_ID: ${process.env.ALGORAND_GREENAFRICA_APP_ID ? 'set' : 'missing'}`,
  );
  console.log(
    `  GREENAFRICA_OPERATOR_MNEMONIC: ${process.env.GREENAFRICA_OPERATOR_MNEMONIC ? 'set' : 'missing'}`,
  );
  console.log(`  ALGOD_SERVER: ${process.env.ALGOD_SERVER || 'AlgoKit network default'}`);
  console.log('');

  if (!process.env.ALGORAND_GREENAFRICA_APP_ID) {
    throw new Error('ALGORAND_GREENAFRICA_APP_ID is required');
  }
  if (!process.env.GREENAFRICA_OPERATOR_MNEMONIC) {
    throw new Error('GREENAFRICA_OPERATOR_MNEMONIC is required');
  }
}

async function registerRVM() {
  console.log('Registering RVM on Algorand');
  console.log(`  ID: ${RVM_DATA.rvmId}`);
  console.log(`  Name: ${RVM_DATA.name}`);
  console.log(`  Location: ${RVM_DATA.latitude}, ${RVM_DATA.longitude}`);

  const result = await registerRVMOnAlgorand(
    RVM_DATA.rvmId,
    RVM_DATA.latitude,
    RVM_DATA.longitude,
    RVM_DATA.name,
    RVM_DATA.metaURI,
  );

  if (!result.success) {
    throw new Error(result.error || result.message);
  }

  console.log(result.message);
  if (result.transactionId) {
    console.log(`Algorand transaction ID: ${result.transactionId}`);
  }
}

async function main() {
  checkEnvironment();

  const shouldProceed = process.argv.includes('--confirm') || process.argv.includes('-y');
  if (!shouldProceed) {
    console.log('Registration cancelled. Re-run with --confirm or -y.');
    return;
  }

  await registerRVM();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
