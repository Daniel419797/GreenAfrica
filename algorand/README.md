# GreenAfrica on Algorand

Algorand is the only blockchain used by GreenAfrica.

The Algorand application is the authoritative on-chain layer for reverse vending machine registration, recycler accounting, bottle-deposit receipts, Green Points balances and redemptions.

## What is stored on-chain

- active/inactive RVM registry
- recycler Green IDs as opaque identifiers
- lifetime PET counts
- Green Points balances
- unique recycling session IDs to prevent duplicate rewards
- unique redemption IDs to prevent duplicate redemption
- hashes of receipt/media payloads
- ARC-28 compatible events for independent analytics and audit trails

Users do not need individual blockchain wallets. GreenAfrica uses a server-managed operator account to submit application calls after the RVM or webapp has authenticated the action.

## Architecture

```text
Recycler
   |
   v
Reverse vending machine / camera
   |
   v
rvm_api + computer vision
   |
   | accepted recycling session
   v
GreenAfrica backend
   |
   v
Algorand application
   |-- RVM registry
   |-- recycler points
   |-- PET totals
   |-- duplicate-session protection
   |-- redemption accounting
   `-- ARC-28 event logs
   |
   +-------------------+
   |                   |
   v                   v
Algorand Indexer   Firebase / webapp
   |                   |
   `-------> sponsor and recycler dashboards
```

## Smart contract

`src/GreenAfrica.algo.ts` is an Algorand TypeScript smart contract compiled for the Algorand Virtual Machine with PuyaTS.

Core methods:

- `registerRvm(rvmId)`
- `setRvmActive(rvmId, active)`
- `registerRecycler(recyclerId)`
- `recordDeposit(recyclerId, rvmId, petCount, pointsAwarded, sessionId, receiptHash)`
- `redeemPoints(recyclerId, pointsToRedeem, redemptionId, destinationHash)`
- `adjustPoints(recyclerId, delta, add)`
- `getRecycler(recyclerId)`
- `isRecyclerRegistered(recyclerId)`
- `isRvmActive(rvmId)`
- `isSessionRecorded(sessionId)`

Sensitive user information must be hashed or kept off-chain. Do not put phone numbers, email addresses or full private media URLs directly in application state or event logs.

## Build

Requirements:

- Node.js 22+
- npm 10+

```bash
cd algorand
npm install
npm run build
```

The build writes the generated Algorand application artifacts to `algorand/artifacts`.

## Deployment sequence

1. Compile and test the application on LocalNet.
2. Deploy to Algorand TestNet.
3. Register the GreenAfrica operator account and pilot RVMs.
4. Set `ALGORAND_GREENAFRICA_APP_ID` in the webapp/backend environment.
5. Run an end-to-end RVM deposit and confirm the ARC-28 event through an Indexer.
6. Test duplicate-session rejection and reward redemption.
7. Move to MainNet after operational and reconciliation tests pass.

## Server environment

```bash
ALGORAND_NETWORK=testnet
ALGORAND_GREENAFRICA_APP_ID=
GREENAFRICA_OPERATOR_MNEMONIC=

# Optional custom endpoints. If omitted, AlgoKit network defaults are used.
ALGOD_SERVER=
ALGOD_PORT=
ALGOD_TOKEN=
INDEXER_SERVER=
INDEXER_PORT=
INDEXER_TOKEN=
```

`GREENAFRICA_OPERATOR_MNEMONIC` is server-only secret material. Never expose it using `NEXT_PUBLIC_*` variables.

## Green Points asset

The current application maintains Green Points as application accounting state. If transferable Green Points are needed later, they can be represented by an Algorand Standard Asset and integrated without changing the recycling receipt model.
