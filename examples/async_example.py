"""Async usage — for async agent frameworks."""

# pip install trustloop[async]

import asyncio
from trustloop import AsyncTrustLoop, TrustLoopBlockedError


async def main():
    async with AsyncTrustLoop(api_key="tl_your_key_here", agent_name="async-agent") as tl:

        # ── Manual check ─────────────────────────────────────────────────────
        result = await tl.intercept("send_email", {"to": "ceo@co.com"})
        if result["allowed"]:
            print("Sending email...")

        # ── Auto-raise ────────────────────────────────────────────────────────
        try:
            await tl.intercept("delete_all_records", raise_if_blocked=True)
        except TrustLoopBlockedError as e:
            print(f"Blocked: {e}")

        # ── Decorator on async function ───────────────────────────────────────
        @tl.guard("transfer_funds")
        async def transfer(amount: float, to: str):
            print(f"Transferring £{amount} to {to}")
            await asyncio.sleep(0.1)
            return "done"

        await transfer(1000, "GB29NWBK60161331926819")

        # ── Check stats ───────────────────────────────────────────────────────
        stats = await tl.get_stats()
        print(f"Total calls this month: {stats.get('total', 0)}")


if __name__ == "__main__":
    asyncio.run(main())
