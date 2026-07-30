# Gold-standard deficiency list — MVR-1381-RC, sections 1.4.3–1.4.6 (Tables 7–15)

Document: Estradiol USP (Hemihydrate, Micronized), 3.2.S.4.3 Verification of Analytical
Procedure for Related Compounds, Method Verification Report MVR-1381-RC, Version 02,
May 02, 2016.

Page convention: page numbers below are PDF/parsed page numbers (the printed footers run
one lower, e.g. PDF p16 carries the footer "Page 15 of 54"). Tables are cited by table number,
which is unambiguous.

All numeric claims below were recomputed from the raw data in the report. Section
"Verified and NOT raised" at the end records what was checked and found correct, so the
absence of an entry there is not an oversight.

---

## 1. LOD and LOQ were not derived by the method the report states; they are pre-set fractions of the specification level, with LOQ mechanically fixed at 2 x LOD

**Evidence**

- §1.4.3 (p15) states: "detection limit of Estradiol and its impurities were determined based
  on the standard deviation of the response." §1.4.4 (p17) makes the same claim for LOQ:
  "quantitation limit of Estradiol and its impurities were determined based on the standard
  deviation of the response."
- Table 7 (LOD, p16): Estradiol 0.097, Δ9,11-Estradiol 0.100, 17α-Estradiol 0.255,
  Estrone 0.199 µg/mL.
  Table 9 (LOQ, p17): 0.195, 0.200, 0.510, 0.399 µg/mL.
  Computed LOQ/LOD ratios: **2.010, 2.000, 2.000, 2.005** — LOQ is exactly 2 x LOD for all
  four analytes.
- The four LOQ values are numerically identical to linearity level 1 in Tables 3–6 (p11–14),
  which is labelled "20 (LOQ)" — i.e. 20% of the specification level. Against the 100%-level
  concentrations in those same tables (0.978, 1.002, 2.554, 1.999 µg/mL), the reported values
  compute to exactly **LOD = 9.9 / 10.0 / 10.0 / 10.0 % of spec** and
  **LOQ = 19.9 / 20.0 / 20.0 / 20.0 % of spec**.
- Direct confirmation from the report's own chromatogram headers: Appendix 9 (LOD,
  parsed p43) Sample Name = "**10%LOD-LOQLevel**"; Appendix 10 (LOQ, parsed p45)
  Sample Name = "**20%LOD-LOQLevel**". The solutions were prepared as fixed 10% and 20%
  fractions of the specification level.
- If the stated σ-of-the-response approach (ICH Q2(R1): LOD = 3.3σ/S, LOQ = 10σ/S) had
  actually been applied, the LOQ/LOD ratio is fixed at **10/3.3 = 3.03**, not 2.00 —
  independently of which σ estimate is chosen. Recomputing from the report's own linearity
  regressions (Tables 3–6, residual SD with n−2 df) gives: Estradiol σ=154.6, S=6920.93 →
  LOD 0.074 / LOQ 0.223; Δ9,11 σ=173.0, S=16483.00 → 0.035 / 0.105; 17α σ=200.9,
  S=6731.36 → 0.099 / 0.299; Estrone σ=328.1, S=6993.99 → 0.155 / 0.469 µg/mL. None of
  these matches Table 7 or Table 9. Note in particular that for Estradiol (0.195 reported vs
  0.223 derived) and Estrone (0.399 reported vs 0.469 derived) the reported LOQ is **below**
  what the stated derivation would yield.

**why_it_is_a_deficiency**

Internal contradiction between the stated determination basis and the reported values. ICH
Q2(R1) §6 and §7 require the approach used to establish LOD/LOQ to be stated and to be the
approach actually applied. A design in which LOD and LOQ are pre-set at 10% and 20% of the
specification level — so that LOQ is arithmetically 2 x LOD for every analyte — is not
"based on the standard deviation of the response" and is not produced by any ICH-recognised
approach (σ/S gives a 3.03 ratio; a 3:1 / 10:1 signal-to-noise design gives ~3.3). The
sensitivity of the method has therefore not been established by the method the report claims,
and §1.3 (p10) simultaneously asserts "No deviation was observed from the protocol."

**confidence:** CERTAIN

---

## 2. No supporting data for the LOD/LOQ determination is presented, and the described experiment (a decreasing-concentration series) is not documented

**Evidence**

