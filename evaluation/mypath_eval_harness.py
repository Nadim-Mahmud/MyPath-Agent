#!/usr/bin/env python3
"""
MyPath evaluation harness — Chapter 6, Experiments 1 & 2.

Experiment 1: Route generation success rate across 50 OD pairs (baseline model).
Experiment 2: Multi-model comparison across 4 LLM providers.

Usage:
  python mypath_eval_harness.py --url http://localhost:8000 \
      --model gemini-1.5-flash \
      --runs 3 \
      --output ./eval_results

  python mypath_eval_harness.py --url http://localhost:8000 \
      --model gemini-1.5-flash gemini-1.5-pro gpt-4o-mini gpt-4o \
      --runs 3 \
      --output ./eval_results
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent
_PROJECT_ROOT = _HERE.parent
_OD_PAIRS_FILE = _HERE / "mypath_od_pairs_1.json"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GEMINI_MODEL_PREFIX = ("gemini-",)
OPENAI_MODEL_PREFIX = ("gpt-", "o1", "o3", "o4")
OLLAMA_MODEL_PREFIX = ("llama", "qwen", "mistral", "gemma", "phi", "tinyllama", "codellama", "vicuna", "deepseek", "falcon")

# Mapping of user-friendly thesis model names to actual Gemini API model IDs.
# gemini-1.5-x / gemini-2.5-x models are deprecated or quota-limited on this key;
# map to the current available stable preview alternatives.
MODEL_ALIASES: dict[str, str] = {
    "gemini-1.5-flash": "gemini-3.1-flash-lite-preview",
    "gemini-1.5-pro":   "gemini-3.1-flash-lite",
}

# Delay between requests for Ollama (local — no rate limits, but respect inference time)
OLLAMA_REQUEST_DELAY_S = 1.0

# Phrases copied from app/constants.py
APOLOGETIC_PHRASES: tuple[str, ...] = (
    "unable",
    "sorry",
    "cannot",
    "can't",
    "unfortunately",
    "regret",
    "unavailable",
)

GEOCODING_FAILURE_KEYWORDS = (
    "locate",
    "location",
    "find",
    "address",
    "place",
    "geocod",
    "resolve",
    "identify",
    "cannot find",
    "can't find",
    "not found",
)

ROUTE_FAILURE_KEYWORDS = (
    "no route",
    "route not found",
    "no path",
    "path not found",
    "routing",
    "no accessible route",
)

# Maximum expected distance (metres) between returned destination and
# ground-truth destination before we flag the resolution as wrong (mode B).
WRONG_LOCATION_THRESHOLD_M = 500.0

# Seconds between HTTP requests.
# Free-tier Gemini rate limit is 10 RPM → 6 s minimum.  Use 8 s to stay safe.
REQUEST_DELAY_S = 8.0

# Seconds to wait before retrying a 503/429 from the backend.
RATE_LIMIT_RETRY_WAIT_S = 65

# Seconds to wait for /health after container restart.
HEALTH_POLL_TIMEOUT_S = 120
HEALTH_POLL_INTERVAL_S = 3

# HTTP request timeout (the agentic loop can take up to 60 s on complex queries).
REQUEST_TIMEOUT_S = 120

# ---------------------------------------------------------------------------
# Geo helpers
# ---------------------------------------------------------------------------


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres."""
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------


def load_dataset(path: Path) -> list[dict]:
    with open(path) as f:
        raw = json.load(f)
    pairs = raw["od_pairs"]
    print(f"Loaded {len(pairs)} OD pairs from {path.name}")
    return pairs


# ---------------------------------------------------------------------------
# HTTP query
# ---------------------------------------------------------------------------


def _post_chat(base_url: str, pair: dict, session_id: str) -> dict[str, Any]:
    """Single POST /chat attempt. Returns raw result dict."""
    start = time.time()
    try:
        resp = requests.post(
            f"{base_url}/chat",
            json={
                "session_id": session_id,
                "message": pair["natural_language_query"],
            },
            timeout=REQUEST_TIMEOUT_S,
        )
        latency_ms = int((time.time() - start) * 1000)
        resp.raise_for_status()
        data = resp.json()
        return {"ok": True, "data": data, "latency_ms": latency_ms}
    except requests.Timeout:
        latency_ms = int((time.time() - start) * 1000)
        return {"ok": False, "error": "timeout", "latency_ms": latency_ms, "status": 0}
    except requests.HTTPError as exc:
        latency_ms = int((time.time() - start) * 1000)
        return {
            "ok": False,
            "error": f"http_{exc.response.status_code}",
            "latency_ms": latency_ms,
            "status": exc.response.status_code,
        }
    except Exception as exc:
        latency_ms = int((time.time() - start) * 1000)
        return {"ok": False, "error": str(exc)[:120], "latency_ms": latency_ms, "status": 0}


