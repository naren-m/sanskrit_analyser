#!/usr/bin/env python3
"""
Layer B builder: Cologne Digital Sanskrit Dictionaries -> project TSVs.

Sources (SLP1, from sanskrit-lexicon.uni-koeln.de via pycdsl):
  SKD  Sabdakalpadruma (1886)   -- vyutpatti in parentheses, often with unadi citation
  VCP  Vacaspatyam (1873)       -- vyutpatti as `base—pratyaya` right after headword
  KRM  Krdantarupamala (1965)   -- krdanta paradigms
  ARMH Abhidhanaratnamala       -- kosa attestation
  ABCH Abhidhanacintamani       -- kosa attestation

Outputs TSV, SLP1 throughout, to match project convention.
"""
import re, sqlite3, os, sys

DICTDIR = "/home/claude/cdsl/dict"
OUT = "/home/claude/out"
os.makedirs(OUT, exist_ok=True)

TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")

def rows(d):
    p = f"{DICTDIR}/{d}/web/sqlite/{d.lower()}.sqlite"
    con = sqlite3.connect(p)
    return con.execute(f"select key, lnum, data from {d.lower()}")

def body(data):
    m = re.search(r"<body>(.*?)</body>", data, re.S)
    raw = m.group(1) if m else data
    return WS.sub(" ", TAG.sub(" ", raw)).strip()

def page(data):
    m = re.search(r"<pc>(.*?)</pc>", data)
    return m.group(1) if m else ""

# ---------------------------------------------------------------- SKD
# `kandalaH , puM, (kadi + alac .) kanakam . ...`
SKD_HEAD = re.compile(r"^(?P<key>\S+)\s*,\s*(?P<lin>[^,()]*),\s*\((?P<vy>.*?)\)")
UNADI = re.compile(r"uRA0\s*(\d+)\s*\.\s*(\d+)")
SUTRA = re.compile(r"\u201c([^\u201d]{2,80})\u201d")   # quoted sutra text
PLUS = re.compile(r"^(?P<base>[^+]{1,40}?)\s*\+\s*(?P<rest>.*)$")

def split_vy(vy):
    """Separate Yaska-style nirvacana gloss from the Paninian base+pratyaya."""
    nirv = base = prat = qual = ""
    if "+" not in vy:
        return vy.strip(), "", "", "", ""
    left, right = vy.split("+", 1)
    # nirvacana = everything up to the last sentence break before the base
    parts = re.split(r"\s\.\s", left)
    base = parts[-1].strip()
    nirv = " . ".join(x.strip() for x in parts[:-1]).strip()
    right = right.strip().rstrip(".").strip()
    # trailing "iti X" is the authoritative pratyaya name
    im = re.search(r"iti\s+([^\s.\u201c\u201d]+)\s*\.?\s*$", right)
    if im:
        prat = im.group(1)
        qual = right[:im.start()].strip(" .")
    else:
        toks = [t for t in re.split(r"[\s.]+", right) if t]
        prat = toks[-1] if toks else ""
        qual = " ".join(toks[:-1])
    qual = re.sub(r"[\u201c\u201d]", "", qual).strip(" .")
    chain_parts = [base] + [re.sub(r"[\u201c\u201d]", "", x).strip(" .") for x in vy.split("+")[1:]]
    chain = " + ".join(x for x in chain_parts if x)
    return nirv, base, prat, qual, chain


def skd():
    out = [("key", "key_stem", "linga", "vyutpatti", "nirvacana", "base", "chain", "pratyaya",
            "qualifier", "unadi_ref", "sutra_quoted", "lnum", "page")]
    n_vy = 0
    for key, lnum, data in rows("SKD"):
        b = body(data)
        m = SKD_HEAD.match(b)
        vy = nirv = base = prat = qual = uref = squote = chain = ""
        linga = ""
        if m:
            linga = m.group("lin").strip()
            vy = WS.sub(" ", m.group("vy")).strip()
            n_vy += 1
            nirv, base, prat, qual, chain = split_vy(vy)
            um = UNADI.search(vy)
            if um:
                uref = f"{um.group(1)}.{um.group(2)}"
            sm = SUTRA.search(vy)
            if sm:
                squote = sm.group(1).strip()
        stem = re.sub(r"(H|M)$", "", key)
        out.append((key, stem, linga, vy, nirv, base, chain, prat, qual, uref, squote,
                    str(lnum), page(data)))
    write("vyutpatti-skd.tsv", out)
    print(f"SKD: {len(out)-1} entries, {n_vy} with a parenthetical vyutpatti")

