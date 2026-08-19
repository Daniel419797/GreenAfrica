import { appendFile, mkdir, readFile, readdir, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { AlgoAmount, AlgorandClient } from '@algorandfoundation/algokit-utils'
import algosdk from 'algosdk'

const here = dirname(fileURLToPath(import.meta.url))
const projectRoot = join(here, '..')
const encoder = new TextEncoder()

function bytes(value: string): Uint8Array {
  return encoder.encode(value)
}

async function findArc56Spec(): Promise<string> {
  const roots = [join(projectRoot, 'artifacts'), join(projectRoot, 'src', 'artifacts')]

  for (const root of roots) {
    try {
      const entries = await readdir(root, { recursive: true })
      const match = entries.find((entry) => entry.endsWith('.arc56.json'))
      if (match) return join(root, match)
    } catch {
      // Try the next compiler output location.
    }
  }

  throw new Error('No ARC-56 artifact found. Run npm run build first.')
}

async function main() {
  if ((process.env.ALGORAND_NETWORK || 'testnet').toLowerCase() !== 'testnet') {
    throw new Error('deploy-testnet.ts only deploys to Algorand TestNet')
  }

  if (!process.env.GREENAFRICA_OPERATOR_MNEMONIC) {
    throw new Error('GREENAFRICA_OPERATOR_MNEMONIC is required and must be supplied as a secret')
  }

  const algorand = AlgorandClient.testNet()
  const operator = await algorand.account.fromEnvironment('GREENAFRICA_OPERATOR')
  const operatorAddress = operator.toString()

  let operatorInfo = await algorand.account.getInformation(operator)
  if (Number(operatorInfo.balance) < 4_000_000 && process.env.ALGOKIT_DISPENSER_ACCESS_TOKEN) {
    const dispenser = algorand.client.getTestNetDispenserFromEnvironment()
    await dispenser.fund(operatorAddress, 5_000_000)
    operatorInfo = await algorand.account.getInformation(operator)
  }

  if (Number(operatorInfo.balance) < 4_000_000) {
    throw new Error(
      `TestNet operator ${operatorAddress} needs at least 4 ALGO. Fund it first or provide ALGOKIT_DISPENSER_ACCESS_TOKEN.`,
    )
  }

  const arc56Path = await findArc56Spec()
  const appSpec = await readFile(arc56Path, 'utf8')
  const factory = algorand.client.getAppFactory({
    appSpec,
    creatorAddress: operator,
    defaultSender: operator,
    appName: 'GreenAfricaAlgorand',
  })

  const { result: createResult, appClient } = await factory.send.bare.create({
    populateAppCallResources: true,
  })

  // Box-backed state increases the application's minimum balance. Seed the app
  // account before creating the RVM, recycler and session boxes used by the proof.
  const appFunding = await algorand.send.payment({
    sender: operator,
    receiver: appClient.appAddress,
    amount: AlgoAmount.algo(2),
  })

  async function call(signature: string, args: unknown[]) {
    const method = algosdk.ABIMethod.fromSignature(signature)
    return algorand
      .newGroup()
      .addAppCallMethodCall({
        sender: operator,
        appId: appClient.appId,
        method,
        args,
      })
      .send({ populateAppCallResources: true })
  }

  const suffix = Date.now().toString(36).toUpperCase()
  const rvmId = `RVM-PROOF-${suffix}`
  const recyclerId = `GREEN-PROOF-${suffix}`
  const sessionId = `SESSION-${suffix}`
  const receiptHash = new Uint8Array(
    await crypto.subtle.digest(
      'SHA-256',
      bytes(JSON.stringify({ rvmId, recyclerId, sessionId, petCount: 3, points: 30 })),
    ),
  )

  const rvmTx = await call('registerRvm(byte[])void', [bytes(rvmId)])
  const recyclerTx = await call('registerRecycler(byte[])void', [bytes(recyclerId)])
  const depositTx = await call(
    'recordDeposit(byte[],byte[],uint64,uint64,byte[],byte[])(uint64,uint64)',
    [bytes(recyclerId), bytes(rvmId), 3n, 30n, bytes(sessionId), receiptHash],
  )
  const recyclerState = await call('getRecycler(byte[])(uint64,uint64)', [bytes(recyclerId)])

  const returned = recyclerState.returns?.[0]?.returnValue
  if (!Array.isArray(returned) || returned.length < 2) {
    throw new Error('Unable to read recycler state after TestNet deposit')
  }

  const points = BigInt(returned[0] as bigint | number | string)
  const totalPet = BigInt(returned[1] as bigint | number | string)
  if (points !== 30n || totalPet !== 3n) {
    throw new Error(`RVM proof mismatch: expected 30 points / 3 PET, got ${points} / ${totalPet}`)
  }

  const proof = {
    network: 'testnet',
    appId: appClient.appId.toString(),
    appAddress: appClient.appAddress.toString(),
    operator: operatorAddress,
    creationTxId: createResult.txIds[0],
    appFundingTxId: appFunding.txIds[0],
    rvmRegistrationTxId: rvmTx.txIds[0],
    recyclerRegistrationTxId: recyclerTx.txIds[0],
    depositTxId: depositTx.txIds[0],
    rvmId,
    recyclerId,
    sessionId,
    points: points.toString(),
    totalPet: totalPet.toString(),
    verifiedAt: new Date().toISOString(),
  }

  const outputPath = join(projectRoot, 'artifacts', 'testnet-deployment.json')
  await mkdir(dirname(outputPath), { recursive: true })
  await writeFile(outputPath, `${JSON.stringify(proof, null, 2)}\n`, 'utf8')

  console.log(JSON.stringify(proof, null, 2))

  if (process.env.GITHUB_OUTPUT) {
    await appendFile(process.env.GITHUB_OUTPUT, `app_id=${proof.appId}\ndeposit_tx_id=${proof.depositTxId}\n`)
  }
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
