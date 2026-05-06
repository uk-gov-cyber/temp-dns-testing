import asyncio
import json
import socket
import time

import aiodns

INPUT_FILE = "small.json"


async def run_aiodns_queries(domains: list[str]) -> list[dict]:
    resolver = aiodns.DNSResolver()
    results = []

    for domain in domains:
        try:
            answer = await resolver.gethostbyname(domain, socket.AF_INET)
            results.append(
                {
                    "domain": domain,
                    "status": "success",
                    "answers": answer.addresses,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "domain": domain,
                    "status": "error",
                    "answers": [],
                    "error": str(exc),
                }
            )

    return results


def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        payload = json.load(f)

    domains = payload["domains"]

    started = time.perf_counter()
    results = asyncio.run(run_aiodns_queries(domains))
    elapsed = time.perf_counter() - started

    success_count = 0
    error_count = 0

    for result in results:
        if result["status"] == "success":
            success_count += 1
        elif result["status"] == "error":
            error_count += 1

    print("domains:", len(domains))
    print("elapsed_seconds:", round(elapsed, 3))
    print("success_count:", success_count)
    print("error_count:", error_count)


if __name__ == "__main__":
    main()
