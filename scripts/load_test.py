#!/usr/bin/env python3
"""Small asynchronous health-endpoint load check for a deployed instance."""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx


async def run(base_url: str, requests: int, concurrency: int) -> None:
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    failures = 0

    async with httpx.AsyncClient(timeout=5.0) as client:

        async def one() -> None:
            nonlocal failures
            async with semaphore:
                started = time.perf_counter()
                try:
                    response = await client.get(f"{base_url.rstrip('/')}/health/live")
                    if response.status_code != 200:
                        failures += 1
                except httpx.HTTPError:
                    failures += 1
                finally:
                    latencies.append((time.perf_counter() - started) * 1000)

        await asyncio.gather(*(one() for _ in range(requests)))
    ordered = sorted(latencies)
    p95 = ordered[max(0, int(len(ordered) * 0.95) - 1)]
    print(f"requests={requests} concurrency={concurrency} failures={failures}")
    print(f"mean_ms={statistics.mean(latencies):.2f} p95_ms={p95:.2f} max_ms={max(latencies):.2f}")
    if failures:
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=20)
    args = parser.parse_args()
    asyncio.run(run(args.base_url, args.requests, args.concurrency))


if __name__ == "__main__":
    main()