- §1.4.3 (p15) and §1.4.4 (p17) both state: "A number of samples with decreasing amounts of
  the analyte are injected."
- Tables 7 and 9 report only the four final LOD/LOQ values plus a chromatogram
  cross-reference. No dilution-series concentrations, no corresponding responses, no σ value,
  no slope, and no regression are given in either section.
- The only LOD/LOQ solutions documented anywhere in the report are two: Appendix 9
  ("10%LOD-LOQLevel", sample set 8135_27_RC_SS, vial 6) and Appendix 10
  ("20%LOD-LOQLevel", same sample set, vial 7).
- No signal-to-noise value appears anywhere in the report — the strings "signal", "noise" and
  "S/N" occur nowhere in the document text or in the Appendix 9 / Appendix 10 chromatogram
  annotations as parsed.

**why_it_is_a_deficiency**

The raw data underpinning a claimed verification characteristic is absent, so the LOD and LOQ
values in Tables 7 and 9 cannot be verified or reproduced by a reviewer from the submission.
ICH Q2(R1) requires that the data used to establish the limit be presented (σ and S for the
σ/S approach, or representative chromatograms with S/N for the signal-to-noise approach).
Neither is supplied, and the two documented solutions do not constitute "a number of samples
with decreasing amounts."

**confidence:** CERTAIN

---

## 3. Unexplained gross outlier retained in the LOD precision data set (Estradiol injection #6), which alone produces the reported %RSD

**Evidence**

- Table 8, Precision at LOD Level (p16), Estradiol row: 677, 670, 660, 707, 673, **389**;
  reported Mean 629, %RSD 18.9. Recomputed: mean 629.33, SD 118.80, %RSD **18.88** —
  the reported statistics are correct as calculated.
- Injection #6 = 389 is **42.6% below** the mean of the other five injections (677.40).
  Excluding it, mean = 677.40, SD = 17.70, %RSD = **2.61%**. The entire reported 18.9% RSD
  is created by this single value.
- Grubbs test on the six values: G = (629.33 − 389)/118.80 = **2.023**, which exceeds the
  two-sided critical values for n = 6 of 1.887 (α = 0.05) and 1.973 (α = 0.01) — a statistical
  outlier at 99% confidence.
- No comparable single-injection collapse occurs for the other three analytes in Table 8
  (Δ9,11 1275–1631; 17α 1346–1901; Estrone 914–1509 all vary smoothly), so the anomaly is
  specific to one peak in one injection, not a run-wide event.
- The report offers no comment, footnote, or investigation. §1.4.3 Conclusion (p16) states:
  "The LOD values met the acceptance criteria indicating the method is precisely sensitive for
  its intended purpose. All components can be precisely detected at the above concentration."

**why_it_is_a_deficiency**

A 43% loss of response for one analyte in one replicate injection from a single solution on a
single system indicates an assignable analytical anomaly (partial injection, integration
failure at the limit, or a genuine inability to detect reliably at the chosen LOD). USP <1010>
and data-integrity expectations require anomalous results to be investigated and either
explained with an assignable cause or handled under a documented outlier procedure; §1.3
(p10) instead records "No deviation was observed from the protocol." Meeting the very wide
33.0% criterion does not discharge the obligation to explain the anomaly, and the conclusion
that "All components can be precisely detected" is directly contradicted by an injection in
which Estradiol response fell to 57% of its normal value.

**confidence:** CERTAIN

---

## 4. Absorptivity factors were calculated from only 3 of the 7 linearity levels, and the omission of the other 4 is undisclosed and unjustified

**Evidence**

- §1.4.5 (p18) defines the basis: "Response: Mean Peak Area/ Concentration (µg/mL)",
  Response Factor = Response(Impurity)/Response(Estradiol), Absorptivity Factor = 1/Response
  Factor. The protocol acceptance criterion in Table 1 (Overall Summary, p7) is
  "**Determine the AF from the linearity data**", notebook reference 8135/25.
- Table 11 (p18) reports Response values to three decimals: Estradiol 6559.876,
  Δ9,11-Estradiol 16262.039, 17α-Estradiol 6371.492, Estrone 6871.372.