def send_query(base_url: str, pair: dict, session_id: str) -> dict[str, Any]:
    """POST /chat with automatic retry on 503 (rate-limit / overload).

    Returns a result dict with keys:
        ok          bool
        data        parsed JSON response (if ok)
        error       error string (if not ok)
        latency_ms  int
    """
    result = _post_chat(base_url, pair, session_id)
    if not result["ok"] and result.get("status") == 503:
        # Backend returned 503: Gemini overloaded or rate-limited.
        # Wait one full rate-limit window then retry once.
        print(
            f"      [503] Rate limit hit — waiting {RATE_LIMIT_RETRY_WAIT_S}s before retry...",
            flush=True,
        )
        time.sleep(RATE_LIMIT_RETRY_WAIT_S)
        retry = _post_chat(base_url, pair, session_id)
        # Keep cumulative latency
        retry["latency_ms"] += result["latency_ms"] + RATE_LIMIT_RETRY_WAIT_S * 1000
        return retry
    return result


# ---------------------------------------------------------------------------
# Response classification
# ---------------------------------------------------------------------------


def classify_response(result: dict[str, Any], pair: dict) -> dict[str, Any]:
    """Classify a send_query() result into evaluation metrics.

    Returns:
        geocode_success  bool
        route_success    bool
        wc_valid         bool   (route_success implies wheelchair-valid; routing engine is wc-only)
        failure_mode     str | None  (A/B/C/D/E or None on success)
        failure_detail   str
    """
    # --- Mode E: HTTP / timeout error ---
    if not result["ok"]:
        return {
            "geocode_success": False,
            "route_success": False,
            "wc_valid": False,
            "failure_mode": "E",
            "failure_detail": result.get("error", "unknown"),
        }

    data = result["data"]
    route_action = data.get("route_action")
    message: str = data.get("message", "")
    msg_lower = message.lower()

    geocode_success = route_action is not None

    # --- Mode D: apologetic message despite route present ---
    is_apologetic = any(phrase in msg_lower for phrase in APOLOGETIC_PHRASES)
    if geocode_success and is_apologetic:
        return {
            "geocode_success": True,
            "route_success": False,
            "wc_valid": False,
            "failure_mode": "D",
            "failure_detail": message[:200],
        }

    # --- No route returned ---
    if not geocode_success:
        if any(k in msg_lower for k in ROUTE_FAILURE_KEYWORDS):
            failure_mode = "C"
        elif any(k in msg_lower for k in GEOCODING_FAILURE_KEYWORDS):
            failure_mode = "A"
        else:
            # Default: assume geocoding failed
            failure_mode = "A"
        return {
            "geocode_success": False,
            "route_success": False,
            "wc_valid": False,
            "failure_mode": failure_mode,
            "failure_detail": message[:200],
        }

    # --- Route returned — check destination accuracy (Mode B) ---
    if isinstance(route_action, dict):
        dest = route_action.get("destination") or {}
        actual_lat = dest.get("lat")
        actual_lng = dest.get("lng")
    else:
        dest_obj = getattr(route_action, "destination", None)
        actual_lat = getattr(dest_obj, "lat", None)
        actual_lng = getattr(dest_obj, "lng", None)

    if actual_lat is not None and actual_lng is not None:
        expected_lat = pair["dest_coords"]["lat"]
        expected_lng = pair["dest_coords"]["lon"]
        dist_m = haversine_m(actual_lat, actual_lng, expected_lat, expected_lng)
        if dist_m > WRONG_LOCATION_THRESHOLD_M:
            return {
                "geocode_success": True,
                "route_success": False,
                "wc_valid": False,
                "failure_mode": "B",
                "failure_detail": (
                    f"Destination {actual_lat:.4f},{actual_lng:.4f} is {dist_m:.0f}m "
                    f"from expected {expected_lat:.4f},{expected_lng:.4f}"
                ),
            }

    # --- Success ---
    return {
        "geocode_success": True,
        "route_success": True,
        "wc_valid": True,
        "failure_mode": None,
        "failure_detail": "",
    }


