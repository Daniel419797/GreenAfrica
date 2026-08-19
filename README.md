# GreenAfrica

GreenAfrica turns reverse vending machines deployed across African cities into digitally verifiable recycling stations. People deposit PET bottles, the machine verifies the recycling event, and the platform awards Green Points that can be redeemed for airtime or data. Algorand provides the project's blockchain verification and reward-accounting layer.

## Vision & Impact

GreenAfrica's goal is to build a practical circular economy where PET bottles retain residual value and local recyclers receive reliable incentives without needing to understand blockchain technology.

- Reward recycling at bus parks, markets, campuses and other high-traffic locations.
- Give recyclers Green Points that can be redeemed for airtime and data.
- Produce tamper-evident recycling records for municipalities, FMCGs, sponsors, grant providers and ESG teams.
- Keep blockchain complexity behind the platform so recyclers do not need individual crypto wallets.
- Use unique on-chain session IDs and hashed receipts to make recycling activity independently verifiable.

## Monorepo Overview

| Folder | Role | Primary stack |
| --- | --- | --- |
| `algorand` | Algorand application for RVM registry, deposits, Green Points and redemptions | Algorand TypeScript, PuyaTS, ARC-4 |
| `rvm_api` | Edge service that detects accepted bottles and emits recycling events | FastAPI, OpenCV, WebSockets |
| `rvm` | Technician-facing mobile interface for provisioning and supervising machines | Expo Router, React Native, TypeScript |
| `webapp` | Recycler dashboard, referrals and reward redemption | Next.js 15, Tailwind, Firebase, AlgoKit Utils |
| `website` | Public marketing site | Astro, Tailwind CSS v4 |

## Architecture

```text
Recycler
   |
   v
Reverse vending machine
   |
   v
Camera + OpenCV verification
   |
   v
rvm_api
   |
   | accepted recycling session
   v
GreenAfrica backend
   |
   v
Algorand application
   |-- RVM registration / activation
   |-- recycler registration
   |-- PET totals
   |-- Green Points accounting
   |-- duplicate-session protection
   |-- redemption accounting
   `-- ARC-28 event logs
   |
   +-----------------------+
   |                       |
   v                       v
Algorand Indexer       Firebase
   |                       |
   `----------+------------'
              |
              v
       Next.js webapp
              |
              v
     Recycler + sponsor views
```

## Operational Flow

1. The reverse vending machine camera observes the bottle-entry region.
2. `rvm_api` uses computer vision to determine whether a bottle has been accepted.
3. The accepted session is assigned a unique session ID and a receipt/media payload is hashed before blockchain submission.
4. The GreenAfrica backend submits an Algorand application call using a server-managed operator account.
5. The Algorand application validates that the RVM is active, rejects duplicate session IDs, updates PET totals and awards Green Points.
6. ARC-28 compatible events expose recycling activity for Indexer-based analytics and independent verification.
7. Firebase stores user-facing profile, notification and transaction-cache data for the web and mobile experiences.
8. Reward redemptions deduct Green Points in the Algorand application before the off-chain airtime/data fulfillment flow completes.

## Algorand Application

The on-chain application lives at:

`algorand/src/GreenAfrica.algo.ts`

It supports:

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

The application uses box-backed state for RVMs, recycler balances, PET totals, deposit-session deduplication and redemption deduplication. Sensitive user data stays off-chain; identifiers and private destinations should be represented by opaque values or hashes.

## Green Points

Green Points are currently accounted for directly in the Algorand application. They represent redeemable platform value such as airtime or data.

This keeps the first production model simple:

```text
accepted bottle
      |
      v
recordDeposit()
      |
      +--> PET total increases
      |
      `--> Green Points balance increases
```

A later version can represent transferable Green Points with an Algorand Standard Asset if the product requires user-held or sponsor-transferable tokens.

## Verification & Analytics

Algorand event logs and Indexer data can support:

- bottle counts by machine and period
- points awarded and redeemed
- RVM activation status
- duplicate-session detection
- hashed receipt verification
- sponsor campaign reporting
- ESG and grant reporting

Firebase remains the user experience and messaging layer, not the authoritative blockchain ledger.

## Web App Setup

```bash
cd webapp
npm install
npm run dev
```

Configure Firebase using the existing `NEXT_PUBLIC_FIREBASE_*` and Firebase Admin variables.

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

Never expose `GREENAFRICA_OPERATOR_MNEMONIC` through a `NEXT_PUBLIC_*` variable.

## Algorand Contract Setup

```bash
cd algorand
npm install
npm run build
```

Deployment sequence:

1. Compile and test on Algorand LocalNet.
2. Deploy the application to TestNet.
3. Save the application ID as `ALGORAND_GREENAFRICA_APP_ID`.
4. Register the operator and pilot RVM IDs.
5. Run a real test recycling session and verify the transaction/event through Algorand tooling.
6. Test duplicate-session rejection and redemption.
7. Move to MainNet only after the end-to-end path is stable.

## Current Algorand Deployment Status

- Contract source: `algorand/src/GreenAfrica.algo.ts`
- Initial target: Algorand TestNet
- Application ID: pending deployment
- Green Points ASA ID: not used in the current application-accounting model

No deployment ID is documented until a real deployment has been completed and verified.

## Project Entry Points

- Consumer UX: `webapp/src/app`
- Algorand contract: `algorand/src/GreenAfrica.algo.ts`
- Algorand integration guide: `algorand/README.md`
- Machine vision pipeline: `rvm_api/app`
- Field-operations mobile app: `rvm/app`
- Marketing website: `website/src/pages`

## Roadmap

- Compile and test the Algorand application on LocalNet.
- Deploy the application to Algorand TestNet.
- Connect real RVM acceptance events directly to Algorand application calls.
- Add Indexer-driven recycler and sponsor analytics.
- Deploy pilot machines across Lagos transit and high-traffic locations.
- Add SMS fallback for users on low-end devices.
- Expand carbon-equivalent and ESG-grade reporting.
- Evaluate an Algorand Standard Asset for Green Points if transferable rewards become necessary.
