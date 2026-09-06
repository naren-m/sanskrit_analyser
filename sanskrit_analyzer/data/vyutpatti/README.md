# Layer B source — Cologne Digital Sanskrit Dictionaries

Retrieved-vyutpatti layer for the vyutpatti database. All files TSV, SLP1, header row present.

## Provenance

Source: Cologne Digital Sanskrit Dictionaries, Universität zu Köln
(`https://www.sanskrit-lexicon.uni-koeln.de/`), fetched via `pycdsl` from the
`/scans/<DICT>Scan/2020/downloads/` endpoints. Build script: `build_layerb.py`.

| dict | ed. | entries | role |
|---|---|---|---|
| SKD  Śabdakalpadruma | 1886 | 42,531 | **primary Layer B** — parenthetical vyutpatti, often with uṇādi citation |
| VCP  Vācaspatyam | 1873 | 50,135 | secondary — `base—pratyaya` immediately after headword |
| KRM  Kṛdantarūpamālā | 1965 | 2,061 | kṛdanta paradigms; cross-check for Layer A output |
| ARMH Abhidhānaratnamālā | 1861 | 7,907 | kośa attestation |
| ABCH Abhidhānacintāmaṇi | 1896 | 13,568 | kośa attestation |

Licence: CDSL data is freely redistributable for scholarly use; retain this
attribution block in any derived artefact.

## Files

**`vyutpatti-skd.tsv`** — 15 cols.
`key, key_stem, linga, vyutpatti, nirvacana, base, chain, pratyaya, qualifier,
unadi_ref, sutra_quoted, lnum, page, unadi_ref_project, unadi_match`

- `key` is the nominative-singular headword (`kandalaH`); `key_stem` strips final H/M.
- `vyutpatti` is the verbatim parenthetical — **this is the authoritative field**.
- `nirvacana` / `base`+`chain`+`pratyaya` implement the project's vyutpatti-vs-nirvacana
  separation: a Yāska-style gloss (`mandyate stūyate praśasyate veti`) lands in
  `nirvacana`, the Pāṇinian chain (`madi + āran`) in `chain`.
- 34,707 of 42,531 entries carry a parenthetical vyutpatti.

**`vyutpatti-vcp.tsv`** — 7 cols. 15,759 entries yield a clean `base—pratyaya` split.
Keys are stems, not nominatives. Use as a second witness against SKD.

**`krdantarupamala.tsv`, `abhidhanaratnamala.tsv`, `abhidhanacintamani.tsv`** — 4 cols
(`key, lnum, page, text`), plain de-tagged body text.

## Uṇādi crosswalk — read this before trusting any `unadi_ref`

767 SKD entries cite an uṇādi sūtra by number. Those citations follow a **different
recension numbering** from the project's `unadipatha.tsv`. The build resolves each
citation by matching SKD's *quoted sūtra text* against the project file and records
the result:

- **196 `agree`** — SKD number == project number.
- **120 `SHIFTED`** — same sūtra, different number (drift of ±1 to ±2).
  e.g. `bandhuram`: SKD cites uṇā 1.42 *madgurādayaś ca*; project file has it at **1.41**.
- **451 `unverified`** — quoted sūtra not found in the project's 748-sūtra recension.

**Rule: cite `unadi_ref_project`, never `unadi_ref`.** Where `unadi_match` is
`unverified`, the claim is out of the project's primary-source scope and must stay flagged.

## Known parse limits

- The `pratyaya` heuristic prefers a trailing `iti X`; a few entries where the
  parenthetical ends in `… nipātanāt sādhuḥ` mis-assign (e.g. `bandhuraḥ` → `sādhuḥ`
  rather than `uraḥ`). `vyutpatti` remains correct — re-read it before citing.
- Multi-`+` chains are preserved in `chain`; `base` = first element, `pratyaya` = last.
- SKD/VCP are 19th-c. compilations, not Pāṇinian derivations. Treat every entry as a
  **retrieved claim requiring Layer A verification**, not as a derivation.
