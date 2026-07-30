# Gold-standard deficiency list — MVR-1381-RC, sections 1.4.7 / 1.4.8 / 1.4.9 / 1.5 / 1.6 (Tables 16–20, PDF pages 23–27 + 55)

Page references are the PDF page (the printed footer runs one lower, e.g. PDF p.26 = footer "Page 25 of 54").

---

## 1. Table 20 "Maximum" theoretical plates cell is wrong (11477 reported; true maximum is 12601)

**Evidence** — Table 20, System Suitability Results (PDF p.26), Theoretical plates column, individual rows:
Specificity 11400 · Linearity 11477 · LOD and LOQ 9816 · **In-house Equivalency Study 12601** · Precision 11160 · Intermediate Precision 9792.
Summary rows as printed: Minimum 9792, **Maximum 11477**, Mean 11041.

Recomputed from the six individual rows:
- min = 9792 (matches)
- **max = 12601 ≠ 11477 reported**
- mean = 66246 / 6 = 11041.0 (matches exactly)

The 12601 value is not a typo in the individual row: it is the theoretical-plates result in Table 18 for the in-house method (PDF p.24, "Theoretical plates 12601 (NLT 7000)") and is repeated in Table 1 (PDF p.9). Also, the reported Mean of 11041 is only obtainable **with** 12601 in the data set — excluding it gives 53645 / 5 = 10729, not 11041. So the data set is right and the Maximum cell is simply mis-transcribed.

The same erroneous maximum is carried into the overall summary Table 1, System Suitability row (PDF p.9): "Theoretical plates | 9792 | 11477 | 11041".

**Why it is a deficiency** — A summary statistic in a validation/verification report contradicts the individual data it is derived from, and the error propagates to the report's overall summary table. This is a data-integrity / transcription failure (21 CFR 211.194(a) accuracy-of-records expectations; ALCOA "accurate"). It does not change any pass/fail call (limit is NLT 7000, and every value passes), which is precisely why it survived review — but the reported range of the system's performance is understated and the table is not self-consistent.

**Confidence: CERTAIN** (arithmetic verified; internally proven by the correct Mean).

---

## 2. Equivalency acceptance criterion is not met: the USP-method unspecified impurity result (0.15%) exceeds the 0.10% specification, yet the section concludes the criteria were met

