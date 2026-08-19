# GreenAfrica

## Hedera Certification

https://drive.google.com/file/d/1J5dpu8Mr0HWa4Uu2BkdkySVCzppRWVx4/view

## Pitch Deck

https://drive.google.com/file/d/1A5GV2dYkhUOWdbIoe0DIInnNxrAwEQ_r/view

**Track:** DLT for Operations  
**Sub-track**: 4, Sustainability & Impact Tech

GreenAfrica turns reverse vending machines deployed across African cities into digitally verifiable recycling stations, pairing real-world bottle recovery with instant, tokenized rewards backed by a multi-chain verification layer using Hedera and Algorand.

## Vision & Impact

GreenAfrica's vision is to unlock a circular economy where every PET bottle keeps residual value and local recyclers earn reliable income without friction. We couple rugged reverse vending machines with blockchain-backed loyalty and audit rails so municipalities, FMCGs, telecoms, grant providers, and ESG teams can co-fund incentives while seeing tamper-evident performance data.

- Reduce plastic leakage by rewarding deposit behavior exactly where waste is generated (bus parks, markets, campuses).
- Provide micro-earnings denominated as Green Points that convert into airtime/data bundles, smoothing household cash flow.
- Deliver audit-ready climate impact evidence so grants and ESG budgets translate into transparent, measurable outcomes.
- Cross-check recycling receipts across Hedera and Algorand for stronger independent verification and multi-chain resilience.

## Monorepo Overview

| Folder     | Role in platform                                                                                  | Primary stack                         | Notable outputs                                                        |
| ---------- | ------------------------------------------------------------------------------------------------- | ------------------------------------- | ---------------------------------------------------------------------- |
| `contract` | Solidity smart contracts for RVM registry, deposits, referrals, and redemptions on Hedera         | Hardhat, Solidity 0.8                 | GreenAfrica.sol bytecode, contract ABIs, deployment scripts            |
| `algorand` | Algorand-native verification and accounting rail for RVMs, deposits, points, and redemptions      | Algorand TypeScript, PuyaTS, ARC-4    | TEAL, ARC specs, ARC-28 deposit/redemption events                      |
| `rvm_api`  | Edge service that runs on the vending machine, detects bottles, and orchestrates reward issuance  | FastAPI, OpenCV, WebSockets           | Computer-vision event stream, QR code payloads, operator dashboard API |
| `rvm`      | Technician-facing mobile interface for provisioning RVMs and supervising sessions                 | Expo Router, React Native, TypeScript | Device onboarding flows, maintenance tools                             |
| `webapp`   | Consumer web experience for recyclers to view their impact, redeem rewards, and onboard referrals | Next.js 15, Tailwind, Firebase        | Responsive dashboard, reward flows, analytics                          |
| `website`  | Public marketing site: home, how it works, brands, partners, technology, about, contact           | Astro, Tailwind CSS v4                | Static site in `website/dist`                                          |

### Operational Flow

![Archtecture Diagram](/achitecture-diagram.png)
`GreenAfrica Architecture Diagram`

1. The vending machine runs the `rvm_api`, which watches the region of interest on camera and emits bottle acceptance events with QR codes and session metadata.
2. Accepted events trigger on-board logic that awards Green Points and submits the recycling receipt through the configured blockchain writers.
3. On Hedera, the existing smart contract anchors deposit details and the hashed receipt can also be published to a Hedera Consensus Service topic.
4. On Algorand, the `GreenAfricaAlgorand` ARC-4 application records the same hashed recycler/RVM/session identifiers, updates PET and point totals, prevents duplicate sessions, and emits ARC-28 events for indexing.
5. The same `sessionId` and receipt hash can be written to both chains, allowing the backend to reconcile Hedera and Algorand records without exposing user PII.
6. The Next.js webapp consumes application state and indexed events, presenting live dashboards to recyclers and sponsors.
7. Referral payouts and airtime/data redemptions remain supported by the existing Hedera flow, while Algorand records redemption accounting as a second verification rail. Algorand Standard Asset support for native Green Points is a planned extension.

### Key On-Chain Records

- RVM registry and activation state for deployed machines.
- Recycler profiles keyed by hashed identifiers rather than raw phone numbers or email addresses.
- Deposit sessions keyed by a unique `sessionId` to prevent double recording.
- PET totals and Green Points accounting.
- Redemption events keyed by unique redemption IDs.
- Hashed deposit receipts for cross-chain reconciliation and ESG reporting.

### Analytics & Monitoring

- Hedera Mirror Node queries surface bottle counts, points issued, and redemption activity.
- Algorand Indexer can independently surface ARC-28 deposit and redemption events from the Algorand application.
- Firebase/Firestore stores user-facing state and acts as notification bus.
- Telemetry from `rvm_api` (QR scans, event latency) is surfaced to judges through Grafana-ready JSON endpoints.
- Cross-chain reconciliation can compare the same `sessionId` and receipt hash on Hedera and Algorand to detect missing or inconsistent writes.

## Multi-Chain Integration Summary

### Hedera Smart Contract Service

We deployed the GreenAfrica RVM Registry contract (`0.0.6779400`) on the Hedera Smart Contract Service to enforce business logic around deposits, referrals, and redemptions in a single atomic call. Contract execution provides the currently deployed operational accounting layer for GreenAfrica.

### Hedera Token Service

Green Points (`0.0.6919030`) is an HTS token that represents off-chain value such as airtime or data bundles. The Token Service provides the existing token rail for sponsor-funded micro-rewards.