- Recomputing Peak Area / Concentration level-by-level from the linearity data in Tables 3–6,
  the reported Responses are reproduced **exactly, to six significant figures, as the mean of
  levels 3, 5 and 7 only** (60%, 100% and 150%):

  | Compound | L3 (60%) | L5 (100%) | L7 (150%) | mean | Table 11 |
  |---|---|---|---|---|---|
  | Estradiol | 6259.386 | 6794.479 | 6625.767 | **6559.877** | 6559.876 |
  | Δ9,11-Estradiol | 16076.539 | 16282.435 | 16427.146 | **16262.040** | 16262.039 |
  | 17α-Estradiol | 6069.191 | 6445.184 | 6600.104 | **6371.493** | 6371.492 |
  | Estrone | 6826.522 | 6992.997 | 6794.598 | **6871.372** | 6871.372 |

  The same three-level subset reproduces all four compounds independently, so the
  identification is not coincidental. Levels 1 (20% / LOQ), 2 (40%), 4 (80%) and 6 (120%) were
  discarded without mention.
- The exclusion is not neutral. The mean Peak Area/Concentration of the four discarded levels
  versus the three retained: Estradiol 5926.76 vs 6559.88 (**+10.7%** bias on the reference
  analyte), Estrone 6261.23 vs 6871.37 (+9.7%), 17α 6178.04 vs 6371.49 (+3.1%),
  Δ9,11 15816.03 vs 16262.04 (+2.8%).
- Because the bias is not uniform across analytes, the adopted AF depends materially on the
  subset: levels 3/5/7 (as used) → 0.403 / 1.030 / 0.955 (reported 0.40 / 1.03 / 0.96);
  all seven levels → 0.387 / 0.990 / 0.950; the low half (levels 1–4) → 0.371 / 0.966 / 0.932;
  the linearity regression slopes → 0.420 / 1.028 / 0.990 (for Δ9,11 / 17α / Estrone
  respectively). For 17α-Estradiol the AF moves from 1.03 to 0.99 (a 3.9% shift in every
  reported result) simply by using all of the linearity data instead of three of seven levels.

**why_it_is_a_deficiency**

Undisclosed selection of a subset of the available data to generate a reported value. The
protocol criterion is to determine the AF "from the linearity data"; §1.4.5 does not state which
levels were used, how many replicates contributed, or why four of the seven levels — including
the LOQ level, at which impurities are least well characterised — were excluded. Since the AF
is a multiplier applied to every reported impurity result against limits of NMT 0.1% (Δ9,11),
NMT 0.25% (17α) and NMT 0.2% (Estrone), a 3–8% shift in the AF from an unstated data
selection is directly consequential. This is both an incomplete-reporting deficiency and a data
selection / data-integrity concern (ICH Q2(R1) reporting expectations; §1.3 "No deviation" is
also inconsistent with a departure from "determine the AF from the linearity data").

**confidence:** CERTAIN

---

## 5. The absorptivity factor is strongly concentration-dependent across the method's range, yet a single value is adopted with no acceptance criterion and no verification

**Evidence**

- §1.4.5 (p18) itself acknowledges concentration dependence: the AF "represents the Response
  factor of the impurity with respect to the Estradiol (Active component) **at the different
  concentration level**", but the section neither reports the level-to-level variation nor
  justifies collapsing it to one number.
- Computing the AF level-by-level on the report's own stated basis — (Peak Area/Concentration)
  for Estradiol divided by (Peak Area/Concentration) for the impurity at the matching linearity
  level (Tables 3–6):

  | Impurity | L1 (20%) | L2 | L3 | L4 | L5 | L6 | L7 (150%) | spread | Table 11 |
  |---|---|---|---|---|---|---|---|---|---|
  | Δ9,11-Estradiol | 0.328 | 0.354 | 0.389 | 0.412 | 0.417 | 0.403 | 0.403 | 27.0% | 0.40 |
  | 17α-Estradiol | 0.886 | 0.912 | 1.031 | 1.029 | 1.054 | 1.001 | 1.004 | 18.9% | 1.03 |
  | Estrone | 0.898 | 0.936 | 0.917 | 0.973 | 0.972 | 0.971 | 0.975 | 8.6% | 0.96 |

  The AF rises monotonically with concentration for Δ9,11 and 17α, and the adopted values sit
  at the upper end of the observed range; at the LOQ level the true factors are 0.328 and 0.886
  — 18% and 14% away from the adopted 0.40 and 1.03.