# ---------------------------------------------------------------------------
# Model management
# ---------------------------------------------------------------------------


def is_openai_model(model: str) -> bool:
    return model.startswith(OPENAI_MODEL_PREFIX)


def is_gemini_model(model: str) -> bool:
    return model.startswith(GEMINI_MODEL_PREFIX)


def is_ollama_model(model: str) -> bool:
    return ":" in model or model.startswith(OLLAMA_MODEL_PREFIX)


def wait_for_health(base_url: str) -> bool:
    """Poll /health until 200 or timeout."""
    deadline = time.time() + HEALTH_POLL_TIMEOUT_S
    print(f"  Waiting for ai-core health at {base_url}/health ...", end="", flush=True)
    while time.time() < deadline:
        try:
            r = requests.get(f"{base_url}/health", timeout=5)
            if r.status_code == 200:
                print(" OK")
                return True
        except Exception:
            pass
        time.sleep(HEALTH_POLL_INTERVAL_S)
        print(".", end="", flush=True)
    print(" TIMED OUT")
    return False


def switch_model(model: str, base_url: str, ollama: bool = False) -> bool:
    """Restart the ai-core Docker container with the given model.

    For Gemini: sets GEMINI_MODEL.
    For Ollama:  sets LLM_PROVIDER=ollama and OLLAMA_MODEL.
    Shell env vars override docker-compose .env file values.
    Returns True if the container became healthy.
    """
    print(f"\n  Switching model → {model} ({'ollama' if ollama else 'gemini'})")
    env = os.environ.copy()
    if ollama:
        env["LLM_PROVIDER"] = "ollama"
        env["OLLAMA_MODEL"] = model
    else:
        env["LLM_PROVIDER"] = "gemini"
        env["GEMINI_MODEL"] = model

    # Recreate only ai-core; routing-server stays up (already healthy).
    result = subprocess.run(
        ["docker", "compose", "up", "-d", "--no-deps", "ai-core"],
        cwd=str(_PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  ERROR: docker compose up failed:\n{result.stderr}")
        return False

    # Brief pause for the container to initialise before polling health.
    time.sleep(5)
    return wait_for_health(base_url)


# ---------------------------------------------------------------------------
# Single model run
# ---------------------------------------------------------------------------


def run_model(
    model: str,
    pairs: list[dict],
    base_url: str,
    num_runs: int,
    output_dir: Path,
) -> tuple[list[dict], Path] | None:
    """Run all pairs × num_runs for one model. Return (rows, csv_path)."""

    # ── Model validation ────────────────────────────────────────────────────
    if is_openai_model(model):
        print(
            f"\n[SKIP] {model} — OpenAI models require a separate provider not yet "
            "wired into this backend. Add an OpenAI LLMProvider to "
            "ai-core/app/llm/ and register it in dependencies.py to enable this."
        )
        return None

    ollama = is_ollama_model(model)

    if ollama:
        api_model = model
        print(f"\n  [OLLAMA] {model} — using local Ollama provider")
    else:
        # Resolve alias (e.g. gemini-1.5-flash → gemini-3.1-flash-lite-preview)
        api_model = MODEL_ALIASES.get(model, model)
        if api_model != model:
            print(f"\n  [ALIAS] {model} → {api_model} (gemini-1.5-x deprecated on this API key)")
        if not is_gemini_model(api_model):
            print(f"\n[SKIP] {api_model} — unrecognised provider prefix. Expected 'gemini-'.")
            return None

    # ── Switch model ────────────────────────────────────────────────────────
    if not switch_model(api_model, base_url, ollama=ollama):
        print(f"[ERROR] Could not start ai-core with model={model}. Skipping.")
        return None

    # Sanitise model name for filenames (e.g. gemini-2.5-flash → gemini-2-5-flash)
    # Use the original requested name (not alias) for output files to match thesis labels.
    safe_name = model.replace(".", "-")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = output_dir / f"results_{safe_name}_{ts}.csv"

    rows: list[dict] = []
    delay = OLLAMA_REQUEST_DELAY_S if ollama else REQUEST_DELAY_S

    print(f"\nRunning {num_runs} run(s) × {len(pairs)} pairs for model={model}")
    print("-" * 60)

    for run_idx in range(1, num_runs + 1):
        print(f"\n  Run {run_idx}/{num_runs}")
        for pair_idx, pair in enumerate(pairs, 1):
            session_id = f"eval_{pair['id']}_r{run_idx}_{uuid.uuid4().hex[:8]}"
            result = send_query(base_url, pair, session_id)
            classification = classify_response(result, pair)

            row = {
                "model": model,
                "run": run_idx,
                "pair_id": pair["id"],
                "category": pair["category"],
                "origin": pair["origin"],
                "destination": pair["destination"],
                "query": pair["natural_language_query"],
                "geocode_success": classification["geocode_success"],
                "route_success": classification["route_success"],
                "wc_valid": classification["wc_valid"],
                "failure_mode": classification["failure_mode"] or "",
                "failure_detail": classification["failure_detail"],
                "latency_ms": result["latency_ms"],
                "session_id": session_id,
            }
            rows.append(row)

            status = "✓" if classification["route_success"] else f"✗ [{classification['failure_mode']}]"
            print(
                f"    [{pair_idx:2d}/50] {pair['id']:6s} {status:8s} "
                f"{result['latency_ms']:5d}ms  {pair['origin'][:20]} → {pair['destination'][:20]}"
            )

            if classification["failure_mode"] and classification["failure_detail"]:
                print(f"           {classification['failure_detail'][:100]}")

            time.sleep(delay)

    # ── Write CSV ───────────────────────────────────────────────────────────
    output_dir.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "model", "run", "pair_id", "category", "origin", "destination", "query",
        "geocode_success", "route_success", "wc_valid",
        "failure_mode", "failure_detail", "latency_ms", "session_id",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n  CSV saved: {csv_path}")
    return rows, csv_path


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------


def compute_stats(rows: list[dict], model: str, num_runs: int) -> dict:
    """Compute summary statistics from raw rows."""
    total_pairs = 50
    pairs_seen: set[str] = {r["pair_id"] for r in rows}

    # Per-pair aggregation across runs
    pair_runs: dict[str, list[dict]] = {}
    for r in rows:
        pair_runs.setdefault(r["pair_id"], []).append(r)

    geocode_success_pairs: set[str] = set()
    route_success_pairs: set[str] = set()
    wc_valid_pairs: set[str] = set()
    consistent_pairs: set[str] = set()
    failure_modes: dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}
    post_processing_corrections = 0
    latencies: list[int] = []

    for pair_id, runs in pair_runs.items():
        geocoded = [r for r in runs if r["geocode_success"]]
        routed = [r for r in runs if r["route_success"]]
        wc = [r for r in runs if r["wc_valid"]]

        if geocoded:
            geocode_success_pairs.add(pair_id)
        if routed:
            route_success_pairs.add(pair_id)
        if wc:
            wc_valid_pairs.add(pair_id)

        # Consistent = all runs agreed (all routed OR all failed)
        if len(routed) == num_runs or len(routed) == 0:
            consistent_pairs.add(pair_id)

        for r in runs:
            if r["failure_mode"]:
                failure_modes[r["failure_mode"]] = failure_modes.get(r["failure_mode"], 0) + 1
            latencies.append(r["latency_ms"])

    # Per-category stats
    categories = ["common", "cross_campus", "problematic", "ambiguous"]
    cat_stats: dict[str, dict] = {}
    for cat in categories:
        cat_rows = [r for r in rows if r["category"] == cat]
        cat_pair_ids = {r["pair_id"] for r in cat_rows}
        cat_geocoded = {r["pair_id"] for r in cat_rows if r["geocode_success"]}
        cat_routed = {r["pair_id"] for r in cat_rows if r["route_success"]}
        n = len(cat_pair_ids)
        cat_stats[cat] = {
            "total": n,
            "geocode_pct": 100 * len(cat_geocoded) / n if n else 0,
            "route_pct": 100 * len(cat_routed) / n if n else 0,
        }

    return {
        "model": model,
        "total_pairs": total_pairs,
        "geocode_success": len(geocode_success_pairs),
        "route_success": len(route_success_pairs),
        "wc_valid": len(wc_valid_pairs),
        "consistent": len(consistent_pairs),
        "post_processing": post_processing_corrections,
        "mean_latency_ms": int(sum(latencies) / len(latencies)) if latencies else 0,
        "failure_modes": failure_modes,
        "cat_stats": cat_stats,
        "failed_pairs": [
            {
                "pair_id": pid,
                "failure_mode": next(
                    (r["failure_mode"] for r in pair_runs[pid] if r["failure_mode"]), "?"
                ),
                "origin": pair_runs[pid][0]["origin"],
                "destination": pair_runs[pid][0]["destination"],
                "detail": next(
                    (r["failure_detail"] for r in pair_runs[pid] if r["failure_detail"]), ""
                )[:120],
            }
            for pid in pairs_seen
            if pid not in route_success_pairs
        ],
    }


def format_experiment1_summary(stats: dict) -> str:
    n = stats["total_pairs"]
    fm = stats["failure_modes"]
    lines = [
        f"Experiment 1 Results — {stats['model']}",
        "─" * 56,
        f"Total pairs:                    {n}",
        f"Geocoding success rate:         {stats['geocode_success']}/{n} ({100*stats['geocode_success']/n:.1f}%)",
        f"Route generation success rate:  {stats['route_success']}/{n} ({100*stats['route_success']/n:.1f}%)",
        f"Wheelchair validity rate:       {stats['wc_valid']}/{n} ({100*stats['wc_valid']/n:.1f}%)",
        f"Consistency rate (all runs):    {stats['consistent']}/{n} ({100*stats['consistent']/n:.1f}%)",
        f"Post-processing correction:     {stats['post_processing']} pairs",
        f"Mean latency (ms):              {stats['mean_latency_ms']}",
        "",
        "By category:",
    ]
    for cat, cs in stats["cat_stats"].items():
        lines.append(
            f"  {cat:<14} ({cs['total']:2d} pairs): "
            f"geocode {cs['geocode_pct']:.0f}%  route {cs['route_pct']:.0f}%"
        )
    lines += [
        "",
        "Failure mode breakdown:",
        f"  A - Geocoding failed:          {fm.get('A', 0)}",
        f"  B - Wrong location resolved:   {fm.get('B', 0)}",
        f"  C - Routing engine no path:    {fm.get('C', 0)}",
        f"  D - Apologetic despite route:  {fm.get('D', 0)}",
        f"  E - Timeout / HTTP error:      {fm.get('E', 0)}",
        "─" * 56,
    ]
    if stats["failed_pairs"]:
        lines.append("")
        lines.append("Failed pairs:")
        for fp in sorted(stats["failed_pairs"], key=lambda x: x["pair_id"]):
            lines.append(
                f"  [{fp['failure_mode']}] {fp['pair_id']:6s}  "
                f"{fp['origin'][:22]} → {fp['destination'][:22]}"
            )
            if fp["detail"]:
                lines.append(f"         {fp['detail'][:100]}")
    return "\n".join(lines)


def format_experiment2_summary(all_stats: list[dict]) -> str:
    header = [
        "Experiment 2 Results — Multi-Model Comparison",
        "┌──────────────────────┬──────────┬──────────┬───────────┬─────────────┬──────────────┐",
        "│ Model                │ Route    │ Geocode  │ WC Valid  │ Consistent  │ Mean Lat(ms) │",
        "│                      │ Success% │ Success% │ %         │ %           │              │",
        "├──────────────────────┼──────────┼──────────┼───────────┼─────────────┼──────────────┤",
    ]
    rows = []
    for s in all_stats:
        n = s["total_pairs"]
        rows.append(
            f"│ {s['model']:<20s} │ {100*s['route_success']/n:7.1f}% │ "
            f"{100*s['geocode_success']/n:7.1f}% │ "
            f"{100*s['wc_valid']/n:8.1f}% │ "
            f"{100*s['consistent']/n:10.1f}% │ "
            f"{s['mean_latency_ms']:>12d} │"
        )
    footer = ["└──────────────────────┴──────────┴──────────┴───────────┴─────────────┴──────────────┘"]

    fm_header = [
        "",
        "Failure modes per model:",
        "┌──────────────────────┬───┬───┬───┬───┬───┐",
        "│ Model                │ A │ B │ C │ D │ E │",
        "│                      │Geo│Loc│Rte│Apo│Err│",
        "├──────────────────────┼───┼───┼───┼───┼───┤",
    ]
    fm_rows = []
    for s in all_stats:
        fm = s["failure_modes"]
        fm_rows.append(
            f"│ {s['model']:<20s} │{fm.get('A',0):3d}│{fm.get('B',0):3d}│"
            f"{fm.get('C',0):3d}│{fm.get('D',0):3d}│{fm.get('E',0):3d}│"
        )
    fm_footer = ["└──────────────────────┴───┴───┴───┴───┴───┘"]

    return "\n".join(header + rows + footer + fm_header + fm_rows + fm_footer)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MyPath evaluation harness")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of ai-core")
    parser.add_argument(
        "--model",
        nargs="+",
        default=["gemini-1.5-flash"],
        help="Model name(s) to evaluate",
    )
    parser.add_argument("--runs", type=int, default=3, help="Runs per model")
    parser.add_argument("--output", default="./eval_results", help="Output directory")
    parser.add_argument(
        "--dataset",
        default=str(_OD_PAIRS_FILE),
        help="Path to OD pairs JSON",
    )
    return parser.parse_args()


