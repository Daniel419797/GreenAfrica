# Algorand Blockchain Integration

GreenAfrica uses Algorand as its only blockchain layer.

## Responsibilities

The Algorand application is responsible for:

- registering and enabling reverse vending machines
- registering recycler Green IDs
- recording accepted recycling sessions
- preventing duplicate session rewards
- maintaining PET totals
- maintaining Green Points balances
- recording point redemptions
- emitting application events for Indexer-based analytics

Firebase remains the user-profile, messaging and UI-cache layer. It is not the authoritative blockchain ledger.

## Application source

`../../algorand/src/GreenAfrica.algo.ts`

## Webapp client

`src/lib/algorand/client.ts`

The client uses a server-side GreenAfrica operator account. Recyclers do not need individual Algorand wallets.

## Required server variables

```bash
ALGORAND_NETWORK=testnet
ALGORAND_GREENAFRICA_APP_ID=
GREENAFRICA_OPERATOR_MNEMONIC=
GREENAFRICA_DEFAULT_RVM_ID=RVM-IFITNESS-ORCHID-001
```

Optional custom node/indexer configuration:

```bash
ALGOD_SERVER=
ALGOD_PORT=
ALGOD_TOKEN=
INDEXER_SERVER=
INDEXER_PORT=
INDEXER_TOKEN=
```

Never expose the operator mnemonic through a `NEXT_PUBLIC_*` variable.

## User registration

After Firebase creates a user and Green ID, `registerUserOnAlgorand` registers that Green ID in the Algorand application. The user profile remains in Firebase; the blockchain stores only the opaque recycler identifier and recycling/reward accounting.

## Deposit flow

```text
RVM accepts bottle
      |
      v
backend receives session
      |
      v
recordDeposit(...)
      |
      +--> verifies active RVM
      +--> rejects duplicate session
      +--> increments PET total
      +--> increments Green Points
      `--> emits deposit event
```

The receipt/media payload is hashed before it is supplied to the application.

## Redemption flow

The webapp checks the recycler's Algorand application balance and then calls `redeemPoints`. A successful blockchain call is followed by the off-chain airtime/data fulfillment flow and a Firebase audit record.

## Deployment

1. Build and test `algorand/src/GreenAfrica.algo.ts` on LocalNet.
2. Deploy it to Algorand TestNet.
3. Set `ALGORAND_GREENAFRICA_APP_ID`.
4. Fund/configure the GreenAfrica operator account.
5. Register pilot RVM IDs.
6. Run deposit, duplicate-session and redemption tests.
7. Use Indexer data for dashboards and audit verification.