### Hedera Consensus Service

Hashed deposit receipts can be broadcast to a dedicated HCS topic so sponsors and regulators can independently verify activity through Mirror Node and retain a tamper-evident timeline of machine activity.

### Algorand Smart Contract Application

The `algorand` module adds an ARC-4-compatible GreenAfrica application written in Algorand TypeScript and compiled to the Algorand Virtual Machine with PuyaTS. The application supports:

- RVM registration and activation
- recycler registration using hashed Green IDs
- PET deposit and Green Points accounting
- duplicate-session protection
- point adjustments and redemptions
- ARC-28 event emission for indexer-based analytics

The Algorand application is designed to run alongside Hedera, not replace it. GreenAfrica can dual-write the same recycling receipt to both networks and use the matching `sessionId` and receipt hash for independent verification.

### Algorand Standard Assets

A production extension can issue Green Points as an Algorand Standard Asset (ASA), creating a native Algorand reward rail in addition to the existing HTS token. The initial integration keeps points in application accounting until token issuance, custody, redemption, and compliance policies are finalized.

## Hedera Transaction Types

- `TokenCreateTransaction`: one-off creation of the Green Points HTS token treasury.
- `TokenMintTransaction`: periodic top-ups of the reward pool when sponsorship funds refresh.
- `TransferTransaction`: distribution of Green Points to recyclers and referral accounts.
- `ContractExecuteTransaction`: invoking `recordDeposit`, `redeemPoints`, and admin functions on the GreenAfrica contract.
- `ContractCallQuery`: reading user balances and machine state for dashboards without consuming gas.
- `TopicMessageSubmitTransaction`: anchoring hashed deposit receipts and operational alerts on HCS for third-party monitoring.

## Algorand Application Operations

- `registerRvm`: register a reverse vending machine in Algorand application state.
- `setRvmActive`: activate or disable a registered machine.
- `registerRecycler`: initialize point and PET accounting for a hashed recycler ID.
- `recordDeposit`: record PET count, points, session ID, and receipt hash while rejecting duplicate sessions.
- `redeemPoints`: deduct points and anchor a hashed redemption destination.
- `adjustPoints`: perform operator-controlled point corrections.
- ARC-28 events: expose machine, deposit, accounting, and redemption activity to Algorand Indexer consumers.

## Economic & Resilience Rationale

- Hedera remains the currently deployed reward and compliance rail, preserving the existing GreenAfrica implementation.
- Algorand adds an independently verifiable application and event stream without requiring recyclers to manage wallets.
- Dual-chain receipt hashes make it possible to reconcile recycling evidence across two separate networks.
- The architecture can route or replicate writes according to sponsorship, grant, geography, or resilience requirements rather than binding the platform to one ledger.

## Setup Instructions (Web App)

- **Clone this monorepo:** then `cd GreenAfrica`.
- **Install web dependencies:** `cd webapp && npm install`.
- **Create environment file:** configure the required Firebase and blockchain server variables.
- **Configure Firebase:** set all `NEXT_PUBLIC_FIREBASE_*`, `FIREBASE_PRIVATE_KEY`, and `FIREBASE_CLIENT_EMAIL` values with your Firebase project credentials.
- **Configure Hedera access:** set `HEDERA_NETWORK=testnet`, point `HEDERA_RPC_URL` to a testnet endpoint, and provide operator `HEDERA_OPERATOR_ID`/`HEDERA_OPERATOR_KEY`.
- **Link Hedera contracts:** ensure `GREEN_AFRICA_CONTRACT_ID` and `GREENPOINTS_TOKEN_ID` reflect the desired testnet deployments.
- **Run the dev server:** `npm run dev`, then open `http://localhost:3000`.

## Setup Instructions (Algorand)

The Algorand module uses the current Algorand TypeScript/PuyaTS toolchain.

```bash
cd algorand
npm install
npm run build
```

Recommended server-side configuration after TestNet deployment:

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

Never expose the Algorand operator mnemonic through `NEXT_PUBLIC_*` environment variables.

## Current Blockchain Deployments

### Hedera Testnet

- GreenAfrica RVM Contract ID: `0.0.6779400`
- GreenPoints HTS Token ID: `0.0.6919030`

### Algorand

- Contract source: `algorand/src/GreenAfrica.algo.ts`
- Network target: TestNet first
- Application ID: pending TestNet deployment
- Green Points ASA ID: pending a later tokenization phase

## Judge & Mentor Quick Links

- Consumer UX: `webapp/src/app`
- Hedera Smart Contract Logic: `contract/contracts/GreenAfrica.sol`
- Algorand Smart Contract Logic: `algorand/src/GreenAfrica.algo.ts`
- Algorand Integration Guide: `algorand/README.md`
- Machine Vision Pipeline: `rvm_api/app`
- Field Ops Mobile App: `rvm/app`

## Roadmap Highlights

- Deploy 5 pilot machines across Lagos transit hubs with sponsor-backed reward pools.
- Deploy the Algorand application to TestNet and add backend dual-write support using the same session IDs and receipt hashes as Hedera.
- Add automated Hedera/Algorand reconciliation and alert on missing or mismatched recycling receipts.
- Evaluate an Algorand Standard Asset representation of Green Points after custody and redemption rules are finalized.
- Launch SMS fallback for low-end devices, mirroring blockchain-backed balances via Firebase functions.
- Expand analytics with carbon-equivalent calculations for ESG-grade reporting.
