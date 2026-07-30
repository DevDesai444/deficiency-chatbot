# Ground truth — Pass D (cross-cutting / cross-document consistency)

Document: Estradiol, USP (Hemihydrate, Micronized) — 3.2.S.4.3 Verification of Analytical
Procedure for Related Compounds, Report No. MVR-1381-RC, Version 02.
Page numbers below are **PDF pages** (= printed footer page + 1), matching the parsed output.

---

## What was checked and came out CLEAN (recorded so these are not re-flagged)

Every one of these was recomputed and matched; they are deliberately **not** findings.

1. **Table 1 (pp. 6–9) vs source Tables 2–20 — value-by-value.** All restated values agree:
   linearity r (0.998/0.999/0.999/0.998 vs T3–T6); LOD % and %RSD (0.01/18.9, 0.01/10.0,
   0.03/11.7, 0.02/17.9 vs T7/T8); LOQ % and %RSD (0.02/9.8, 0.02/3.5, 0.05/9.1, 0.04/8.8 vs
   T9/T10); AF (N/A, 0.40, 1.03, 0.96 vs T11); system precision 0.6/1.2/3.0/11160 vs T12;
   method precision means, ranges, %RSD vs T13; ruggedness system precision A & B vs T14;
   ruggedness recoveries and the three analyst differences (2.5, 1.7, 0.8) vs T15; both stability
   tables vs T16/T17; equivalency system suitability and impurity results vs T18/T19; system
   suitability Min/Max/Mean vs T20. The only mismatch found anywhere in this comparison is
   Finding 1 below, and Table 1 reproduces the Table 20 error faithfully (so the error originates
   in Table 20).
2. **Every Mean / Min / Max / %RSD in the report was recomputed from the individual rows**
   (Tables 8, 10, 12, 13, 14, 15, 18, 20 and the Table 1 restatements). All means and all %RSD
   values are correct to the displayed precision. Example checks: T8 Estradiol mean 629.33→629,
   RSD 18.88→18.9; T10 17α mean 3297.5→3298, RSD 9.09→9.1; T14 Analyst B mean 6419.7→6420,
   RSD 3.36→3.4; T15 17α Analyst B mean 99.12→99.1, RSD 5.08→5.1; T18 USP mean 13,620,090.8→
   13,620,091 (n = 5), in-house mean 6441.7→6442, RSD 1.80→1.8. Only the single Max in Table 20
   fails (Finding 1).
3. **Linearity regressions (T3–T6, pp. 11–14).** Least-squares fits reproduce every reported
   slope and intercept exactly (e.g. Estradiol 6920.93 / −377.49; Δ9,11 16483.00 / −285.56;
   17α 6731.36 / −704.96; Estrone 6994.00 / −480.38) and the reported "correlation coefficient"
   equals r² at 3 dp for all four analytes.
4. **Table 11 Absorptivity Factor (p. 18) traces to the linearity data.** The four "Response"
   values (6559.876 / 16262.039 / 6371.492 / 6871.372) are exactly the mean of area÷concentration
   at linearity levels 3, 5 and 7 (60 %, 100 %, 150 %) from Tables 3–6, and the response factors
   and AF (1/RF) follow arithmetically. No deficiency here.
5. **Appendix chromatograms vs body tables.** Appendix 8 (100 % linearity) areas 6645 / 16315 /
   16461 / 13979 = Tables 3–6 level 5 exactly; Appendix 9 (LOD) 677 / 1296 / 1671 / 914 = Table 8
   injection #1 exactly; Appendix 10 (LOQ) 1470 / 3374 / 3536 / 2507 = Table 10 injection #1
   exactly; Appendix 12 Estradiol area 6420 = Table 12 injection #1; Appendix 11 (system
   suitability soln) tailing 1.2, 17α resolution 3.0, Estradiol plate count 11160 = Table 12's
   three system-suitability entries; Appendix 7 (spiked sample) areas 17680 / 24708 / 13143 =
   Table 17 "Initial" row exactly; Appendix 6 (diluent) shows "Missing" at all four analyte
   retention times, supporting the specificity claim.
6. **All % Drift values (T16, T17)** recomputed from the peak areas — all nine correct.
   **All RRTs (T2)** recomputed from RT ÷ 12.0 min — 0.87 / 1.12 / 1.39 correct.
