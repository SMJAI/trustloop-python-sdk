"""Basic usage — any Python agent, any framework."""

from trustloop import TrustLoop, TrustLoopBlockedError

tl = TrustLoop(api_key="tl_your_key_here", agent_name="my-agent")


# ── Option 1: Check and proceed manually ─────────────────────────────────────

def send_email(to: str, subject: str, body: str):
    result = tl.intercept("send_email", {"to": to, "subject": subject, "body": body})

    if not result["allowed"]:
        print(f"Blocked: {result.get('message')}")
        return

    # ... actual send logic here
    print(f"Email sent to {to}")


# ── Option 2: raise_if_blocked ────────────────────────────────────────────────

def delete_records(table: str, where: dict):
    try:
        tl.intercept("delete_records", {"table": table, "where": where}, raise_if_blocked=True)
    except TrustLoopBlockedError as e:
        print(f"Blocked by TrustLoop: {e}")
        return

    # ... actual delete logic here
    print(f"Deleted from {table}")


# ── Option 3: @tl.guard() decorator ──────────────────────────────────────────

@tl.guard("transfer_funds")
def transfer_funds(amount: float, to_account: str):
    # This function body only runs if TrustLoop allows it
    print(f"Transferring £{amount} to {to_account}")


if __name__ == "__main__":
    send_email("ceo@example.com", "Hello", "Test message")
    transfer_funds(50000, "GB29NWBK60161331926819")  # will be intercepted