- The protocol's entry for this parameter in Table 1 (p7) is "Determine the AF from the
  linearity data" — an instruction, not an acceptance criterion. No numeric criterion, no
  replicate agreement requirement, and no comparison against the USP monograph's relative
  response values are presented anywhere in the report. Absorptivity Factor is also absent from
  the system-suitability compilation in Table 20 (p26) and from the conclusions in §1.5 (p27).

**why_it_is_a_deficiency**

A single fixed absorptivity factor is applied across the whole reporting range, but the report's
own data show the factor varies by up to 27% over that range and is systematically different at
the low end where impurities are actually quantified — so reported impurity levels near the
LOQ / reporting threshold will be biased. Establishing a correction factor without any
acceptance criterion, without a statement of its valid concentration range, and without
demonstrating it is stable or verified against an independent reference means the factor is
unqualified. A reviewer would request the level-wise data, justification of the single value,
and demonstration that the factor is valid at the reporting threshold.

**confidence:** LIKELY

---

## 6. §1.4.6.1 states a Sensitivity solution was injected, but no result and no acceptance criterion for it appears anywhere in the report

**Evidence**

- §1.4.6.1 (p19): "System precision was assessed from six (6) replicates of a standard solution
  from the same vial, one injection of System suitability working solution and **one injection of
  Sensitivity solution**." Appendix 13 (parsed p51) is the "Typical chromatogram of Sensitivity
  Solution" (Sample Name "Sensitivity working standard sol", sample set 8133_36_RC_SS,
  HPLC_04, acquired 12/9/2014).
- Table 12, System Precision Results (p19), reports only: six standard peak areas, Mean 6473,
  %RSD (NMT 6.0) 0.6, Tailing factor (0.9–1.5) 1.2, Resolution (NLT 2.5) 3.0, Theoretical
  plates (NLT 7000) 11160. There is no row derived from the sensitivity solution.
- The §1.4.6.1 Acceptance Criteria paragraph (p19) lists only %RSD, tailing factor, resolution
  and theoretical plates. The same four criteria — and no sensitivity criterion — recur in the
  §1.4.6.3 criteria (p22), in the method's system-suitability requirements table (p25), and in
  §1.4.9 / Table 20 (p26).
- No signal-to-noise value or sensitivity result appears anywhere in the report.

**why_it_is_a_deficiency**

