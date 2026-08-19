import assert from 'node:assert/strict'
import { Bytes, Uint64 } from '@algorandfoundation/algorand-typescript'
import { TestExecutionContext } from '@algorandfoundation/algorand-typescript-testing'
import { GreenAfricaAlgorand } from '../src/GreenAfrica.algo.js'

const ctx = new TestExecutionContext()

try {
  const contract = ctx.contract.create(GreenAfricaAlgorand)

  const rvmId = Bytes('RVM-TEST-001')
  const recyclerId = Bytes('GREEN-TEST-001')
  const sessionId = Bytes('SESSION-001')
  const receiptHash = Bytes('receipt-hash-001')

  contract.registerRvm(rvmId)
  assert.equal(contract.isRvmActive(rvmId), true, 'RVM should be active after registration')

  contract.registerRecycler(recyclerId)
  assert.equal(
    contract.isRecyclerRegistered(recyclerId),
    true,
    'Recycler should be registered',
  )

  const [pointsAfterDeposit, petAfterDeposit] = contract.recordDeposit(
    recyclerId,
    rvmId,
    Uint64(3),
    Uint64(30),
    sessionId,
    receiptHash,
  )

  assert.equal(pointsAfterDeposit, Uint64(30), 'Deposit should award Green Points')
  assert.equal(petAfterDeposit, Uint64(3), 'Deposit should increment PET count')
  assert.equal(contract.isSessionRecorded(sessionId), true, 'Session should be recorded')

  assert.throws(
    () =>
      contract.recordDeposit(
        recyclerId,
        rvmId,
        Uint64(1),
        Uint64(10),
        sessionId,
        Bytes('duplicate-receipt'),
      ),
    /Session already recorded/,
    'Duplicate session IDs must be rejected',
  )

  const redemptionId = Bytes('REDEMPTION-001')
  const pointsAfterRedeem = contract.redeemPoints(
    recyclerId,
    Uint64(20),
    redemptionId,
    Bytes('destination-hash'),
  )
  assert.equal(pointsAfterRedeem, Uint64(10), 'Redemption should deduct points')

  assert.throws(
    () =>
      contract.redeemPoints(
        recyclerId,
        Uint64(11),
        Bytes('REDEMPTION-002'),
        Bytes('destination-hash-2'),
      ),
    /Insufficient points/,
    'Overspending Green Points must be rejected',
  )

  contract.adjustPoints(recyclerId, Uint64(5), true)
  const [pointsAfterAdjustment] = contract.getRecycler(recyclerId)
  assert.equal(pointsAfterAdjustment, Uint64(15), 'Point adjustment should update balance')

  contract.setPaused(true)
  assert.throws(
    () =>
      contract.recordDeposit(
        recyclerId,
        rvmId,
        Uint64(1),
        Uint64(10),
        Bytes('SESSION-PAUSED'),
        Bytes('receipt-paused'),
      ),
    /Paused/,
    'Deposits must fail while the contract is paused',
  )

  contract.setPaused(false)
  const [finalPoints, finalPet] = contract.recordDeposit(
    recyclerId,
    rvmId,
    Uint64(1),
    Uint64(10),
    Bytes('SESSION-002'),
    Bytes('receipt-hash-002'),
  )

  assert.equal(finalPoints, Uint64(25))
  assert.equal(finalPet, Uint64(4))

  console.log('GreenAfrica Algorand contract tests passed')
} finally {
  ctx.reset()
}
