# Green Points on Algorand

Green Points are GreenAfrica's recycling reward units. Their authoritative blockchain balance is maintained by the GreenAfrica Algorand application.

## Current model

Green Points are application accounting state rather than a transferable token.

For a successful bottle deposit:

```text
recordDeposit
  -> PET total increases
  -> Green Points balance increases
  -> unique session ID is marked as used
  -> deposit event is emitted
```

For a redemption:

```text
redeemPoints
  -> validates sufficient balance
  -> Green Points balance decreases
  -> redemption ID is marked as used
  -> redemption event is emitted
```

Referral/admin rewards use the application's `adjustPoints` method.

## Source files

- Algorand application: `../../algorand/src/GreenAfrica.algo.ts`
- Server client: `src/lib/algorand/client.ts`
- Reward actions: `src/actions/greenpoints.ts`
- Firebase cache/audit flow: `src/lib/firebase/firestore.ts`

## Firebase relationship

Firebase's `totalPoints` field is a UI cache. Blockchain writes are performed first; the Firebase cache and transaction history are updated after a successful Algorand call.

For reconciliation, read the recycler's application state from Algorand and compare it with the cached Firebase value.

## Privacy

Recycler Green IDs are opaque application keys. Redemption destinations such as phone numbers are hashed before being sent to the Algorand application.

## Future ASA option

If GreenAfrica later needs transferable, user-held Green Points, the reward can be represented by an Algorand Standard Asset. That is not required for the current airtime/data redemption model.
