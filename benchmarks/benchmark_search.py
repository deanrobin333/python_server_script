#!/usr/bin/python3
"""
Benchmarking utilities for search algorithms and end-to-end server latency/QPS.

This script supports two primary benchmarking modes:

1) Algorithm benchmarks (direct calls to SearchEngine.exists):
   - Measures per-query latency statistics (avg, p50, p95, min, max).

2) Server QPS benchmarks (end-to-end TCP requests):
   - Starts the TCP server as a subprocess using a temporary config.
   - Sends requests using multiple concurrent clients.
   - Measures achieved QPS and latency percentiles.

Results are written as CSV files to the chosen output directory.
"""

from __future__ import annotations

import argparse
import csv
import random
import socket
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from config import AppConfig
from search_engine import EngineError, SearchEngine


def percentile(values: list[float], pct: float) -> float:
    """Compute a simple percentile value from a list.

    Args:
        values: List of numeric values.
        pct: Percentile to compute (0-100).

    Returns:
        The percentile value, or 0.0 for an empty input list.
    """
    if not values:
        return 0.0
    values_sorted = sorted(values)
    k = int(round((pct / 100.0) * (len(values_sorted) - 1)))
    k = max(0, min(k, len(values_sorted) - 1))
    return float(values_sorted[k])


def now_ts() -> str:
    """Return a human-readable timestamp."""
    return time.strftime("%Y-%m-%d %H:%M:%S")


def ensure_dir(p: Path) -> None:
    """Create a directory (and parents) if missing.

    Args:
        p: Directory path to create.
    """
    p.mkdir(parents=True, exist_ok=True)