**Evidence**
- Table 19, Equivalency study Results (PDF p.24): "Any Unspecified Impurity (Single Largest) | USP method **0.15\*** | In-house method ND". Footnote: "* Largest value of three samples reported."
- Stated acceptance criterion for §1.4.8 (PDF p.25): "The % impurities should be comparable between In-house method and USP method **and all unknown and known impurity should be within the specification.**"
- Specification for unspecified impurities, given in the same criteria block on PDF p.25 (Amneal's Method column): "**Any Unspecified Impurity : NMT 0.10%**". Identical limit stated in §1.1 Introduction (PDF p.5): Any Unspecified Impurity — Manufacturer's Limit NMT 0.10%, Amneal's Limit NMT 0.10%.
- Conclusion for §1.4.8 (PDF p.25): "The results met the acceptance criteria indicating that Amneal's In-house developed method is equivalent to USP compendia method."

Arithmetic: 0.15% vs limit NMT 0.10% → **exceeds the limit by 0.05% absolute (50% relative)**. Direction confirmed: the result is *above* a not-more-than limit.

**Why it is a deficiency** — Internal contradiction between the report's own acceptance criterion, the specification it cites on the same page, and its own conclusion. An unspecified (unknown) impurity was reported at 0.15% in the drug-substance lot (L00036941) used for verification, above the 0.10% unspecified-impurity limit applicable to that material, and the report states without qualification that all impurities were within specification. The reviewer needs (a) identification/justification of that peak, (b) a statement of whether the lot complies, and (c) correction of the conclusion. Note this is *not* a case of judging the USP method against in-house system-suitability criteria: the 0.10% unspecified-impurity limit is the **product** specification for the material, applicable to whichever method measures it.

**Confidence: CERTAIN** (numeric comparison verified; criterion, specification and contradicting conclusion are all in the document).

---

## 3. The two methods are not "comparable" for the single largest unspecified impurity — 0.15% by the USP method vs not detected in-house — which is the central claim of the equivalency study

**Evidence**
- Table 19 (PDF p.24): Any Unspecified Impurity (Single Largest) — USP method **0.15%**, In-house method **ND**. Every other row agrees closely (Total impurities 0.14% vs 0.13%).
- Criterion (PDF p.25): "The % impurities **should be comparable between In-house method and USP method**…"
- The in-house method's sensitivity does not explain the discordance: Table 7, LOD (PDF p.16) gives in-house LODs of 0.01% (Estradiol), 0.01% (Δ9,11-Estradiol), 0.03% (17 α-Estradiol), 0.02% (Estrone) — i.e. a 0.15% peak is roughly 5–15× the in-house LOD.
- Conclusion (PDF p.25) nonetheless declares the methods equivalent.

**Why it is a deficiency** — The largest single unspecified impurity found by the compendial method is absent from the in-house result for the same material, and this cannot be attributed to detection limit. It points to a selectivity/elution difference (a peak the in-house method does not resolve, or one eluting outside its run window), which is exactly the risk an equivalency study exists to rule out. The report does not investigate or discuss the discrepancy before concluding equivalency. (This is raised as a failure of the report's own "comparable" criterion, not as an objection to reporting a below-LOD result as ND.)

**Confidence: LIKELY** (defensible reviewer judgement, supported by in-document LOD data).

---

## 4. Table 19 is internally inconsistent for the USP method: total impurities (0.14%) is lower than the single largest unspecified impurity (0.15%), and the footnote shows the two cells come from different samples

**Evidence** — Table 19 (PDF p.24), USP method column: "Any Unspecified Impurity (Single Largest) 0.15\*" and "Total Impurities 0.14". Footnote applies only to the 0.15 cell: "* Largest value of three samples reported." The Total Impurities cell carries no such qualifier.

Arithmetic: for any single sample, total impurities must be ≥ the largest individual impurity. 0.14 < 0.15 is impossible on a common-sample basis.

**Why it is a deficiency** — As presented the column is self-contradictory; the footnote resolves it only by revealing that the two cells are drawn from **different samples**, which means the USP-vs-in-house comparison in Table 19 is not made on a like-for-like sample basis and the totals cannot be interpreted. The number of samples and the sample identity behind each cell are not stated, so the "comparable results" claim rests on an undefined basis. (The same 0.15% value appears in Table 1, PDF p.9, with no footnote at all.)

**Confidence: LIKELY** (arithmetic impossibility on its face; the footnote supplies an explanation but exposes an unstated, inconsistent reporting basis).

---

## 5. §1.4.7 conclusion asserts a storage condition ("stored at room temperature") that is documented nowhere in the study description or in Tables 16–17

**Evidence**
- §1.4.7 study description (PDF p.23) states only: solutions "were prepared and analyzed as per the analytical procedure over a period of time using freshly prepared standard solution… up to 72 hours". No storage temperature, location (bench / autosampler / refrigerator), or light-protection condition is given, and neither Table 16 nor Table 17 records one.
- Conclusion, §1.4.7 (PDF p.23): "The data indicates that the standard solution and the sample solution are **stable up to 72 hours when stored at room temperature**." The same unsupported condition is repeated in §1.5 Conclusions (PDF p.27).
- A whole-document search finds "room temperature" **only** in these two conclusion statements — never in the experimental description.

**Why it is a deficiency** — Solution stability is only usable if the condition under which it was demonstrated is defined (ICH Q2(R1) / USP <1225>–<1226>: the conditions of use must be established and documented). The report's conclusion — which is what a QC analyst would rely on to hold solutions for 72 hours — states a condition that the study record does not support, so the stated hold time cannot be tied to any verified condition.

**Confidence: LIKELY**.

---

## 6. §1.5 Conclusions does not address all verification characteristics evaluated, while claiming that it does

**Evidence**
- Verification attributes evaluated, per §1.1 (PDF pp.5–6): 1 Specificity, 2 Linearity, 3 Limit of Detection, 4 Limit of Quantitation, 5 Absorptivity Factor, 6 Precision (system / method / intermediate), 7 Stability of Analytical Solutions, 8 Equivalency with the USP Method, 9 System Suitability. Each has its own section and acceptance criteria (§1.4.3 Table 7–8, §1.4.4 Table 9–10, §1.4.5 Table 11, §1.4.9 Table 20).
- §1.5 Conclusions (PDF p.27) bullets cover only: Specific, Linear, Precise, Stability of solution, Equivalency with the USP Method. **No conclusion is drawn on Limit of Detection, Limit of Quantitation, Absorptivity Factor, or System Suitability.**
- Closing sentence (PDF p.27): "**The data for each verification characteristic described in this report** meets the acceptance criteria **with respect to specificity, linearity, precision and ruggedness**." The sentence claims coverage of every characteristic but enumerates four, omitting even solution stability and USP equivalency, which do have bullets above it.

**Why it is a deficiency** — The overall conclusion of a method verification report must dispose of every characteristic evaluated. Here four evaluated characteristics receive no concluding statement, and the summary sentence is internally inconsistent with the bullet list immediately above it (it claims completeness while listing a narrower set). The LOD/LOQ omission is the substantive one — those sections carry the study's weakest precision data (Table 8, Estradiol %RSD 18.9% at LOD; Table 10, Estradiol %RSD 9.8% at LOQ against an NMT 10.0% criterion).

**Confidence: LIKELY**.

---

## 7. Table 20 / §1.4.9 conclusion claims system suitability across the "entire verification study" but the compilation omits the solution-stability runs

**Evidence**
- §1.4.9 narrative (PDF p.25): "The system suitability data **from overall validation study** is compiled in the form of minimum, maximum and average. The results are reported in Table 20."
- Table 20 (PDF p.26) contains exactly six rows: Specificity, Linearity, LOD and LOQ, In-house Equivalency Study, Precision, Intermediate Precision.
- The solution-stability study (§1.4.7) was a separate set of chromatographic runs over 72 hours with its own raw-data references (Table 16: "Notebook # 8135, Page # 50, 51 and Notebook # 8133, Page # 41, 44, 55"; Table 17: "Notebook # 8135, Page # 51 and Notebook # 8133, Page # 42, 44, 45, 56") — none of which appear in Table 20, whose single reference is "Notebook # 8133, Page # 68".
- Conclusion, §1.4.9 (PDF p.26): "The system suitability criteria met the acceptance criteria **during the entire verification study**."

**Why it is a deficiency** — The conclusion asserts coverage broader than the compiled data supports: system suitability for the 72-hour stability analyses (a named study in the report, run on separate days against freshly prepared standards) is neither tabulated nor summarised anywhere, so the claim that suitability was met "during the entire verification study" is not demonstrated for those runs. This is a scope mismatch between the table's stated basis and the conclusion drawn from it, not a demand for every individual injection. (Absorptivity Factor, §1.4.5, is a calculation off the linearity data — Notebook 8135 p.25 vs p.24 — so its absence from Table 20 is not itself a gap.)

**Confidence: LIKELY**.

---

## Checks performed that came out CLEAN (deliberately not reported as deficiencies)

- **Table 16** (standard solution, initial 6431): drifts recomputed = −0.68% (24 h, reported 0.7), −4.18% (48 h, reported 4.2), −4.54% (72 h, reported 4.5). All correct; all within NMT ±10.0%.
- **Table 17** (sample solution): Δ9,11-Estradiol −1.25 / −0.93 / −3.60 (reported 1.3 / 0.9 / 3.6); 17 α-Estradiol +0.95 / +2.06 / −0.35 (reported 1.0 / 2.1 / 0.3); Estrone +2.02 / +3.15 / +1.00 (reported 2.0 / 3.1 / 1.0). All correct at displayed precision; all within NMT ±10.0%. All three known impurities are covered, as the criterion requires.
- **Table 18 means and %RSDs**: USP mean = 68100454 / 5 = 13620090.8 → 13620091 (reported), %RSD = 0.55 → 0.5 (reported), within NMT 2.0. In-house mean = 38650 / 6 = 6441.67 → 6442 (reported), %RSD = 1.80 → 1.8 (reported), within NMT 6.0. Both correct.
- **Table 18 pass/fail, each method against its own criteria**: USP — tailing 1.0 (NMT 1.5) pass, resolution 2.6 (NLT 1.0) pass, plates 5656 (NLT 800) pass. In-house — tailing 1.3 (0.9–1.5) pass, resolution 3.1 (NLT 2.5) pass, plates 12601 (NLT 7000) pass. The in-house column also passes the USP monograph criteria. No breach.
- **Table 18 "N/A" for USP injection #6**: five replicate injections are permissible under USP <621> when the RSD requirement is ≤ 2.0% (here 0.5% against NMT 2.0%). Not a deficiency, and judging it against the in-house six-injection criterion would be an error.
- **Table 20 summary integrity, other three columns**: %RSD min 0.6 / max 3.6 / mean 14.3÷6 = 2.38 → 2.4 — all match. Tailing min 1.2 / max 1.3 / mean 7.3÷6 = 1.22 → 1.2 — all match. Resolution min 2.8 / max 3.1 / mean 17.8÷6 = 2.97 → 3.0 — all match. Only the theoretical-plates Maximum is wrong (finding 1).
- **Table 20 individual results vs criteria**: every value passes (%RSD max 3.6 vs NMT 6.0; tailing 1.2–1.3 within 0.9–1.5; resolution min 2.8 vs NLT 2.5; plates min 9792 vs NLT 7000). No individual system-suitability failure exists in this table.
- **Table 20 traceability**: Precision row (0.6 / 1.2 / 3.0 / 11160) = Table 12 and Table 14 Analyst A; Intermediate Precision row (3.4 / 1.2 / 2.8 / 9792) = Table 14 Analyst B; In-house Equivalency Study row (1.8 / 1.3 / 3.1 / 12601) = Table 18 in-house column. All consistent.
- **Table 19 in-house column self-consistency**: Δ9,11 0.00 + 17 α 0.13 + Estrone ND = 0.13 = reported Total 0.13. Consistent. Known-impurity results within their limits (Δ9,11 0.00 vs NMT 0.1%; 17 α 0.13 vs NMT 0.25%; total 0.13 vs NMT 0.5%).
- **Table 19 "N/A" cells for the USP method** (Δ9,11-Estradiol, 17 α-Estradiol, Estrone): those impurities are outside the USP method's declared scope — excluded per instruction.
- **§1.5 linearity claim** ("linear … from about LOQ to 150% of the specification level") is supported by §1.4.2 / Table 3, which runs level 1 = 20% (LOQ) through level 7 = 150%. No finding.
- **§1.6 History**: content (Version 01 original issue, PW-13-0018; Version 02 footnote added to Table 19 + reformat, CC_2016_0203) is factually consistent with the document as issued — the Table 19 footnote is present. The table has no date or approver column, but that is a documentation-format observation rather than a provable deficiency, so it is not listed.

TOTAL: 7 (CERTAIN: 2, LIKELY: 5)
