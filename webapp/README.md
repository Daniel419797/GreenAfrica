# GreenAfrica Web App

The GreenAfrica web app is the recycler-facing Next.js application for authentication, Green Points, referrals, activity history and reward redemption.

GreenAfrica uses **Algorand as its only blockchain layer**. Firebase stores user profiles, notifications and UI-friendly cached state, while the GreenAfrica Algorand application is the authoritative blockchain record for recycler balances, PET totals, recycling sessions and redemptions.

## Main features

- Google, Facebook and phone authentication
- Recycler Green ID registration
- Green Points dashboard
- Recycling reward history
- Referral rewards
- Airtime/data redemption flows
- Firebase-backed profile and notification state
- Algorand-backed reward and redemption accounting

## Blockchain flow

```text
Recycler / RVM
      |
      v
GreenAfrica backend
      |
      v
Algorand application
      |-- recycler registration
      |-- RVM validation
      |-- PET totals
      |-- Green Points
      |-- duplicate-session protection
      `-- redemptions
      |
      +--> Algorand indexing / audit data
      |
      `--> Firebase UI cache -> Next.js dashboard
```

Recyclers do not need individual blockchain wallets. The server uses a GreenAfrica operator account to submit application calls after the platform has authenticated and validated the action.

## Tech stack

- Next.js 15 with App Router
- React 19
- TypeScript
- Tailwind CSS v4
- Firebase / Firebase Admin
- AlgoKit Utils
- `algosdk`
- Leaflet / React Leaflet

## Important source paths

```text
src/actions/blockchain.ts       Algorand registration actions
src/actions/greenpoints.ts      Reward/balance/redemption actions
src/actions/airtime.ts          Algorand-backed airtime redemption
src/lib/algorand/client.ts      Server-side Algorand client
src/lib/firebase/firestore.ts   Profile/UI cache and audit records
src/contexts/AuthContext.tsx    Auth + Algorand recycler registration
scripts/register-rvm-ifitness.ts
```

The Algorand smart contract itself lives one directory above the webapp:

`../algorand/src/GreenAfrica.algo.ts`

## Environment

Configure Firebase using the existing Firebase client and Admin variables.

Configure Algorand server access with:

```bash
ALGORAND_NETWORK=testnet
ALGORAND_GREENAFRICA_APP_ID=
GREENAFRICA_OPERATOR_MNEMONIC=
GREENAFRICA_DEFAULT_RVM_ID=RVM-IFITNESS-ORCHID-001

# Optional custom endpoints
ALGOD_SERVER=
ALGOD_PORT=
ALGOD_TOKEN=
INDEXER_SERVER=
INDEXER_PORT=
INDEXER_TOKEN=
```

`GREENAFRICA_OPERATOR_MNEMONIC` is a server secret. Do not expose it using a `NEXT_PUBLIC_*` variable.

## Development

Because the old lockfile represented the removed Hedera/EVM dependency graph, regenerate it after installing the Algorand dependencies:

```bash
cd webapp
npm install
npm run build
npm run lint
npm run dev
```

Commit the newly generated `package-lock.json` after the install/build succeeds.

## RVM registration

After the Algorand application is deployed and the application ID is configured:

```bash
npm run register-rvm -- --confirm
```

This registers the configured pilot RVM in the Algorand application so rewarded deposits can be accepted for that machine ID.

## Documentation

- `docs/BLOCKCHAIN_INTEGRATION.md`
- `docs/BLOCKCHAIN_POINT_SYSTEM.md`
- `docs/README-RVM-REGISTRATION.md`
- `docs/FIREBASE_SETUP.md`
- `docs/REFERRAL_SYSTEM.md`
- `docs/UI-Design-Guide.md`

## Deployment status

The Algorand application ID is intentionally not hard-coded in this repository. Deploy and verify the application on TestNet first, then set `ALGORAND_GREENAFRICA_APP_ID` in the server environment.
