"""CLI: python -m sanskrit_analyzer.prakriya "verse" [--json]"""
from __future__ import annotations

import argparse
import json
import sys

from sanskrit_analyzer.prakriya import analyze_verse


def _render(record: dict) -> str:
    lines: list[str] = []
    ch = record.get("chandas") or {}
    if ch.get("name"):
        lines.append(f"chandas: {ch['name']}")
    for pada in record["padas"]:
        lines.append(f"\n{pada['surface']}")
        if not pada["analyses"]:
            lines.append("  (no Pāṇinian derivation found)")
        for a in pada["analyses"]:
            lines.append(f"  {a['kind']}  lemma={a['lemma']}  [{a['morph']}]")
            for s in a["prakriya"]:
                text = f" — {s['sutra_text']}" if s["sutra_text"] else ""
                lines.append(f"    {s['step']:>2}. {s['form']}  (A. {s['code']}){text}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sanskrit_analyzer.prakriya",
        description="Analyze a Sanskrit verse down to dhātus with sūtra-cited "
        "derivations.",
    )
    parser.add_argument("verse", nargs="?", help="verse text in any script")
    parser.add_argument("--json", action="store_true", help="emit raw JSON")
    args = parser.parse_args(argv)
    if not args.verse:
        parser.print_usage(sys.stderr)
        return 2
    record = analyze_verse(args.verse)
    print(json.dumps(record, ensure_ascii=False, indent=2) if args.json
          else _render(record))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
