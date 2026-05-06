"""Stop a Together AI dedicated endpoint to halt $/min billing.

Usage: python scripts/stop_endpoint.py <endpoint_id>
"""
from __future__ import annotations
import os
import sys

from together import Together


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <endpoint_id>", file=sys.stderr)
        return 2

    ep_id = sys.argv[1]
    client = Together(api_key=os.environ["TOGETHER_API_KEY"])

    before = client.endpoints.retrieve(ep_id)
    print(f"before: state={before.state}")

    client.endpoints.update(ep_id, state="STOPPED")

    after = client.endpoints.retrieve(ep_id)
    print(f"after:  state={after.state}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
