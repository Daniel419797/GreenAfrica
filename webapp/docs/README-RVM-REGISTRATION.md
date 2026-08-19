# Registering a GreenAfrica RVM on Algorand

RVMs must be registered in the GreenAfrica Algorand application before they can submit rewarded recycling sessions.

The current example registers the iFitness Orchid machine:

`RVM-IFITNESS-ORCHID-001`

## Prerequisites

Deploy the Algorand application first and configure the webapp server environment:

```bash
ALGORAND_NETWORK=testnet
ALGORAND_GREENAFRICA_APP_ID=
GREENAFRICA_OPERATOR_MNEMONIC=
```

Optional custom Algod/Indexer endpoints can be supplied with `ALGOD_SERVER`, `ALGOD_TOKEN`, `INDEXER_SERVER` and `INDEXER_TOKEN`.

## Run the registration script

```bash
cd webapp
npm install
npm run register-rvm -- --confirm
```

The script calls `registerRVMOnAlgorand`, which sends `registerRvm(rvmId)` to the deployed application.

Location, human-readable name and other machine metadata stay in GreenAfrica's off-chain data layer. The Algorand application stores the machine identifier and active status needed to validate deposits.

## Expected result

A successful run prints the Algorand transaction ID. If the RVM is already registered, the action returns successfully without creating a duplicate machine record.

## Deposit requirement

`recordDeposit` rejects recycling sessions for unknown or inactive RVM IDs. Register the machine before running end-to-end bottle tests.