def count_lines(path: Path) -> int:
    """Count the number of lines in a text file.

    Args:
        path: Path to the file.

    Returns:
        The number of lines in the file.
    """
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def generate_data_file(path: Path, lines: int, seed: int = 123) -> list[str]:
    """Generate a deterministic data file and return sample hit queries.

    The generated file uses newline separators and contains deterministic rows
    based on a PRNG seed. A subset of lines are returned as "hits" so benchmark
    query generation can mix hits and misses.

    Args:
        path: Output file path.
        lines: Number of lines to generate.
        seed: Random seed for deterministic generation.

    Returns:
        A list of sample "hit" strings that are present in the file.
    """
    rng = random.Random(seed)
    ensure_dir(path.parent)

    hits: list[str] = []
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for i in range(lines):
            s = (
                f"{rng.randint(0, 999)};{rng.randint(0, 999)};"
                f"{i};{rng.randint(0, 999)};"
            )
            f.write(s + "\n")
            if i % max(1, lines // 100) == 0:
                hits.append(s)

    if not hits and lines > 0:
        hits.append("0;0;0;0;")
    return hits


def make_queries(
    hits: list[str],
    total: int,
    hit_ratio: float = 0.5,
    seed: int = 456,
) -> list[str]:
    """Create a mixed list of hit and miss queries.

    Args:
        hits: Known-hit query strings that exist in the data file.
        total: Total number of queries to generate.
        hit_ratio: Fraction of queries that should be hits.
        seed: PRNG seed for deterministic generation.

    Returns:
        A list of query strings.
    """
    rng = random.Random(seed)
    q: list[str] = []
    for _ in range(total):
        if rng.random() < hit_ratio:
            q.append(rng.choice(hits))
        else:
            q.append(f"MISS;{rng.randint(0, 10_000_000)};")
    return q


def generate_hits_from_file(path: Path, max_hits: int = 200) -> list[str]:
    """Load a small number of lines from a file to use as hit queries.

    Args:
        path: Path to the data file.
        max_hits: Maximum number of hit strings to collect.

    Returns:
        A list of hit strings read from the file (line terminators stripped).
    """
    hits: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if i >= max_hits:
                break
            hits.append(line.rstrip("\r\n"))
    return hits


def benchmark_algo(
    file_path: Path,
    algo: str,
    reread_on_query: bool,
    queries: list[str],
) -> dict[str, Any]:
    """Benchmark per-query latency for a given algorithm and mode.

    This uses SearchEngine.exists directly (no TCP), collecting per-query
    durations and summary statistics.

    Args:
        file_path: Data file path.
        algo: Algorithm name.
        reread_on_query: Whether to re-read the file per query.
        queries: Query strings to execute.

    Returns:
        A results dictionary suitable for CSV export.

    Raises:
        EngineError: If the engine fails to initialize or execute.
        RuntimeError: For unexpected runtime failures.
    """
    cfg = AppConfig(
        linuxpath=file_path,
        reread_on_query=reread_on_query,
        search_algo=algo,
    )
    engine = SearchEngine.from_config(cfg)

    if not reread_on_query:
        engine.warmup()

    durations_ms: list[float] = []
    hits = 0

    for q in queries[:10]:
        engine.exists(q)

    for q in queries:
        t0 = time.perf_counter()
        ok = engine.exists(q)
        t1 = time.perf_counter()
        durations_ms.append((t1 - t0) * 1000.0)
        hits += 1 if ok else 0

    return {
        "ts": now_ts(),
        "algo": algo,
        "reread_on_query": str(reread_on_query).lower(),
        "lines": count_lines(file_path),
        "queries": len(queries),
        "hits": hits,
        "avg_ms": statistics.mean(durations_ms),
        "p50_ms": percentile(durations_ms, 50),
        "p95_ms": percentile(durations_ms, 95),
        "min_ms": min(durations_ms),
        "max_ms": max(durations_ms),
        "skipped": "",
        "skip_reason": "",
    }


def get_free_port() -> int:
    """Return a free ephemeral port bound on localhost.

    Returns:
        An available TCP port number.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def write_temp_config(
    cfg_path: Path,
    data_file: Path,
    reread_on_query: bool,
    algo: str,
) -> None:
    """Write a temporary config file for starting the benchmark server.

    Args:
        cfg_path: Output path for the temporary config.
        data_file: Data file path to embed in the config.
        reread_on_query: Whether the server should reread the file per query.
        algo: Algorithm name to set in config.
    """
    cfg_path.write_text(
        "\n".join(
            [
                "foo=bar",
                f"linuxpath={data_file}",
                f"reread_on_query={'True' if reread_on_query else 'False'}",
                f"search_algo={algo}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def recv_all(sock: socket.socket, bufsize: int = 4096) -> bytes:
    """Receive all data until the server closes the connection.

    Args:
        sock: Connected socket.
        bufsize: Bytes per recv() call.

    Returns:
        All bytes read from the socket.
    """
    chunks: list[bytes] = []
    while True:
        part = sock.recv(bufsize)
        if not part:
            break
        chunks.append(part)
    return b"".join(chunks)


def one_request(
    host: str,
    port: int,
    query: str,
    timeout_s: float = 3.0,
) -> tuple[bool, float]:
    """Send one TCP request and measure end-to-end latency.

    The request opens a new connection, sends one query, reads the entire
    response, and returns whether a well-formed response terminator is present.

    Args:
        host: Server host to connect to.
        port: Server port to connect to.
        query: Query string (without newline).
        timeout_s: Timeout for connect and socket operations.

    Returns:
        A tuple of:
        - ok: True if the response ends with a valid result line.
        - latency_ms: End-to-end duration in milliseconds.
    """
    t0 = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout_s) as s:
            s.settimeout(timeout_s)
            s.sendall((query + "\n").encode("utf-8"))
            raw = recv_all(s)

        text = raw.decode("utf-8", errors="replace")
        ok = text.endswith(("STRING EXISTS\n", "STRING NOT FOUND\n"))

        t1 = time.perf_counter()
        return ok, (t1 - t0) * 1000.0
    except Exception:
        t1 = time.perf_counter()
        return False, (t1 - t0) * 1000.0


def benchmark_server_qps(
    data_file: Path,
    algo: str,
    reread_on_query: bool,
    qps_target: int,
    duration_s: float,
    clients: int,
    tmp_dir: Path,
) -> dict[str, Any]:
    """Benchmark end-to-end request throughput and latency.

    This function starts the server as a subprocess, then submits TCP requests
    using multiple client workers, attempting to send at a target QPS for a
    fixed duration.

    Args:
        data_file: Data file to configure the server with.
        algo: Algorithm name.
        reread_on_query: Whether the server should reread the file per query.
        qps_target: Target QPS (requests per second) to attempt.
        duration_s: Benchmark duration in seconds.
        clients: Number of concurrent client workers.
        tmp_dir: Temporary directory for config files.

    Returns:
        A results dictionary suitable for CSV export.

    Raises:
        RuntimeError: If the server fails to start.
    """
    port = get_free_port()
    cfg_path = tmp_dir / "bench_app.conf"
    write_temp_config(cfg_path, data_file, reread_on_query, algo)

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "server",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--config",
            str(cfg_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    time.sleep(0.35)
    if proc.poll() is not None:
        out, err = proc.communicate(timeout=2)
        raise RuntimeError(
            "Server failed to start.\n"
            f"--- stdout ---\n{out}\n"
            f"--- stderr ---\n{err}\n"
        )

    queries = make_queries(
        hits=generate_hits_from_file(data_file, max_hits=200),
        total=int(qps_target * duration_s),
    )

    sent = 0
    ok_count = 0
    errors = 0
    latencies_ms: list[float] = []

    t_end = time.perf_counter() + duration_s

    try:
        with ThreadPoolExecutor(max_workers=clients) as ex:
            futures = []
            spacing = 1.0 / max(1, qps_target)
            next_time = time.perf_counter()

            for q in queries:
                now = time.perf_counter()
                if now < next_time:
                    time.sleep(next_time - now)
                next_time += spacing

                if time.perf_counter() > t_end:
                    break

                futures.append(ex.submit(one_request, "127.0.0.1", port, q))
                sent += 1

            for fut in as_completed(futures):
                ok, ms = fut.result()
                latencies_ms.append(ms)
                if ok:
                    ok_count += 1
                else:
                    errors += 1

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()

    achieved_qps = ok_count / max(duration_s, 0.001)

    return {
        "ts": now_ts(),
        "algo": algo,
        "reread_on_query": str(reread_on_query).lower(),
        "lines": count_lines(data_file),
        "clients": clients,
        "qps_target": qps_target,
        "duration_s": duration_s,
        "sent": sent,
        "ok": ok_count,
        "errors": errors,
        "achieved_qps": achieved_qps,
        "p50_ms": percentile(latencies_ms, 50),
        "p95_ms": percentile(latencies_ms, 95),
        "skipped": "",
        "skip_reason": "",
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write results as a CSV file.

    The CSV header uses a stable field order computed as the union of keys in
    insertion order.

    Args:
        path: Output CSV file path.
        rows: Result rows to write.
    """
    if not rows:
        return
    ensure_dir(path.parent)

    keys: list[str] = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                keys.append(k)

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for benchmarking.

    Returns:
        Parsed command-line arguments.
    """
    p = argparse.ArgumentParser(
        description="Benchmark search algorithms and server QPS."
    )
    p.add_argument(
        "--outdir",
        default="benchmarks/results",
        help="Output directory for CSV results.",
    )
    p.add_argument(
        "--datadir",
        default="benchmarks/data",
        help="Directory to store generated data files.",
    )
    p.add_argument(
        "--sizes",
        default="10000,50000,100000,250000,500000,1000000",
        help="Comma-separated line counts.",
    )
    p.add_argument(
        "--queries",
        type=int,
        default=500,
        help="Number of queries per algo run.",
    )
    p.add_argument(
        "--hit-ratio",
        type=float,
        default=0.5,
        help="Fraction of queries that should be hits.",
    )
    p.add_argument(
        "--algos",
        default="linear_scan,mmap_scan,grep_fx,set_cache,sorted_bisect",
        help="Comma-separated algos.",
    )
    p.add_argument("--mode", choices=["algo", "qps", "both"], default="both")
    p.add_argument(
        "--qps-targets",
        default="100,250,500,1000,2000",
        help="Comma-separated QPS targets.",
    )
    p.add_argument(
        "--qps-duration",
        type=float,
        default=5.0,
        help="Duration seconds per QPS step.",
    )
    p.add_argument(
        "--clients",
        type=int,
        default=50,
        help="Concurrent client workers for QPS tests.",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Print progress updates.",
    )
    return p.parse_args()


def main() -> None:
    """Run benchmarks and write CSV outputs."""
    args = parse_args()

    outdir = Path(args.outdir)
    datadir = Path(args.datadir)
    tmp_dir = outdir / "tmp"
    ensure_dir(outdir)
    ensure_dir(datadir)
    ensure_dir(tmp_dir)

    sizes = [int(x.strip()) for x in args.sizes.split(",") if x.strip()]
    algos = [x.strip() for x in args.algos.split(",") if x.strip()]
    qps_targets = (
        [int(x.strip()) for x in args.qps_targets.split(",") if x.strip()]
    )

    supported: set[str] | None = None
    if hasattr(SearchEngine, "supported_algorithms"):
        try:
            # type: ignore[attr-defined]
            supported = SearchEngine.supported_algorithms()
        except Exception:
            supported = None

    if supported is not None:
        algos = [a for a in algos if a in supported]
        if args.verbose:
            print(f"Supported algos: {sorted(supported)}", flush=True)
            print(f"Benchmarking algos: {algos}", flush=True)

    est_runs = 0
    for _n in sizes:
        for algo in algos:
            reread_modes = (
                [True, False]
                if algo in {"linear_scan", "mmap_scan", "grep_fx"}
                else [False]
            )
            for _reread in reread_modes:
                if args.mode in {"algo", "both"}:
                    est_runs += 1
                if args.mode in {"qps", "both"}:
                    est_runs += len(qps_targets)

    if args.verbose:
        print(f"Planned runs: {est_runs}  (mode={args.mode})", flush=True)

    algo_rows: list[dict[str, Any]] = []
    qps_rows: list[dict[str, Any]] = []

    done = 0

    for n in sizes:
        data_file = datadir / f"data_{n}.txt"
        hits = generate_data_file(data_file, n, seed=123)
        queries = make_queries(
            hits,
            total=args.queries,
            hit_ratio=args.hit_ratio,
            seed=456,
        )

        for algo in algos:
            reread_modes = (
                [True, False]
                if algo in {"linear_scan", "mmap_scan", "grep_fx"}
                else [False]
            )

            for reread in reread_modes:
                if args.mode in {"algo", "both"}:
                    done += 1
                    if args.verbose:
                        print(
                            f"[{done}/{est_runs}] algo: "
                            f"lines={n} algo={algo} reread={reread}",
                            flush=True,
                        )
                    try:
                        row = benchmark_algo(data_file, algo, reread, queries)
                    except (EngineError, RuntimeError) as exc:
                        if args.verbose:
                            print(f"  -> skipped: {exc}", flush=True)
                        algo_rows.append(
                            {
                                "ts": now_ts(),
                                "algo": algo,
                                "reread_on_query": str(reread).lower(),
                                "lines": n,
                                "queries": len(queries),
                                "hits": 0,
                                "avg_ms": "",
                                "p50_ms": "",
                                "p95_ms": "",
                                "min_ms": "",
                                "max_ms": "",
                                "skipped": "yes",
                                "skip_reason": str(exc),
                            }
                        )
                    else:
                        algo_rows.append(row)

                if args.mode in {"qps", "both"}:
                    for qps in qps_targets:
                        done += 1
                        if args.verbose:
                            print(
                                f"[{done}/{est_runs}] qps:  "
                                f"lines={n} algo={algo} reread={reread} "
                                f"qps={qps}",
                                flush=True,
                            )
                        try:
                            row2 = benchmark_server_qps(
                                data_file=data_file,
                                algo=algo,
                                reread_on_query=reread,
                                qps_target=qps,
                                duration_s=args.qps_duration,
                                clients=args.clients,
                                tmp_dir=tmp_dir,
                            )
                        except (EngineError, RuntimeError) as exc:
                            if args.verbose:
                                print(f"  -> skipped: {exc}", flush=True)
                            qps_rows.append(
                                {
                                    "ts": now_ts(),
                                    "algo": algo,
                                    "reread_on_query": str(reread).lower(),
                                    "lines": n,
                                    "clients": args.clients,
                                    "qps_target": qps,
                                    "duration_s": args.qps_duration,
                                    "sent": 0,
                                    "ok": 0,
                                    "errors": 0,
                                    "achieved_qps": 0,
                                    "p50_ms": "",
                                    "p95_ms": "",
                                    "skipped": "yes",
                                    "skip_reason": str(exc),
                                }
                            )
                        else:
                            qps_rows.append(row2)

    if algo_rows:
        write_csv(outdir / "results_algo.csv", algo_rows)
    if qps_rows:
        write_csv(outdir / "results_qps.csv", qps_rows)

    print(f"Wrote results to: {outdir}", flush=True)


if __name__ == "__main__":
    main()
