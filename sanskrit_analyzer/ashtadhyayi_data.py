"""Aṣṭādhyāyī commentaries from the ashtadhyayi.com data repo.

The vidyut bundle carries the bare sūtrapāṭha but only a 9-row Kāśikā stub
and no translation. The ashtadhyayi.com repo has the Kāśikā for all 3983
sūtras, Vasu's English, and a dozen more commentaries. Its README: "You are
free to use this data in your own projects provided that appropriate credits
are mentioned", so the repo vendors all of it under ``data/ashtadhyayi`` with
the credit in SOURCE.md. The wheel ships only CORE_FILES (see pyproject.toml);
the rest (~65 MB) is in a source checkout only.

Resolution order for the data directory:

1. ``ASHTADHYAYI_DATA_DIR`` environment variable
2. ``sanskrit_analyzer/data/ashtadhyayi`` (vendored)

Refresh the vendored copy after bumping COMMIT (resumable)::

    python -m sanskrit_analyzer.ashtadhyayi_data --all

Without ``--all`` only CORE_FILES are fetched (~4.5 MB).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

REPO = "ashtadhyayi-com/data"
COMMIT = "5744762f010d677cfb43f347a42d02796cf615d6"  # master, 2026-09-13

# What the analyzer reads at runtime (see prakriya.sutra_index).
CORE_FILES = ("sutraani/kashika.txt", "sutraani/vasu_english_summary.txt")

# Everything Pāṇinian in the repo. dhatu/dhatuforms_* are vidyut-generated
# paradigms (we run vidyut ourselves), so only the Dhātupāṭha is listed.
ALL_FILES = (
    *(f"sutraani/{name}.txt" for name in (
        "data",  # sūtra text, padaccheda, anuvṛtti, adhikāra, type
        "kashika", "bhashya", "nyaas", "padamanjari",
        "kaumudi", "laghukaumudi", "balamanorama", "tattvabodhini",
        "praudhamanorama", "laghushabdendushekhar", "sudha", "sarala",
        "prakriyasarvasvam", "sutrartha", "sutrartha_english",
        "vasu_english", "vasu_english_summary", "vartika", "sutra_prayogas",
    )),
    "shivasutra/data.txt",
    "pratyahara/data.txt",
    "ganapath/data.txt",
    "dhatu/data.txt",
    "unaadi/data.txt",
    "linganushasanam/data.txt",
    "fit/data.txt",
)

SOURCE_MD = f"""# Aṣṭādhyāyī data

Source: https://github.com/{REPO} at commit `{COMMIT}`,
the data behind https://ashtadhyayi.com.

Credit: ashtadhyayi.com and its contributors. Their terms: "You are free to
use this data in your own projects provided that appropriate credits are
mentioned wherever applicable." Keep this file next to the data wherever
it is copied.

Refreshed by `python -m sanskrit_analyzer.ashtadhyayi_data --all`.
"""


def data_dir() -> Path:
    """Where the data lives: the env override, else the vendored copy."""
    env = os.environ.get("ASHTADHYAYI_DATA_DIR")
    return Path(env) if env else Path(__file__).parent / "data" / "ashtadhyayi"


def load_commentary(name: str, root: Path | None = None) -> dict[str, str]:
    """Return ``{"3.1.91": text}`` for ``sutraani/<name>.txt``; ``{}`` if absent.

    The repo keys sūtras as "31091" (adhyāya, pāda, 3-digit number); empty
    entries are dropped so callers can treat a missing key as "no gloss".
    """
    path = (root or data_dir()) / "sutraani" / f"{name}.txt"
    if not path.is_file():
        return {}
    raw: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
    return {
        f"{k[0]}.{k[1]}.{int(k[2:])}": v.strip()
        for k, v in raw.items()
        if len(k) == 5 and k.isdigit() and v.strip()
    }


def fetch(out: Path, files: tuple[str, ...] = CORE_FILES) -> dict:
    """Download ``files`` at the pinned commit into ``out``; return the manifest."""
    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if manifest.get("commit") != COMMIT:
        manifest = {"repo": REPO, "commit": COMMIT, "files": {}}

    for path in files:
        dest = out / path
        known = manifest["files"].get(path)
        if known and dest.exists() and dest.stat().st_size == known["bytes"]:
            continue
        url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/{path}"
        with urllib.request.urlopen(url, timeout=120) as resp:
            data = resp.read()
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(dest)  # no half-written file survives an interrupt
        manifest["files"][path] = {
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        print(f"  got {path} ({len(data) / 1e6:.1f} MB)")
        manifest_path.write_text(json.dumps(manifest, indent=2))  # resume point

    (out / "SOURCE.md").write_text(SOURCE_MD)
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch Aṣṭādhyāyī commentary data.")
    ap.add_argument("--out", type=Path, default=data_dir())
    ap.add_argument("--all", action="store_true", help="every commentary (~72 MB)")
    args = ap.parse_args(argv)
    manifest = fetch(args.out, ALL_FILES if args.all else CORE_FILES)
    total = sum(f["bytes"] for f in manifest["files"].values())
    print(f"{len(manifest['files'])} files, {total / 1e6:.1f} MB in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
