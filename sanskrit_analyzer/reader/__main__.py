"""CLI: python -m sanskrit_analyzer.reader "verse" [--no-llm] [--json] [--trace]"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from sanskrit_analyzer.reader.read import read_sloka


def render(record: dict, show_trace: bool = False) -> str:
    out: list[str] = [record["input"]["iast"]]
    ch = record.get("chandas") or {}
    if ch.get("name"):
        out.append(f"meter: {ch.get('name_iast') or ch['name']}"
                   + (f" ({ch['ganas']})" if ch.get("ganas") else ""))
    s = record["stats"]
    out.append(f"words: {s['words']}, verified: {s['verified']} {s['by_source']}")
    sp = record.get("split")
    if sp:
        verdict = "licensed" if sp["licensed"] else "NOT licensed"
        sutras = ", ".join(sp["sutras"]) or "-"
        out.append(f"split: {verdict} by sandhi rules, "
                   f"{sp['unruled_junctions']} unruled junctions, sūtras {sutras}\n")
    else:
        out.append("")
    interp = record.get("interpretation") or {}
    glosses = {w["index"]: w for w in interp.get("words") or [] if isinstance(w, dict)}
    for w in record["words"]:
        mark = "✓" if w["verified"] else "?"
        surface = w.get("compound_surface_iast") or w["surface_iast"]
        feats = " ".join(str(v) for k, v in w["features"].items() if k != "pada")
        g = glosses.get(w["index"], {})
        out.append(f"{mark} {w['index']:>2} {surface:<22} {w['lemma']:<12} {w['kind']:<9} "
                   f"{feats}" + (f"  — {g.get('gloss')} [{g.get('role')}]" if g else ""))
        dh = w.get("dhatu") or {}
        if dh.get("root"):
            out.append(f"       dhātu {dh['root']} ({dh.get('code')}, {dh.get('artha')}"
                       f"{'; ' + dh['gloss_en'] if dh.get('gloss_en') else ''})")
        for m in w.get("compound_members") or []:
            out.append(f"       member {m['lemma']} {'✓' if m['verified'] else '?'}")
        for note in w.get("notes") or []:
            out.append(f"       note: {note}")
        if show_trace:
            for st in w.get("trace") or []:
                out.append(f"         {st['step']:>2}. {st['form']}  (A. {st['code']})")
    if interp:
        if interp.get("error"):
            out.append(f"\nLLM: {interp['error']}")
        else:
            idx = {w["index"]: (w.get("compound_surface_iast") or w["surface_iast"])
                   for w in record["words"]}
            out.append("\nanvaya: " + " ".join(idx.get(i, "?") for i in interp.get("anvaya") or []))
            out.append(f"translation: {interp.get('translation')}")
            out.append(f"explanation: {interp.get('explanation')}")
            checks = ("passed" if interp.get("checks_passed")
                      else "FAILED: " + "; ".join(interp.get("check_errors", [])))
            out.append(f"[{interp['model']}, checks {checks}]")
    return "\n".join(out)


def render_translation(record: dict) -> str:
    """Verse, meter, translation: the short form for --translate."""
    from sanskrit_analyzer.models.scripts import Script
    from sanskrit_analyzer.utils import transliterate

    out = [transliterate(record["input"]["slp1"], Script.SLP1, Script.DEVANAGARI),
           record["input"]["iast"]]
    ch = record.get("chandas") or {}
    if ch.get("name"):
        out.append(f"meter: {ch.get('name_iast') or ch['name']}")
    tr = record.get("translation") or {}
    out.append("")
    out.append(tr.get("translation") or f"(no translation: {tr.get('error', 'LLM unavailable')})")
    s = record["stats"]
    out.append(f"\n[{s['verified']}/{s['words']} words verified; split by {record['segmenter']}; "
               f"{tr.get('model', '')}]")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m sanskrit_analyzer.reader")
    ap.add_argument("verse", help="one verse, any script")
    ap.add_argument("--no-llm", action="store_true", help="skip the meaning layer")
    ap.add_argument("--translate", action="store_true",
                    help="print only the verse, its meter and an English translation")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--trace", action="store_true", help="print sūtra traces")
    ap.add_argument("--model", default=None)
    ap.add_argument("--proposer", choices=("byt5", "slm", "best", "cascade"), default="byt5",
                    help="who proposes the split: ByT5, the DCS char model (SANSKRIT_SLM_CKPT), "
                    "or best of both")
    args = ap.parse_args(argv)
    logging.disable(logging.WARNING)
    if args.translate:
        record = read_sloka(args.verse, model=args.model, proposer=args.proposer, translate=True)
        sys.stdout.write((json.dumps(record, ensure_ascii=False, indent=2) if args.json
                          else render_translation(record)) + "\n")
        return 0
    record = read_sloka(args.verse, llm=not args.no_llm, model=args.model, proposer=args.proposer)
    if args.json:
        output = json.dumps(record, ensure_ascii=False, indent=2)
    else:
        output = render(record, args.trace)
    sys.stdout.write(output + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