# ---------------------------------------------------------------- VCP
# `kandala  tri0 kadi—alac . 1 kalApe ...`
VCP_HEAD = re.compile(
    r"^(?P<key>\S+)\s+(?P<lin>(?:tri0|pu0|na0|strI|avya0)?)\s*(?P<base>[^\u2014.]{1,40}?)\u2014(?P<prat>[^.\u2014]{1,40}?)\s*\.")

def vcp():
    out = [("key", "linga", "base", "pratyaya", "head_segment", "lnum", "page")]
    n_vy = 0
    for key, lnum, data in rows("VCP"):
        b = body(data)
        m = VCP_HEAD.match(b)
        linga = base = prat = ""
        if m:
            linga = m.group("lin")
            base = m.group("base").strip()
            prat = m.group("prat").strip()
            n_vy += 1
        out.append((key, linga, base, prat, b[:200], str(lnum), page(data)))
    write("vyutpatti-vcp.tsv", out)
    print(f"VCP: {len(out)-1} entries, {n_vy} with a parsed base\u2014pratyaya")

# ---------------------------------------------------------------- plain dumps
def dump(d, fname):
    out = [("key", "lnum", "page", "text")]
    for key, lnum, data in rows(d):
        out.append((key, str(lnum), page(data), body(data)))
    write(fname, out)
    print(f"{d}: {len(out)-1} entries -> {fname}")

def write(name, rows_):
    with open(f"{OUT}/{name}", "w", encoding="utf-8") as f:
        for r in rows_:
            f.write("\t".join(x.replace("\t", " ").replace("\n", " ") for x in r) + "\n")

# ------------------------------------------------- unadi crosswalk to project
def load_project_unadi(path="/mnt/project/unadipatha.tsv"):
    idx = {}
    for line in open(path, encoding="utf-8"):
        parts = line.rstrip("\n\r").split("\t")
        if len(parts) < 2 or parts[0] == "code":
            continue
        idx[norm(parts[1])] = parts[0]
    return idx


def norm(t):
    return re.sub(r"[^a-zA-Z]", "", t)


def crosswalk():
    idx = load_project_unadi()
    src = f"{OUT}/vyutpatti-skd.tsv"
    lines = [l.rstrip("\n").split("\t") for l in open(src, encoding="utf-8")]
    hdr = lines[0] + ["unadi_ref_project", "unadi_match"]
    i_ref = hdr.index("unadi_ref"); i_q = hdr.index("sutra_quoted")
    out = [tuple(hdr)]
    agree = disagree = unresolved = 0
    for r in lines[1:]:
        cited, quoted = r[i_ref], r[i_q]
        proj, status = "", ""
        if quoted:
            proj = idx.get(norm(quoted), "")
        if cited and proj:
            status = "agree" if cited == proj else "SHIFTED"
            agree += status == "agree"; disagree += status == "SHIFTED"
        elif cited and not proj:
            status = "unverified"; unresolved += 1
        out.append(tuple(r + [proj, status]))
    write("vyutpatti-skd.tsv", out)
    print(f"unadi crosswalk: {agree} agree, {disagree} SHIFTED, {unresolved} unverified")


if __name__ == "__main__":
    skd(); vcp()
    dump("KRM", "krdantarupamala.tsv")
    dump("ARMH", "abhidhanaratnamala.tsv")
    dump("ABCH", "abhidhanacintamani.tsv")
    crosswalk()