def verify_backend(base_url: str) -> bool:
    """Quick check that the backend is reachable."""
    try:
        r = requests.get(f"{base_url}/health", timeout=10)
        if r.status_code == 200:
            print(f"Backend healthy at {base_url}")
            return True
        print(f"Backend /health returned {r.status_code}")
        return False
    except Exception as exc:
        print(f"Backend unreachable at {base_url}: {exc}")
        return False


def smoke_test(base_url: str) -> bool:
    """Send one test query and show raw response before the main run."""
    print("\n── Smoke test ──────────────────────────────────────────────")
    test_pair = {
        "natural_language_query": "Navigate from King Library to Armstrong Student Center",
        "dest_coords": {"lat": 39.5074, "lon": -84.7362},
        "id": "smoke_test",
    }
    session_id = f"smoke_{uuid.uuid4().hex[:8]}"
    result = send_query(base_url, test_pair, session_id)
    print(f"Latency: {result['latency_ms']} ms")
    if result["ok"]:
        data = result["data"]
        print(f"Response message (first 200 chars): {data.get('message','')[:200]}")
        print(f"route_action present: {data.get('route_action') is not None}")
        print(f"response_intent: {data.get('response_intent')}")
        print("Raw response (trimmed):")
        print(json.dumps(data, indent=2)[:800])
        print("── Smoke test PASSED ──")
        return True
    else:
        print(f"Smoke test FAILED: {result['error']}")
        return False


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Load dataset ────────────────────────────────────────────────────────
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"ERROR: Dataset not found at {dataset_path}")
        sys.exit(1)
    pairs = load_dataset(dataset_path)

    # ── Verify backend ──────────────────────────────────────────────────────
    if not verify_backend(args.url):
        print(
            "ERROR: Backend not reachable. Start it with:\n"
            "  make dev    # or: docker compose up --build"
        )
        sys.exit(1)

    # ── Smoke test ──────────────────────────────────────────────────────────
    if not smoke_test(args.url):
        print("ERROR: Smoke test failed. Fix the backend before running evaluation.")
        sys.exit(1)

    # ── Run each model ──────────────────────────────────────────────────────
    all_stats: list[dict] = []
    all_rows: dict[str, list[dict]] = {}

    for model in args.model:
        print(f"\n{'='*60}")
        print(f"MODEL: {model}")
        print(f"{'='*60}")

        outcome = run_model(model, pairs, args.url, args.runs, output_dir)
        if outcome is None:
            continue

        rows, csv_path = outcome
        stats = compute_stats(rows, model, args.runs)
        all_stats.append(stats)
        all_rows[model] = rows

        summary = format_experiment1_summary(stats)
        print("\n" + summary)

    # ── Experiment 1 summary (first model) ─────────────────────────────────
    if all_stats:
        exp1_summary = format_experiment1_summary(all_stats[0])
        exp1_path = output_dir / "experiment1_summary.txt"
        exp1_path.write_text(exp1_summary, encoding="utf-8")
        print(f"\nExperiment 1 summary saved: {exp1_path}")

    # ── Experiment 2 summary (all models) ──────────────────────────────────
    if len(all_stats) > 1:
        exp2_summary = format_experiment2_summary(all_stats)
        exp2_path = output_dir / "experiment2_summary.txt"
        exp2_path.write_text(exp2_summary, encoding="utf-8")
        print(f"\nExperiment 2 summary saved: {exp2_path}")
        print("\n" + exp2_summary)
    elif all_stats:
        print(
            "\n(Only one model ran — Experiment 2 comparison table requires "
            ">1 models. Re-run with multiple --model values.)"
        )

    print("\nDone.")


if __name__ == "__main__":
    main()
