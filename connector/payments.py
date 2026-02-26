"""
x402 Commerce Rail Integration.

Encapsulates the stateless HTTP challenge/response flow for premium
document templates that require micropayment authorization.

On a 402 Payment Required response, this module extracts the payment
instructions from the PAYMENT-REQUIRED response header, signs the
transaction payload using hex encoding, and retries the request with
the signed payload in the X-PAYMENT header per the x402 specification.

On a successful settlement, the PAYMENT-RESPONSE header is extracted
and returned to the caller as an immutable cryptographic receipt.

Includes mitigation for the February 2026 settlement edge case: if the
retry fails and the PAYMENT-RESPONSE header is absent from the response,
the function suppresses the HTTP error and returns a structured recovery
object that the generate_final tool handler can forward directly to
Claude rather than raising an unhandled exception.

References:
    x402 specification: https://www.x402.org/x402-whitepaper.pdf
    Coinbase x402 MCP integration: https://docs.cdp.coinbase.com/x402/mcp-server
"""

import logging
from typing import Any, Dict, Union

import httpx

logger = logging.getLogger("connector.payments")


def _sign_payment_hex(payment_instructions_hex: str) -> str:
    """
    Sign the x402 payment instructions payload.

    Accepts the payment instructions as a hex-encoded string and returns
    a hex-encoded signed payload. Hex encoding is used throughout to avoid
    the 33% size inflation of base64 and the associated computational overhead.

    Production note: In a full deployment this function must interface with
    a hardware wallet, a KMS-backed signing daemon, or an environment-injected
    EVM private key. The deterministic stub below is sufficient for validating
    the challenge/response rail and the February 2026 bug mitigation path
    during integration testing. It must be replaced before handling real funds.
    """
    # Stub: deterministic mock signature for rail validation only.
    return f"{payment_instructions_hex}deadbeef"


async def x402_post(
    client: httpx.AsyncClient,
    url: str,
    **kwargs: Any,
) -> Union[httpx.Response, Dict[str, str]]:
    """
    A stateless async wrapper around httpx.AsyncClient.post that
    transparently handles x402 payment challenges.

    The caller passes in the shared AsyncClient instance so that
    connection pooling is preserved across tool invocations.

    Execution flow:
        1. Attempt the POST request as normal.
        2. On 402, extract payment instructions from the PAYMENT-REQUIRED
           response header.
        3. Sign the instructions and retry with the signed payload in the
           X-PAYMENT header.
        4. On successful settlement, extract the PAYMENT-RESPONSE receipt
           header and attach it to the response for the caller to log and
           return.
        5. On settlement failure with a missing PAYMENT-RESPONSE header,
           return a structured error dict rather than raising, so that
           generate_final can return a recoverable error to Claude.

    Args:
        client:   Shared httpx.AsyncClient instance.
        url:      Target URL.
        **kwargs: Any keyword arguments accepted by httpx.AsyncClient.post.

    Returns:
        httpx.Response on success (with x402_receipt attribute injected)
            or on unhandled non-402 failure.
        dict with paymentStatus and reason keys if the February 2026
            settlement edge case is triggered.
    """
    # Step 1: Initial attempt.
    response = await client.post(url, **kwargs)

    if response.status_code != 402:
        return response

    logger.info("x402: 402 Payment Required — initiating challenge flow for %s", url)

    # Step 2: Extract payment instructions from the response header.
    # The PAYMENT-REQUIRED header carries base64-encoded instructions
    # specifying the required amount, accepted currency (e.g. USDC),
    # destination wallet address, and CAIP-2 network identifier.
    raw_instructions = response.headers.get("PAYMENT-REQUIRED", "")
    if not raw_instructions:
        logger.error(
            "x402: PAYMENT-REQUIRED header absent — cannot proceed with payment."
        )
        return response

    # Encode the instructions as hex for signing to avoid base64 inflation.
    instructions_hex = raw_instructions.encode("utf-8").hex()

    # Step 3: Sign and prepare the retry request.
    signed_hex = _sign_payment_hex(instructions_hex)

    # Build the retry headers without mutating the caller's dict.
    caller_headers: Dict[str, str] = dict(kwargs.pop("headers", {}))
    caller_headers["X-PAYMENT"] = signed_hex
    kwargs["headers"] = caller_headers

    # Step 4: Retry with the signed payment payload.
    retry_response = await client.post(url, **kwargs)

    # February 2026 bug mitigation: a failed settlement may return a second
    # 402 without the PAYMENT-RESPONSE header that would normally carry the
    # failure reason. Return a structured dict so Claude can prompt the user
    # to recover rather than receiving an opaque tool failure.
    if retry_response.status_code == 402:
        if "PAYMENT-RESPONSE" not in retry_response.headers:
            logger.warning(
                "x402: PAYMENT-RESPONSE header missing after settlement attempt — "
                "applying February 2026 bug mitigation."
            )
            try:
                error_reason = retry_response.json().get(
                    "errorReason", "insufficient_balance"
                )
            except ValueError:
                error_reason = "insufficient_balance"

            return {
                "paymentStatus": "failed",
                "reason": error_reason,
            }

    # Step 5: Extract the immutable settlement receipt from the success response.
    # PAYMENT-RESPONSE is a cryptographic receipt that must be preserved for
    # audit purposes. We inject it as a custom attribute on the response object
    # so the caller can include it in the tool return value without re-parsing.
    receipt = retry_response.headers.get("PAYMENT-RESPONSE", "")
    if receipt:
        logger.info("x402: settlement confirmed receipt=%s", receipt[:16])
    else:
        logger.warning(
            "x402: settlement succeeded but PAYMENT-RESPONSE header absent."
        )

    # Attach receipt to the response object for the caller.
    retry_response.x402_receipt = receipt  # type: ignore[attr-defined]

    return retry_response