7. **Reference-standard purities vs CoAs.** 99.9 % (Estradiol, Appx 1 "0.999 mg/mg"), 98.4 %
   (Δ9,11, Appx 2), 99.50 % (17α, Appx 3 HPLC purity), 99.9 % (Estrone, Appx 4) — all four
   numbers match their CoAs. (But see Finding 4 for the basis on which Estradiol's is stated.)
8. **Specification limits stated in three places** (p. 5 intro table, p. 25 Amneal column, and
   the per-table criteria) are mutually consistent: Δ9,11 NMT 0.1 %, 17α NMT 0.25 %, Estrone
   NMT 0.2 %, any unspecified NMT 0.10 %, total NMT 0.5 %.
9. **Concentration/level self-consistency.** LOQ concentrations (T9) equal the linearity level-1
   concentrations; the 100 % linearity level equals the specification level for each analyte
   (0.0978 %, 0.1002 %, 0.2554 %, 0.1999 % of a 1000 µg/mL sample). Consistent.
10. **Table 18 USP injection #6 = "N/A"** is *not* reported: USP <621> permits five replicate
    injections when RSD ≤ 2.0 %, the reported mean and %RSD are both computed on n = 5, and the
    USP criterion quoted on p. 25 does not fix an injection count.
11. Notebook/page cross-references in Table 1 were checked against every source table
    (8133/42, 8135/24-21-22-23, 8135/33 & 32, 8135/25, 8133/43+47, 8133/47-49, 8135/44+46,
    8135/46-48, 8135/50+51 & 8133/41+44+55, 8133/54+57+65, 8133/57+66, 8133/68) — all agree
    except Finding 2.

---

## FINDINGS

### Finding 1 — Table 20 "Maximum" theoretical plates is not the maximum of the tabulated data (arithmetic error, propagated into Table 1)

**Evidence**
- Table 20, System Suitability Results, p. 26 (printed p. 25), "Theoretical plates (NLT 7000)"
  column. The six compiled values are: Specificity 11400, Linearity 11477, LOD and LOQ 9816,
  **In-house Equivalency Study 12601**, Precision 11160, Intermediate Precision 9792.
  The summary rows state: Minimum **9792**, Maximum **11477**, Mean **11041**.
- Computed from those same six values: minimum = 9792 (correct), maximum = **12601**,
  mean = 66246/6 = **11041.0** (correct).
- The reported Mean of 11041 can only be obtained by including 12601 in the average, which proves
  12601 belongs to the data set and is therefore the maximum.
- 12601 is independently confirmed as a real study value: Table 18, p. 24 (printed p. 23),
  "Theoretical plates — In-house method = 12601 (NLT 7000)", and Table 1, p. 9 (printed p. 8),
  Equivalency row, "12601 (NLT 7000)".
- The wrong value is then restated in **Table 1, p. 9** (printed p. 8), System Suitability block:
  "Theoretical plates — Min. 9792, Max. **11477**, Mean 11041".

**Why it is a deficiency**
A row labelled "Maximum" must equal the largest of the values tabulated immediately above it.
11477 < 12601, so the stated maximum is arithmetically wrong, and the error is carried into the
overall summary table (Table 1) that a reviewer reads first. The remaining three columns of the
same summary block (%RSD 0.6/3.6/2.4, tailing 1.2/1.3/1.2, resolution 2.8/3.1/3.0) were all
verified correct, which isolates this as a genuine transcription/computation error rather than a
different data set. (11477 → 12601 also cannot be a rounding or precision artefact.)

**Confidence:** CERTAIN

---

### Finding 2 — The same notebook citation for Table 17 is given two different page numbers

**Evidence**
- Body, Table 17 "Stability Results for Sample Solution", p. 23 (printed p. 22), footer:
  "Reference: Notebook # 8135, Page # 51 and Notebook # 8133, Page # 42, 44, 45, **56**".
- Table 1, p. 8 (printed p. 7), Stability of Analytical Solutions / "Stability Results for Sample
  Solution", Ref. Book/Pg. cell: "8135/51 and 8133/42, 44, 45, **46**".
- The parallel citation for Table 16 (standard-solution stability) is identical in both places
  ("8135/50, 51 and 8133/41, 44, 55"), so the discrepancy is specific to Table 17 and is not a
  parsing artefact.

**Why it is a deficiency**
Both statements cite the raw-data location for the *same* table of the *same* results; they cannot
both be right. One of the two source-data references is incorrect, so the reported sample-solution
stability data cannot be traced unambiguously to the laboratory notebook — a data-traceability
defect (and a reviewer cannot verify the data set from the citation given).

**Confidence:** CERTAIN

---

### Finding 3 — LOD and LOQ were not determined by the method the report states; they are fixed 10 % and 20 % dilution levels

**Evidence**
- Body text, p. 15 (printed p. 14), §1.4.3: "A number of samples with decreasing amounts of the
  analyte are injected and detection limit … were determined **based on the standard deviation of
  the response**." The same sentence appears for LOQ on p. 17 (printed p. 16), §1.4.4.
- Table 9 (LOQ, p. 17) values 0.195 / 0.200 / 0.510 / 0.399 µg/mL are **identical, to three
  decimals, to the linearity level-1 (20 %) concentrations** in Tables 3–6, pp. 11–14
  (0.195 / 0.200 / 0.510 / 0.399 µg/mL).
- Table 7 (LOD, p. 16) values 0.097 / 0.100 / 0.255 / 0.199 µg/mL are **exactly one half** of the
  corresponding LOQ values for all four analytes (ratios computed: 0.4974, 0.5000, 0.5000, 0.4987).
- Appendix 9 (p. 43, chromatogram cited by Table 7) has Sample Name "**10 % LOD-LOQ Level**";
  Appendix 10 (p. 45, chromatogram cited by Table 9) has Sample Name "**20 % LOD-LOQ Level**".

**Why it is a deficiency**
A σ/slope determination (ICH Q2, LOD = 3.3 σ/S, LOQ = 10 σ/S) or a signal-to-noise determination
(3:1 and 10:1) both give an LOD:LOQ ratio of ≈0.33; a uniform ratio of exactly 0.50 across four
chemically different analytes cannot arise from either. Together with the appendix sample names,
this shows LOD and LOQ were simply the pre-selected 10 % and 20 % specification-level dilutions,
which contradicts the determination method stated in the body text and means the reported limits
are not experimentally derived detection/quantitation limits at all. (Note the report's own
acceptance criterion is "LOD to be determined experimentally".)

**Confidence:** LIKELY

---

### Finding 4 — Estradiol USP RS potency is used as 99.9 % although its CoA requires a water-content correction that is never performed or reported

**Evidence**
- §1.2 "Standards and Samples Used in Verification Study", Table on p. 10 (printed p. 9):
  "Estradiol, USP Reference Standard — N0J191 (**Purity: 99.9 %**) — Appendix 1".
- Appendix 1 CoA, p. 28 (printed p. 27), label text: "Do not dry. This is the hemihydrate form of
  estradiol. For quantitative applications, **determine the water content titrimetrically at the
  time of use** and use a value of 0.999 mg of estradiol per mg of material **on the anhydrous
  basis**."
- No water-content determination for lot N0J191 appears anywhere in the report (§1.2, §1.4.x,
  Tables 1–20, or Appendices 1–14); no as-is potency or correction factor is stated.
- Magnitude is not hypothetical: the same hemihydrate form is shown to carry ~3 % water — vendor
  CoA, Appendix 5, p. 36 (printed p. 35): "Water (KF) 2.9 to 3.5 % — result **3.2 %**". An as-is
  potency would therefore be ≈96.7 %, not 99.9 %.
- Contrast within the same report: the Estrone USP RS CoA (Appendix 4, p. 32) directs use of
  0.999 mg/mg **as-is** with no water determination, yet §1.2 records both standards identically
  as "Purity: 99.9 %".

**Why it is a deficiency**
The reference-standard value used for quantitation is inconsistent with the basis mandated by its
own CoA. Taking the anhydrous-basis figure (99.9 %) as the as-is potency of a hemihydrate standard
overstates the standard's content by ~3 %, which biases every impurity result, the absorptivity
factors and all % recovery figures in Tables 11, 13, 15 and 19. The report gives a reviewer no way
to confirm the correction was applied, because the required titrimetric water content of lot
N0J191 is not documented.

**Confidence:** LIKELY

---

### Finding 5 — Specificity: three of the five solutions the report says were analysed have no result anywhere in the report, including the control (unspiked) sample

**Evidence**
- §1.4.1 Specificity, p. 10 (printed p. 9): "Specificity of the method was established by
  analyzing diluent, **individual impurity, impurity mixture, control sample** and sample solution
  spiked with impurities. The specificity results are tabulated in Table 2."
- Table 2 "Specificity Study Results", p. 10, contains only: a Diluent row (cross-referenced to
  Appendix 6) and RT/RRT for Estradiol, Δ9,11-Estradiol, 17α-Estradiol and Estrone
  (cross-referenced to Appendix 7, the *spiked* sample). There is no row, value or cross-reference
  for an individual-impurity injection, an impurity-mixture injection, or the control sample.
- The strings "control sample", "individual impurity" and "impurity mixture" occur exactly once in
  the whole document — in the sentence quoted above. No appendix chromatogram exists for any of
  them (Appendices 6–14 are: diluent, spiked sample, linearity, LOD, LOQ, system suitability
  working, system precision, sensitivity, method precision).
- The absence is load-bearing elsewhere: the % recovery values in Table 13 (p. 20) and Table 15
  (p. 22) are recoveries of impurities spiked into a drug substance that itself contains
  17α-Estradiol at 0.17 % (Appendix 5 CoA, p. 35) — they cannot be computed or checked without
  the control-sample result, which is never given.

**Why it is a deficiency**
The report asserts data that it does not present. A reviewer cannot verify the specificity
conclusion ("All impurities are well resolved … indicating the method is specific") for the
individual and mixed-impurity injections, and cannot reproduce any % recovery figure, because the
unspiked control result — the blank the recoveries are corrected against — is silently absent from
both the tables and the appendices.

**Confidence:** LIKELY

---

### Finding 6 — Sensitivity solution is stated as part of the system-precision assessment but no result or acceptance criterion is reported, and its response falls below the reported LOD

**Evidence**
- §1.4.6.1 System Precision, p. 19 (printed p. 18): "System precision was assessed from six (6)
  replicates of a standard solution from the same vial, one injection of System suitability working
  solution and **one injection of Sensitivity solution**." The chromatograms are said to be
  Appendices 11, 12 and 13 "respectively".
- Table 12 (p. 19) reports only the six standard replicates plus tailing factor, resolution and
  theoretical plates (all three traceable to Appendix 11, the system-suitability solution). It
  contains **no** row, value or criterion for the sensitivity solution. No acceptance criterion for
  a sensitivity solution appears anywhere in the report (§1.4.6.1 criteria, Table 1 p. 7, §1.4.9 /
  Table 20 p. 26 all list only %RSD, tailing, resolution and plates).
- Appendix 13, p. 52 (printed p. 51), "Sensitivity working standard sol", HPLC_04: Estradiol
  RT 12.0, **Area 485**. For comparison, the working standard on the same instrument and sample
  set (Appendix 12, p. 50) gives Estradiol area 6420, and the LOD-level mean Estradiol area is 629
  (Table 8, p. 16) with the LOQ-level mean 1262 (Table 10, p. 17); the 100 % standard responses on
  the two instruments agree within ~3.5 % (6420 vs 6645), so the areas are comparable. Scaling
  485/6420 against the 0.978 µg/mL standard gives ≈0.074 µg/mL, i.e. **below the reported
  Estradiol LOD of 0.097 µg/mL** (Table 7, p. 16).

**Why it is a deficiency**
A solution the report states was injected as part of a verification parameter is left unevaluated:
no result, no criterion, no conclusion. Worse, the only datum available for it (area 485) is lower
than the mean response at the LOD level (629), so the solution used to demonstrate system
sensitivity sits below the detection limit the same report claims — an internally inconsistent
pair of statements that the missing result and criterion prevent from being resolved.

**Confidence:** LIKELY

---

### Finding 7 — Table 19: the USP-method total impurities (0.14 %) is smaller than the USP-method single largest unspecified impurity (0.15 %)

**Evidence**
- Table 19 "Equivalency study Results of In-house method and USP method", p. 24 (printed p. 23),
  **USP method** column: "Any Unspecified Impurity (Single Largest) = **0.15\***" and
  "Total Impurities = **0.14**". Footnote: "* Largest value of three samples reported."
- The same two numbers are restated without the footnote in Table 1, p. 9 (printed p. 8):
  "Any Unspecified Impurity (Single Largest) — USP method 0.15" and "Total impurities — USP method
  0.14".
- For contrast, the in-house column is internally consistent: Δ9,11 0.00 + 17α 0.13 + Estrone ND +
  unspecified ND = total 0.13, which is exactly the reported in-house total.

**Why it is a deficiency**
A single largest impurity can never exceed the total impurities of the same preparation, so the two
USP-method figures cannot describe the same sample. The footnote states that 0.15 % is the worst of
three samples, but no total is then given for that sample — the total 0.14 % carries no such
qualifier — so the table reports a worst-case individual value against a non-worst-case total. As
presented, the USP column is either arithmetically impossible or mixes two different bases without
saying which, and it is the column against which the "% impurities should be comparable" acceptance
criterion is judged. (The report's Version 02 history, p. 55, records "Added footnote to Table 19",
i.e. the footnote was a later patch that still leaves the 0.15/0.14 pair unreconciled.)

**Confidence:** LIKELY

---

TOTAL: 7 (CERTAIN: 2, LIKELY: 5)
