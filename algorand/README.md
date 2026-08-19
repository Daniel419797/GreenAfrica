# GreenAfrica on Algorand

This module adds Algorand as a second blockchain rail for GreenAfrica while keeping the existing Hedera implementation intact.

## Purpose

The Algorand application mirrors the core recycling accounting data needed for independent verification:

- register and activate reverse vending machines (RVMs)
- register recycler Green IDs without requiring user wallets
- record PET deposits and awarded Green Points
- prevent duplicate recycling sessions
- record reward redemptions
- emit ARC-28 compatible events that indexers and analytics services can consume

The application creator acts as the authorized writer. This matches GreenAfrica's existing model where the backend/RVM operator submits blockchain transactions on behalf of recyclers.

## Architecture

```text
RVM / camera
    |
    v
rvm_api
    |
    +--------------------+
    |                    |
    v                    v
Hedera              Algorand
    |                    |
    |              ARC-4 application
    |              + ARC-28 events
    |                    |
    +----------+---------+
               |
               v
       GreenAfrica webapp
       + sponsor analytics
```

Hedera can continue handling the currently deployed contract, HTS Green Points and HCS audit trail. Algorand provides an additional independently verifiable application state and event stream. A future production phase can also issue Green Points as an Algorand Standard Asset (ASA) if GreenAfrica wants rewards to exist natively on both chains.

## Smart contract

`src/GreenAfrica.algo.ts` is an Algorand TypeScript smart contract compiled for the Algorand Virtual Machine (AVM) with PuyaTS.

Core methods:

- `registerRvm(rvmId)`
- `setRvmActive(rvmId, active)`
- `registerRecycler(recyclerId)`
- `recordDeposit(recyclerId, rvmId, petCount, pointsAwarded, sessionId, receiptHash)`
- `redeemPoints(recyclerId, pointsToRedeem, redemptionId, destinationHash)`
- `adjustPoints(recyclerId, delta, add)`
- `getRecycler(recyclerId)`
- `isRvmActive(rvmId)`
- `isSessionRecorded(sessionId)`

Sensitive information should be hashed before being supplied to the contract. Do not store phone numbers, email addresses or full media URLs directly on-chain.

## Build

Requirements:

- Node.js 22+
- npm 10+

Install and compile:

```bash
cd algorand
npm install
npm run build
```

The build generates TEAL and ARC application specifications under the `artifacts` output directory.

You can also compile with AlgoKit:

```bash
algokit compile typescript src/GreenAfrica.algo.ts --out-dir artifacts
```

## Deployment plan

1. Start on Algorand LocalNet and compile the contract.
2. Run contract tests for RVM registration, duplicate-session protection, deposits and redemptions.
3. Deploy the application to Algorand TestNet.
4. Store the resulting application ID as `ALGORAND_GREENAFRICA_APP_ID` in the server environment.
5. Add an operator signer in the backend/RVM service.
6. Dual-write each accepted recycling receipt to Hedera and Algorand using the same `sessionId` and receipt hash.
7. Query Algorand Indexer for sponsor dashboards and cross-chain reconciliation.
8. Move to MainNet only after reconciliation and failure-handling tests pass.

## Recommended environment variables

```bash
ALGORAND_NETWORK=testnet
ALGORAND_ALGOD_URL=
ALGORAND_ALGOD_TOKEN=
ALGORAND_INDEXER_URL=
ALGORAND_INDEXER_TOKEN=
ALGORAND_OPERATOR_MNEMONIC=
ALGORAND_GREENAFRICA_APP_ID=
ALGORAND_GREENPOINTS_ASSET_ID=
```

Keep `ALGORAND_OPERATOR_MNEMONIC` server-side only. Never expose it through `NEXT_PUBLIC_*` variables.
