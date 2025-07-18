"""Erigon execution client transition tool."""

from ethereum_test_exceptions import BlockException, ExceptionMapper, TransactionException


class ErigonExceptionMapper(ExceptionMapper):
    """Erigon exception mapper."""

    mapping_substring = {
        TransactionException.SENDER_NOT_EOA: "sender not an eoa",
        TransactionException.INITCODE_SIZE_EXCEEDED: "max initcode size exceeded",
        TransactionException.INSUFFICIENT_ACCOUNT_FUNDS: (
            "insufficient funds for gas * price + value"
        ),
        TransactionException.NONCE_IS_MAX: "nonce has max value",
        TransactionException.INTRINSIC_GAS_TOO_LOW: "intrinsic gas too low",
        TransactionException.INTRINSIC_GAS_BELOW_FLOOR_GAS_COST: "intrinsic gas too low",
        TransactionException.INSUFFICIENT_MAX_FEE_PER_GAS: "fee cap less than block base fee",
        TransactionException.PRIORITY_GREATER_THAN_MAX_FEE_PER_GAS: "tip higher than fee cap",
        TransactionException.INSUFFICIENT_MAX_FEE_PER_BLOB_GAS: "max fee per blob gas too low",
        TransactionException.NONCE_MISMATCH_TOO_LOW: "nonce too low",
        TransactionException.GAS_ALLOWANCE_EXCEEDED: "gas limit reached",
        TransactionException.TYPE_3_TX_PRE_FORK: "blob txn is not supported by signer",
        TransactionException.TYPE_3_TX_INVALID_BLOB_VERSIONED_HASH: (
            "invalid blob versioned hash, must start with VERSIONED_HASH_VERSION_KZG"
        ),
        TransactionException.TYPE_3_TX_ZERO_BLOBS: "a blob stx must contain at least one blob",
        TransactionException.TYPE_3_TX_WITH_FULL_BLOBS: "rlp: expected String or Byte",
        TransactionException.TYPE_3_TX_CONTRACT_CREATION: "wrong size for To: 0",
        TransactionException.TYPE_3_TX_MAX_BLOB_GAS_ALLOWANCE_EXCEEDED: (
            "blobs/blobgas exceeds max"
        ),
        TransactionException.TYPE_4_EMPTY_AUTHORIZATION_LIST: (
            "SetCodeTransaction without authorizations is invalid"
        ),
        TransactionException.TYPE_4_TX_CONTRACT_CREATION: "wrong size for To: 0",
        TransactionException.TYPE_4_TX_PRE_FORK: "setCode tx is not supported by signer",
        BlockException.INVALID_DEPOSIT_EVENT_LAYOUT: "could not parse requests logs",
        BlockException.SYSTEM_CONTRACT_EMPTY: "Syscall failure: Empty Code at",
        BlockException.SYSTEM_CONTRACT_CALL_FAILED: "Unprecedented Syscall failure",
        BlockException.INVALID_REQUESTS: "invalid requests root hash in header",
        BlockException.INVALID_BLOCK_HASH: "invalid block hash",
        BlockException.RLP_BLOCK_LIMIT_EXCEEDED: "block exceeds max rlp size",
    }
    mapping_regex = {
        TransactionException.GAS_LIMIT_EXCEEDS_MAXIMUM: (
            r"invalid block, txnIdx=\d+, gas limit too high"
        ),
        BlockException.INCORRECT_BLOB_GAS_USED: r"blobGasUsed by execution: \d+, in header: \d+",
        BlockException.INCORRECT_EXCESS_BLOB_GAS: r"invalid excessBlobGas: have \d+, want \d+",
        BlockException.INVALID_GAS_USED: r"gas used by execution: \w+, in header: \w+",
        BlockException.INVALID_GAS_USED_ABOVE_LIMIT: r"invalid gasUsed: have \d+, gasLimit \d+",
    }