An experiment that the report states was performed has no reported result and no acceptance
criterion, so it cannot contribute to the conclusion drawn. The purpose of a sensitivity
solution in a related-compounds method is to demonstrate on each analytical run that the
system can detect and respond at the LOQ / reporting-threshold level; omitting both the result
and the criterion leaves the run-to-run demonstration of sensitivity undocumented and leaves
the §1.4.6.1 conclusion ("the analytical procedure is precise with respect to the
chromatographic system") unsupported for the sensitivity element of the described test. This
compounds deficiencies 1 and 2, since sensitivity is the one aspect of the LOD/LOQ claim that a
routine system-suitability check could have corroborated.

**confidence:** LIKELY

---

## 7. LOQ precision is marginal for three of four analytes, with no demonstration that the chosen LOQ is robust

**Evidence**

- Table 10, Precision at LOQ Level (p17), against the criterion "The RSD of peak area of each
  component from six replicate injections at LOQ level should be NMT 10.0%":
  Estradiol reported 9.8 (recomputed **9.83%**), 17α-Estradiol reported 9.1 (recomputed
  **9.09%**), Estrone reported 8.8 (recomputed **8.77%**), Δ9,11-Estradiol reported 3.5
  (recomputed 3.46%). All four pass; three of four sit within 1.3 percentage points of the
  limit, and Estradiol has only **0.17 percentage points** of margin.
- The LOQ level was not derived but pre-set at 20% of the specification level (see deficiency 1;
  Appendix 10 Sample Name "20%LOD-LOQLevel"), so the marginal precision is a property of an
  arbitrarily chosen level rather than of a level demonstrated to be the lowest reliably
  quantifiable one.
- Only a single solution and a single six-injection set were run per level; no repeat set, no
  second day, and no second system are presented for the LOQ level.

**why_it_is_a_deficiency**

ICH Q2(R1) defines the quantitation limit as the lowest amount that can be quantitated with
suitable precision. A single six-injection %RSD of 9.83% against a 10.0% limit provides no
assurance of reproducibility — ordinary run-to-run variability would fail the criterion — and
because the level was fixed a priori rather than established from the data, the report contains
no evidence that a defensible LOQ has been identified. A reviewer would request either
justification of the LOQ with supporting replicate/multi-run data or a higher LOQ with adequate
margin, together with confirmation that the resulting LOQ remains at or below the reporting
threshold.

**confidence:** LIKELY

---

## 8. LOQ accuracy is not demonstrated, contrary to the report's own definition of LOQ; and the six "replicate injections" measure injector repeatability only

**Evidence**

- §1.4.4 (p17) defines the parameter: "The limit of quantitation is the minimum level of
  analyte, which is quantitated with **acceptable accuracy and precision** with RSD for six
  replicate injections of not more than 10.0%."
- What is actually presented for LOQ is Table 10 alone — six **injections** of one solution
  ("The precision of LOQ was established by injecting six injections of LOQ concentration",
  §1.4.4, p17). No recovery, no measured-versus-theoretical comparison, and no independent
  preparations at the LOQ level appear in §1.4.4 or elsewhere.
- The only recovery data in the report is at the specification level: Table 13 (Method Precision,
  p20) and Table 15 (Ruggedness, p22), both from samples "spiked with the impurities at the
  specification level". The report's table of contents and body contain sections 1.4.1–1.4.9
  with no accuracy section at all.
- §1.4.4 Conclusion (p18) nevertheless states: "All components can be precisely quantified at
  the above concentration level."

**why_it_is_a_deficiency**

Internal contradiction: the report states the acceptance basis for LOQ includes acceptable
accuracy, then demonstrates only precision. Six injections of a single solution characterise
injector and detector repeatability, not the ability to quantitate — which requires
independently prepared samples and a comparison of measured to theoretical amount. Without
accuracy at the LOQ, and with recovery demonstrated only at the specification level (0.1–0.25%),
the accuracy of results reported between the LOQ (0.02–0.05%) and the specification level —
which includes the "Any Unspecified Impurity" limit of NMT 0.10% — is not established.

**confidence:** LIKELY

---

## 9. Precision was not demonstrated for two specification attributes: "Any Unspecified Impurity" and "Total Impurities"

**Evidence**

- The specification the method must support (report p6 and the comparison table on p25) lists
  five impurity attributes: Δ9,11-Estradiol NMT 0.1%, 17α-Estradiol NMT 0.25%, Estrone NMT
  0.2%, **Any Unspecified Impurity NMT 0.10%**, **Total Impurities NMT 0.5%**.
- Table 13, Method Precision Results (p20), reports % Recovery, Mean, % Range and % RSD for
  only three columns: Δ9,11-Estradiol, 17α-Estradiol, Estrone.
- Table 15, Ruggedness study Results (p22), likewise covers only those same three impurities
  for each of the two analysts.
- These attributes are demonstrably part of the method's reported output: Table 19, the
  Equivalency study (p24), reports results for "Any Unspecified Impurity (Single Largest)" and
  "Total Impurities". §1.4.3/§1.4.4 also establish an LOD and LOQ for Estradiol itself
  (0.097 / 0.195 µg/mL, Tables 7 and 9) — Estradiol being the standard against which
  unspecified impurities are quantified — so the unspecified-impurity determination was
  recognised as part of the method, yet its precision was never assessed.

**why_it_is_a_deficiency**

Method precision and intermediate precision must be established for each attribute the
procedure is used to control. Unspecified impurities are quantified against the Estradiol
standard (absorptivity factor of 1.0 by default) rather than against an authentic impurity
standard, so the repeatability of that determination is not covered by the three spiked known
impurities. Total impurities is a summed attribute whose variability is likewise not
demonstrated. As a result the §1.4.6.2 and §1.4.6.3 conclusions ("the analytical procedure is
precise for its intended use"; "The method is precise and rugged") extend beyond the data
presented.

**confidence:** LIKELY

---

# Verified and NOT raised (checked, found correct or excluded by design)

Recorded so the caller can distinguish "checked and clean" from "not examined".

**Arithmetic that reconciles exactly (no finding):**
- Table 8 (LOD precision) — all means and %RSDs recompute correctly: Estradiol 629.33/18.88
  (reported 629/18.9); Δ9,11 1466.67/10.04 (1467/10.0); 17α 1627.83/11.71 (1628/11.7);
  Estrone 1159.00/17.93 (1159/17.9).
- Table 10 (LOQ precision) — Estradiol 1261.67/9.83 (1262/9.8); Δ9,11 3169.50/3.46
  (3170/3.5); 17α 3297.50/9.09 (3298/9.1); Estrone 2682.17/8.77 (2682/8.8).
- Table 12 — mean 6473.17 (6473), %RSD 0.610 (0.6).
- Table 14 Analyst B — mean 6419.67 (6420), %RSD 3.355 (3.4). Analyst A column is identical
  to Table 12 and this reuse is disclosed in §1.4.6.3 ("The same lot/batch (used in precision
  study) of standard and sample were used").
- Table 13 — means 98.98/97.40/97.60 (99.0/97.4/97.6), %RSDs 0.704/1.287/2.743
  (0.7/1.3/2.7), ranges as printed.
- Table 15 — all six means and %RSDs correct (Δ9,11 A 98.98/0.704, B 96.53/1.639;
  17α A 97.40/1.287, B 99.12/5.085; Estrone A 97.60/2.743, B 98.38/2.222); all six ranges
  correct; analyst mean differences recompute to 2.45, 1.72, 0.78 → reported 2.5, 1.7, 0.8.
- Table 11 — Response Factors and Absorptivity Factors are internally consistent with the
  stated Response values (Δ9,11 RF 2.4790→2.479, AF 0.4034→0.40; 17α RF 0.9713→0.971,
  AF 1.0296→1.03; Estrone RF 1.0475→1.047, AF 0.9547→0.96). The arithmetic in Table 11 is
  correct; the deficiency (item 4) is the undisclosed input data, not the calculation.
- Tables 7 and 9 — the "%" columns are correct against the stated 1000 µg/mL Estradiol sample
  concentration at the two-decimal precision displayed (0.0097→0.01, 0.0255→0.03,
  0.0199→0.02, 0.0195→0.02, 0.051→0.05, 0.0399→0.04).

**No stated acceptance criterion is breached anywhere in scope (all verified):** LOD %RSD
maximum 18.9 vs NMT 33.0; LOQ %RSD maximum 9.8 vs NMT 10.0; system precision %RSD 0.6
and 3.4 vs NMT 6.0; method/ruggedness %RSD maximum 5.1 vs NMT 10.0; all 36 individual
recoveries within 93.9–105.6 vs 80.0–120.0; all means within range; analyst differences
2.5/1.7/0.8 vs NMT 10.0; tailing 1.2 vs 0.9–1.5; resolution 3.0 and 2.8 vs NLT 2.5;
theoretical plates 11160 and 9792 vs NLT 7000.

**Deliberately excluded:**
- Estradiol's "N/A" Response Factor and Absorptivity Factor in Table 11 — correct by
  definition, Estradiol is the reference analyte.
- Analyst A vs Analyst B differences in Table 14/15 (e.g. 17α %RSD 1.3 vs 5.1, range spread
  3.0 vs 11.7) — different measurements, and the governing difference criterion is met.
- Differences between system, method and intermediate precision results — different
  measurements by design.
- Rounding at the displayed precision throughout.
- Wording issues, e.g. "The mean recovery ... within 80.0% and 120.0% **in each sample**"
  (§1.4.6.2, p20) being applied in Table 13 to the individual-sample range rather than the mean;
  and "not less than 2.5" (p20/p22/p26) vs "greater than 2.5" (p25) for resolution.
- The +26.5% (Estradiol), +17.9% (Estrone), +12.0% (17α) and +1.7% (Δ9,11) differences between
  the Table 10 LOQ mean peak areas and the linearity level-1 peak areas at the same nominal
  concentrations (Tables 3–6), despite both runs being on HPLC_07 by the same analyst one day
  apart (Appendix 8 vs Appendix 10). Examined and set aside: these are separate solution
  preparations, and the underlying cause is non-proportional response at the lowest linearity
  level (all four regressions carry negative intercepts: −377.49, −285.55, −704.96, −480.37),
  which belongs to §1.4.2 Linearity and is outside this scope. Its in-scope consequence is
  already captured in deficiencies 4 and 5.
- Absence of an accuracy section anywhere in the report, and the omission of LOD, LOQ,
  absorptivity factor and solution stability from the §1.5 Conclusions (p27) — outside
  sections 1.4.3–1.4.6. The LOQ-specific accuracy gap is raised as deficiency 8.

TOTAL: 9 (CERTAIN: 4, LIKELY: 5)
