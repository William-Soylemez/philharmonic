"""Build the global GO ID → {name, namespace} map from go-basic.obo.

Run once per data refresh. The resulting `go_terms.json` is uploaded to the
bucket root and consumed by the frontend to resolve GO IDs to human names.

Usage:
    python build_go_terms.py <output_path> [--obo-url URL]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

DEFAULT_OBO_URL = "http://current.geneontology.org/ontology/go-basic.obo"


def _parse_obo(text: str) -> dict[str, dict[str, str]]:
    """Minimal OBO parser: pull id, name, namespace from each [Term] stanza."""
    out: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    in_term = False

    for raw in text.splitlines():
        line = raw.rstrip()
        if line == "[Term]":
            if current and "id" in current:
                out[current["id"]] = {
                    "name": current.get("name", ""),
                    "namespace": current.get("namespace", ""),
                }
            current = {}
            in_term = True
            continue
        if line.startswith("[") and line.endswith("]"):
            if current and "id" in current and in_term:
                out[current["id"]] = {
                    "name": current.get("name", ""),
                    "namespace": current.get("namespace", ""),
                }
            current = None
            in_term = False
            continue
        if not in_term or current is None or not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key in ("id", "name", "namespace") and key not in current:
            current[key] = value

    if current and "id" in current and in_term:
        out[current["id"]] = {
            "name": current.get("name", ""),
            "namespace": current.get("namespace", ""),
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("output_path", type=Path)
    ap.add_argument("--obo-url", default=DEFAULT_OBO_URL)
    ap.add_argument("--obo-file", type=Path, help="use a local .obo file instead of downloading")
    args = ap.parse_args()

    if args.obo_file:
        print(f"reading {args.obo_file}", file=sys.stderr)
        text = args.obo_file.read_text()
    else:
        print(f"downloading {args.obo_url}", file=sys.stderr)
        with urllib.request.urlopen(args.obo_url) as r:
            text = r.read().decode("utf-8")

    terms = _parse_obo(text)
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(json.dumps(terms, separators=(",", ":")))
    print(f"wrote {len(terms)} GO terms → {args.output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
