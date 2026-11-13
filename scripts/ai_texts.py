"""Draft family letters and clinician briefs.

Default is a dry run: print prompts and a token estimate. No model is called.
--run is for a later approved job and refuses to start without its environment.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from screen.ai_check import check
from screen.ai_prompt import KINDS, build_prompt

SAMPLES = ROOT / "data" / "samples"


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / 4) if text else 0


def estimate_output_tokens(kind: str) -> int:
    """Cap, not a reply: word limit, 5 characters a word, English and Arabic."""
    words = 160 if kind == "family_letter" else 140
    return math.ceil(words * 5 * 2 / 4)


def session_paths(samples: Path, only: str | None) -> list[Path]:
    paths = []
    for path in sorted(samples.glob("*.json")):
        if path.name == "index.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if "participant" not in data:
            continue
        pid = (data.get("participant") or {}).get("pid")
        if only and pid != only:
            continue
        paths.append(path)
    return paths


def live_config(system: str):
    from google.genai import types
    return types.GenerateContentConfig(
        temperature=0.2,
        response_mime_type="application/json",
        system_instruction=system,
    )


def make_client(project: str):
    from google import genai
    return genai.Client(
        enterprise=True,
        project=project,
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
    )


def generate(client, model: str, system: str, user: str) -> str:
    resp = client.models.generate_content(
        model=model,
        contents=user,
        config=live_config(system),
    )
    text = getattr(resp, "text", None)
    if not text:
        raise RuntimeError("model returned no text")
    return text


def problems_for_reply(raw: str, session: dict, kind: str) -> list[str]:
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        return ["reply was not JSON"]
    if not isinstance(body, dict) or "en" not in body or "ar" not in body:
        return ["reply JSON needs en and ar"]
    problems = []
    for lang in ("en", "ar"):
        for item in check(str(body[lang]), session, kind):
            problems.append(f"{lang}: {item}")
    return problems


def store_kind(session: dict, kind: str, raw: str, model: str) -> list[str]:
    problems = problems_for_reply(raw, session, kind)
    if problems:
        return problems
    body = json.loads(raw)
    session.setdefault("ai_texts", {})
    session["ai_texts"][kind] = {
        "en": body["en"],
        "ar": body["ar"],
        "model": model,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "stored-sample",
    }
    return []


def store_from_client(path: Path, client, model: str, max_calls: int) -> int:
    session = json.loads(path.read_text(encoding="utf-8"))
    calls = 0
    changed = False
    for kind in KINDS:
        if calls >= max_calls:
            print(f"stopped at max calls {max_calls}")
            break
        system, user = build_prompt(session, kind)
        raw = generate(client, model, system, user)
        calls += 1
        problems = store_kind(session, kind, raw, model)
        if problems:
            print(f"{path.name} {kind}")
            for item in problems:
                print(item)
            continue
        changed = True
    if changed:
        path.write_text(
            json.dumps(session, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return calls


def run_dry(samples: Path, only: str | None, price_in: float, price_out: float) -> None:
    print("dry run, no model call")
    total_in = 0
    total_out = 0
    files = session_paths(samples, only)
    for path in files:
        session = json.loads(path.read_text(encoding="utf-8"))
        pid = (session.get("participant") or {}).get("pid") or path.stem
        for kind in KINDS:
            system, user = build_prompt(session, kind)
            tokens_in = estimate_tokens(system + user)
            tokens_out = estimate_output_tokens(kind)
            cost = (tokens_in * price_in + tokens_out * price_out) / 1_000_000
            total_in += tokens_in
            total_out += tokens_out
            print(f"=== {pid} {kind} ===")
            print("--- system ---")
            print(system)
            print("--- user ---")
            print(user)
            print(
                f"tokens_in={tokens_in} tokens_out={tokens_out} "
                f"cost_usd={cost:.6f}"
            )
    total_cost = (total_in * price_in + total_out * price_out) / 1_000_000
    print(
        f"TOTAL files={len(files)} tokens_in={total_in} "
        f"tokens_out={total_out} cost_usd={total_cost:.6f}"
    )


def run_live(samples: Path, only: str | None, model: str, project: str, max_calls: int) -> None:
    client = make_client(project)
    calls = 0
    for path in session_paths(samples, only):
        if calls >= max_calls:
            print(f"stopped at max calls {max_calls}")
            break
        calls += store_from_client(path, client, model, max_calls - calls)
    print(f"calls={calls}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Draft screening texts. Default is a dry run.")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts and a cost estimate. Default.")
    parser.add_argument("--run", action="store_true", help="Call the model. Needs an approved project.")
    parser.add_argument("--price-in", type=float, required=True, help="US$ per million input tokens.")
    parser.add_argument("--price-out", type=float, required=True, help="US$ per million output tokens.")
    parser.add_argument("--only", default=None, help="One participant id.")
    parser.add_argument("--max-calls", type=int, default=20)
    parser.add_argument("--samples", type=Path, default=SAMPLES)
    args = parser.parse_args(argv)
    if args.run and args.dry_run:
        print("Pass only one of --run or --dry-run.", file=sys.stderr)
        return 2
    if args.run:
        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
        model = os.environ.get("NODAL_AI_MODEL", "").strip()
        if not project or not model:
            print(
                "GOOGLE_CLOUD_PROJECT and NODAL_AI_MODEL are required",
                file=sys.stderr,
            )
            return 2
        run_live(args.samples, args.only, model, project, args.max_calls)
        return 0
    run_dry(args.samples, args.only, args.price_in, args.price_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
