// 売買の承認(authorization)への署名。Sorare のウォレットから書き出した Ethereum の秘密鍵(0x + 64 桁)を使う。
//   - ETH の支払い(Base): EthereumBankTransferAuthorizationRequest … Ethereum の鍵で署名(viem)
//   - カードの受け渡し(Solana): SolanaTokenTransferAuthorizationRequest … Ethereum の鍵から SLIP-0010(m/44'/501'/0'/0')で作る Solana の鍵で署名
// 署名の作り方は Sorare の公式の例(github.com/sorare/api の examples/baseBankTransfer.js・solanaTokenTransfer.js)と同じ。
// どちらも、鍵から作ったアドレスが承認の senderAddress と一致する時だけ署名する(違えば止める)。
import { createHash } from "node:crypto";
import { encodeAbiParameters, encodePacked, keccak256 } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { createKeyPairFromPrivateKeyBytes, createSignerFromKeyPair, createSignableMessage, getBase58Decoder } from "@solana/kit";
import { HDKey } from "micro-key-producer/slip10.js";

// 前後の空白・改行・引用符を除き、0x + 64 桁の小文字にそろえる。違う形なら、鍵は出さずに形だけを理由にして止める
export function ethKey(raw) {
  const k = String(raw ?? "").trim().replace(/^["']|["']$/g, "").trim();
  const hex = k.replace(/^0x/i, "").toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(hex)) throw new Error(`SORARE_PRIVATE_KEY が 0x + 64 桁の 16 進数になっていない(${k.length} 文字)。Sorare のウォレット設定から書き出した秘密鍵を登録してください`);
  return "0x" + hex;
}

export async function createSigner(raw) {
  const key = ethKey(raw);
  const eth = privateKeyToAccount(key);
  const { privateKey } = HDKey.fromMasterSeed(Buffer.from(key.slice(2), "hex")).derive("m/44'/501'/0'/0'");
  const sol = await createSignerFromKeyPair(await createKeyPairFromPrivateKeyBytes(privateKey));
  return { ethAddress: eth.address, solAddress: sol.address, eth, sol };
}

export function ethBankTransferHash(r) {
  const message = encodeAbiParameters(
    [{ type: "address" }, { type: "address" }, { type: "uint256" }, { type: "uint256" }, { type: "uint64" }, { type: "bytes32" }, { type: "address" }, { type: "bytes" }, { type: "address" }],
    [r.senderAddress, r.receiverAddress, BigInt(r.amount), BigInt(r.feeAmount), BigInt(r.deadline), r.salt, r.proxyAddress, "0x", r.contractAddress]);
  return encodePacked(["bytes"], [keccak256(message)]);
}

export function solanaTransferMessage(r) {
  return ["TRANSFER", r.transferProxyProgramAddress, r.merkleTreeAddress, String(r.leafIndex), r.nonce, String(r.expirationTimestamp), r.receiverAddress, "0x", r.originator].join(":");
}

// 承認を種類ごとに作る。check(request) で金額などを確かめてから署名する(違えば例外で止める)
export async function buildApprovals(authorizations, signer, check = () => {}) {
  const out = [];
  for (const { fingerprint, request: r } of authorizations) {
    check(r);
    switch (r.__typename) {
      case "EthereumBankTransferAuthorizationRequest": {
        if (r.senderAddress?.toLowerCase() !== signer.ethAddress.toLowerCase()) throw new Error(`SORARE_PRIVATE_KEY がこのアカウントの鍵と違う(Ethereum のアドレスが一致しない: 鍵 ${signer.ethAddress} / Sorare ${r.senderAddress})`);
        const signature = await signer.eth.signMessage({ message: { raw: ethBankTransferHash(r) } });
        out.push({ fingerprint, ethereumBankTransferApproval: { signature, deadline: r.deadline, salt: r.salt } });
        break;
      }
      case "SolanaTokenTransferAuthorizationRequest": {
        if (r.senderAddress !== signer.solAddress) throw new Error(`SORARE_PRIVATE_KEY がこのアカウントの鍵と違う(Solana のアドレスが一致しない: 鍵 ${signer.solAddress} / Sorare ${r.senderAddress})`);
        const hash = createHash("sha256").update(solanaTransferMessage(r)).digest();
        const [sigs] = await signer.sol.signMessages([createSignableMessage(new Uint8Array(hash))]);
        out.push({ fingerprint, solanaTokenTransferApproval: { signature: getBase58Decoder().decode(sigs[signer.sol.address]), nonce: r.nonce, expirationTimestamp: r.expirationTimestamp } });
        break;
      }
      default:
        throw new Error(`扱わない承認の種類: ${r.__typename}(何もせずに止めました)`);
    }
  }
  return out;
}

export const AUTH = `authorizations { fingerprint request { __typename
  ... on EthereumBankTransferAuthorizationRequest { senderAddress receiverAddress amount feeAmount deadline salt proxyAddress contractAddress }
  ... on SolanaTokenTransferAuthorizationRequest { assetId leafIndex merkleTreeAddress originator receiverAddress senderAddress expirationTimestamp nonce transferProxyProgramAddress } } }`;
