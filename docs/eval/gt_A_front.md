# Gold-standard deficiency list — MVR-1381-RC (Estradiol USP, Related Compounds method verification)
## Scope A: front matter, report identification, 1.1–1.4.2 (Specificity, Linearity), Tables 1–6, specificity/linearity appendices (approx. pp. 5–14 + Appendices 1–8)

Page numbers below are **PDF page numbers** (the printed footer is one lower, e.g. PDF p.11 = footer "Page 10 of 54").

---

### 1. Estradiol USP Reference Standard potency of 99.9% used without the water-content determination and anhydrous-basis correction the standard's own certificate requires
**Evidence**
- §1.2, PDF p.10: "Estradiol, USP Reference Standard | N0J191 (Purity: 99.9%) | Appendix 1".
- Appendix 1 (USP certificate for LOT N0J191), PDF p.28: "Do not dry. This is the hemihydrate form of estradiol. For quantitative applications, determine the water content titrimetrically at the time of use and use a value of 0.999 mg of estradiol per mg of material **on the anhydrous basis**." PDF p.29: "Unless otherwise stated on the Reference Standard label, a value of 100.0% should be used…".
- No water content, Karl Fischer, or loss-on-drying determination for the Estradiol RS appears anywhere in the report (searched full text; the only water values in the document are in Appendix 3 for the 17α standard and Appendix 5 for the drug substance).
- Water content of the hemihydrate: Appendix 5, PDF p.36 — "Water (KF) 2.9 to 3.5% → 3.2%"; theoretical = (0.5 × 18.02)/281.39 = 3.20% (MW hemihydrate 281.39 per Appendix 1; anhydrous 272.38).
- Arithmetic: as-is potency = 0.999 × (1 − 0.032) = **0.967 → 96.7%**, not 99.9%. The assigned standard potency is therefore overstated by 99.9/96.7 = **3.3% relative**.
- Contrast within the same report: the Estrone USP RS certificate (Appendix 4, PDF p.32) says "use a value of 0.999 mg of estrone per mg of material **on the as-is basis**" — 99.9% is correct there. §1.2 applied 99.9% to both standards identically, i.e. the anhydrous-basis instruction on the estradiol label was not applied.

**Why it is a deficiency** — The reference standard's assigned value was used contrary to the explicit instruction on its certificate/label. Because every impurity result, the absorptivity factors (Table 11), and all linearity/LOD/LOQ concentrations (Tables 3–6, 7, 9) are calculated against this standard, an approximately 3.3% systematic error propagates through the entire verification. USP <11>/<1226> require reference standards to be used in accordance with the label instructions.

**Confidence: CERTAIN**

---

### 2. The diluent chromatogram cross-referenced as "No Interference" in Table 2 is not peak-free, and the report defines no disregard limit or integration cut-off for the "any unspecified impurity" portion of the specification
**Evidence**
- Table 2, PDF p.10, Diluent row: retention-time column = "No peak should elute at the retention time of Estradiol and its known impurity peaks", result column = "**No Interference**", cross-reference Appendix 6.
- Appendix 6 peak table, PDF p.38: seven integrated peaks — RT 0.1 / area 201; RT 2.1 / area **13439** (80.0% area); RT 2.8 / 1174; RT 3.1 / 62; RT 3.5 / 719; RT 21.9 / 885; RT 24.1 / 322. Total integrated area = 16 802. (The four named analyte rows read "Missing", which does support the retention-time-specific part of the criterion.)
- Scale of the interference: the Estradiol 100%-linearity-level peak area is 6645 (Table 3, PDF p.11, confirmed in the Appendix 8 peak table, PDF p.42) at 0.978 µg/mL = 0.098% of the 1000 µg/mL sample (sample concentration stated §1.4.3, PDF p.15). The 2.1-min diluent peak (13 439) is **2.02 ×** that response, i.e. ≈ **0.20%** if quantified as an unspecified impurity — twice the NMT 0.10% limit. Total diluent area 16 802 = 2.53 × → ≈ 0.25%.
- Specification, §1.1 PDF p.5: "Any Unspecified Impurity NMT 0.10%", "Total Impurities NMT 0.5%".
- §1.4.1 and Table 2 contain no disregard limit, no integration start time, no blank-subtraction provision, and no statement of how these diluent peaks are excluded from unspecified/total impurity results.

**Why it is a deficiency** — Specificity was demonstrated only at four discrete retention times, while the specification requires quantitation of *any* unspecified impurity anywhere in the chromatogram. A blank peak with twice the response of the 100%-level standard is a material interference for that part of the specification, yet Table 2's summary cell states "No Interference" without qualification and no disregard/cut-off convention is documented (ICH Q2(R1) §4.1.2; blank suitability for impurity procedures).

**Confidence: CERTAIN** (peak areas and the 13 439 vs 6645 ratio verified from the cross-referenced appendices)

---

### 3. Specificity: three of the five solution types the report says were analysed have no reported results and no cross-referenced chromatogram, and the resolution half of the acceptance criterion is never tabulated
**Evidence**
- §1.4.1, PDF p.10: "Specificity of the method was established by analyzing **diluent, individual impurity, impurity mixture, control sample and sample solution spiked with impurities**."
- Table 2, PDF p.10, contains only: the diluent row (Appendix 6) and RT/RRT for the four analytes (Appendix 7). No results, and no appendix cross-reference, for individual impurity solutions, the impurity mixture, or the control (unspiked drug substance) sample. The appendix list (PDF p.3) contains no such chromatograms (Appendices 6–14 are diluent, spiked sample, linearity, LOD, LOQ, system suitability working, system precision, sensitivity, method precision).
- Table 2 is populated entirely from Appendix 7: RRT check — 10.4/12.0 = 0.867 → 0.87; 13.4/12.0 = 1.117 → 1.12; 16.7/12.0 = 1.392 → 1.39, matching the stated RRTs exactly.
- Two-part acceptance criterion (Table 1 PDF p.6 and §1.4.1 PDF p.11): "The Diluent chromatogram should not show any interference … **and each peak of known impurities and Estradiol should be well resolved.**" The Results column of Table 1 addresses only the first clause; Table 2 has no resolution column. Resolution values exist only inside Appendix 7 (PDF p.40: 3.5 for Estradiol vs Δ9,11; 2.9 for 17α; 5.8 for Estrone).
- The conclusion (PDF p.11) nevertheless asserts "All impurities are well resolved from each other".

**Why it is a deficiency** — Results claimed in the narrative are not presented (no control-sample chromatogram means matrix interference at the impurity retention times in the *unspiked* drug substance was never shown), and a stated acceptance criterion has no reported result in either the summary table or the section table. A conclusion is drawn for data that are not in the report body.

**Confidence: CERTAIN** (narrative-vs-data contradiction, verified against the full appendix list)

---

### 4. Specificity established only by spiking with three known impurities — no degradation samples and no peak-homogeneity data, although the report's own definition of specificity invokes degradants
**Evidence**
- §1.4.1, PDF p.10: "Specificity is the ability of the method to assess unequivocally impurities in the presence of analyte **and degradants**."
- No stressed/degraded samples appear in §1.4.1, Table 2, or any appendix; no forced-degradation study is listed among the nine verification attributes (§1.1, PDF pp.5–6).
- Detector is a single-/dual-wavelength UV absorbance detector — "Channel Name: 2487 Channel 1" (Appendices 6, 7, 8; PDF pp.37, 39, 41) — so no diode-array peak-purity data exist to show the Estradiol peak or the impurity peaks are free of co-eluting species.

**Why it is a deficiency** — ICH Q2(R1) §4.1.2 states that for impurity procedures, specificity should be demonstrated by resolution of the two closest-eluting components and, where degradation products are not all available, by comparison of results on degraded/stressed samples with a second procedure. As written, specificity is not shown to be stability-indicating and the report's own stated definition (which includes degradants) is not satisfied by the data presented.

**Confidence: LIKELY**

---

### 5. Linearity judged on the correlation coefficient alone; large negative y-intercepts and a substantial low-end depression of response factor are neither evaluated nor subject to any criterion
**Evidence** (all regressions independently recomputed from the tabulated concentration/area pairs — slope, intercept and r are exactly reproducible, so the reported regressions themselves are arithmetically correct)
- Intercept relative to the lowest (LOQ) level response:
  - Table 3, Estradiol, PDF p.11: intercept **−377.49** vs LOQ-level response 998 → **−37.8%** of the LOQ response; −5.7% of the 100%-level response (6645).
  - Table 5, 17α-Estradiol, PDF p.13: −704.96 vs 2945 → **−23.9%**.
  - Table 6, Estrone, PDF p.14: −480.37 vs 2275 → **−21.1%**.
  - Table 4, Δ9,11-Estradiol, PDF p.12: −285.55 vs 3116 → −9.2%.
- Response factor (area/concentration) across the range:
  - Estradiol (Table 3): 5118 at 0.195 µg/mL → 6795 at 0.978 µg/mL; the LOQ-level response factor is only **75.3%** of the 100%-level response factor.
  - Estrone (Table 6): 5702 → 6993 = **81.5%**.
  - 17α-Estradiol (Table 5): 5775 → 6445 = **89.6%**.
  - Δ9,11-Estradiol (Table 4): 15 580 → 16 282 = 95.7%.
- The only criterion applied is "Co-relation Coefficient (NLT 0.990)" (Tables 3–6; Table 1 PDF p.6). No y-intercept criterion, no % relative response or % recovery per level, no residual analysis, and no residual sum of squares are reported.

**Why it is a deficiency** — ICH Q2(R1) §4.1.1 requires the correlation coefficient, y-intercept, slope **and residual sum of squares** to be submitted, and states that analysis of the deviation of actual data points from the regression line should be evaluated. A correlation coefficient of 0.998–0.999 is fully compatible with the ~25% low-end response depression shown above; because impurities are quantified against a single ~100%-level external standard, impurities at or near the LOQ will be under-reported by up to ~25%. The report does not address this and applies no criterion capable of detecting it.

**Confidence: LIKELY**

---

### 6. The statistic reported as "Co-relation Coefficient" in Tables 3 and 6 is the coefficient of determination (r²), not the correlation coefficient the acceptance criterion specifies
**Evidence**
- Table 3 (Estradiol), PDF p.11, states "Co-relation Coefficient (NLT 0.990) — 0.998". Computed from the seven tabulated points: **r = 0.99896** (rounds to 0.999); **r² = 0.99792** (rounds to 0.998).
- Table 6 (Estrone), PDF p.14, states 0.998. Computed: **r = 0.99890** (→ 0.999); **r² = 0.99780** (→ 0.998).
- Tables 4 and 5 are indeterminate (r = 0.99978 / 0.99973 and r² = 0.99956 / 0.99945 both round to the stated 0.999).
- Acceptance criterion (Table 1 PDF p.6 and Tables 3–6): "The **correlation coefficient** of Estradiol and its impurities should be NLT 0.990."

**Why it is a deficiency** — In two of the four tables the reported value cannot be the correlation coefficient computed from the data in the same table; it matches r² instead. Both statistics pass the 0.990 limit, so there is no acceptance-criterion failure, but the report applies a criterion written for one statistic to a different statistic and mislabels it — the reviewer must be able to reconcile the reported number with the tabulated data.

**Confidence: LIKELY** (arithmetic verified; the r-vs-r² attribution is the judgement)

---

### 7. Lower end of the claimed linear range is not an experimentally determined LOQ — the reported LOD/LOQ are fixed 10% and 20% dilutions of the specification level, not values derived from the standard deviation of the response
**Evidence**
- Tables 3–6 label level 1 as "20 (LOQ)" and §1.4.2 (PDF p.11) and the conclusion (PDF p.15) claim the range is "from LOQ to 150% of the specification level".
- Level-1 concentrations (Tables 3–6, PDF pp.11–14): 0.195, 0.200, 0.510, 0.399 µg/mL — **identical** to the reported LOQ values (Table 9, PDF p.17: 0.195, 0.200, 0.510, 0.399).
- Reported LOD values (Table 7, PDF p.16): 0.097, 0.100, 0.255, 0.199 µg/mL = **exactly LOQ/2** (0.0975, 0.100, 0.255, 0.1995). LOQ/LOD = 2.010, 2.000, 2.000, 2.005.
- Both sets are fixed fractions of each analyte's own limit (§1.1, PDF p.5): LOD ≈ 10% of limit (0.0097%, 0.010%, 0.0255%, 0.0199% vs limits 0.10%, 0.1%, 0.25%, 0.2%); LOQ ≈ 20% of limit.
- Stated method of determination (PDF pp.15 and 17): "…detection limit / quantitation limit of Estradiol and its impurities were determined **based on the standard deviation of the response**." No σ (standard deviation of the response), no S (slope), and no calculation are presented.

**Why it is a deficiency** — Under ICH Q2(R1) §6.3/§7.3, LOD = 3.3σ/S and LOQ = 10σ/S, so LOQ/LOD must be ≈ 3.03; a signal-to-noise determination gives ≈ 3.3. A ratio of exactly 2.00 for all four analytes, coinciding exactly with pre-set 10%/20%-of-limit dilution levels, is only consistent with dilution levels chosen in advance. The stated basis of determination therefore contradicts the reported values, and the lower bound of the validated linear range is an assumed rather than a demonstrated quantitation limit. (Scope note: the LOD/LOQ tables themselves are §1.4.3/§1.4.4; half the evidence is the level-1 rows of Tables 3–6.)

**Confidence: CERTAIN**

---

### 8. Demonstrated range does not cover the total-impurities specification
**Evidence**
- §1.1, PDF p.5: "Total Impurities — NMT 0.5%" (both manufacturer's and Amneal's limit).
- Top of the demonstrated range, from the 150% rows of Tables 3–6 against the 1000 µg/mL sample concentration (§1.4.3, PDF p.15): Estradiol (surrogate used for unspecified impurities) 1.467 µg/mL = **0.147%**; Δ9,11-Estradiol 1.503 = **0.150%**; 17α-Estradiol 3.831 = **0.383%**; Estrone 2.999 = **0.300%**.
- §1.4.2 and the conclusion (PDF p.15) claim linearity only "in the concentration range of LOQ to 150% of the specification level"; no analyte was evaluated at or above 0.5%.

**Why it is a deficiency** — ICH Q2(R1) §3.3 requires the range to be demonstrated over the interval in which the procedure is applied, and for impurity determination to extend to at least 120% of the specification limit. Reporting a total-impurities result at or above the 0.5% limit — the value on which an OOS decision would be made — requires extrapolation beyond the demonstrated range for every analyte. The report does not establish or discuss the upper reporting range for total impurities.

**Confidence: LIKELY**

---

### 9. Accuracy is not included as a verification parameter, and the only recovery data are at a single concentration level
**Evidence**
- §1.1, PDF pp.5–6, lists the nine attributes evaluated: Specificity; Linearity; Limit of Detection; Limit of Quantitation; Absorptivity Factor; Precision (system, method, intermediate); Stability of Analytical Solutions; Equivalency with the USP Method; System Suitability. **Accuracy, Range and Robustness are absent**, and Table 1 (PDF pp.6–9) contains no Accuracy row.
- The only recovery data in the report are summarised in Table 1 (PDF p.7) under "Method Precision" (means 99.0 / 97.4 / 97.6%; criterion 80.0–120.0%) and detailed in Table 13 (PDF p.20): "six individual samples spiked with the impurities **at the specification level**" — i.e. six determinations at **one** concentration level.

**Why it is a deficiency** — ICH Q2(R1) §4.2 requires accuracy for quantitative impurity procedures to be assessed from a minimum of nine determinations over at least three concentration levels covering the specified range (typically LOQ, 100% and 150% of the limit). The report presents accuracy-type data (percent recovery of spiked impurities) only under the heading of precision, at a single level, so accuracy across the range — in particular at the LOQ, where the linearity data show up to ~25% low-end response depression (finding 5) — is never established.

**Confidence: LIKELY**

---

### 10. The regulatory basis invoked — USP <1226>, verification of *compendial* procedures — does not apply to the method, which the report itself identifies as a vendor-DMF in-house procedure distinct from the USP method
**Evidence**
- §1.1, PDF p.5: "The analytical procedure to determine the Related Compounds of Estradiol by high performance liquid chromatography is **adopted from the vendor's DMF**." Immediately followed by: "As per the USP General Chapters <1226>, i.e. Verification of compendial procedures, **users of compendial analytical procedures are not required to validate these procedures** when first used in the laboratories… Hence, this method is verified by Amneal…".
- The report simultaneously treats the in-house method and the USP method as two different procedures with different system-suitability criteria — Table 1 PDF p.9 and Table 18 PDF p.24: theoretical plates NLT 800 (USP) vs NLT 7000 (in-house); %RSD NMT 2.0 (USP) vs NMT 6.0 (in-house); tailing NMT 1.5 (USP) vs 0.9–1.5 (in-house); resolution NLT 1.0 (USP) vs NLT 2.5 (in-house) — and devotes §1.4.8 to demonstrating "Equivalency with the USP Method".
- Title of the report and every page header: "Verification of Analytical Procedure"; §1.5 (PDF p.27) concludes "The test method is valid…".

**Why it is a deficiency** — A procedure that is not the compendial procedure cannot be qualified under USP <1226>; it must be fully validated under 21 CFR 211.165(e) and ICH Q2(R1). The report cannot both invoke <1226> (which presupposes the procedure *is* compendial) and demonstrate equivalency to a *different* USP method. This mis-categorisation is the root cause of the omitted validation characteristics in finding 9 (accuracy, range, robustness).

**Confidence: CERTAIN** (internal contradiction, both statements on the same page/report)

---

### 11. Table 1 reports an unspecified impurity of 0.15% — above the NMT 0.10% limit — as meeting the acceptance criterion, and drops the footnote that would otherwise leave Total Impurities (0.14%) below one of its own components (0.15%)
**Evidence**
- Table 1, PDF p.9, Equivalency block, USP method column: "Any Unspecified Impurity (Single Largest) — **0.15**"; "Total impurities — **0.14**". A total cannot be smaller than one of its components.
- The acceptance criterion in the same Table 1 cell: "The % impurities should be comparable between In-house method and USP method and **all unknown and known impurity should be within the specification**."
- Specification, §1.1, PDF p.5: "Any Unspecified Impurity — NMT 0.10%" (manufacturer's and Amneal's limit). **0.15% > 0.10%.**
- Table 19, PDF p.24, carries "0.15*" with the footnote "* Largest value of three samples reported" — which resolves the total-vs-component arithmetic but not the limit exceedance. That footnote (the sole content change recorded for Version 02 in §1.6, PDF p.55: "Added footnote to Table 19") is **not** carried into the Table 1 summary on PDF p.9.
- §1.5, PDF p.27, nevertheless concludes "Equivalency with the USP Method: The method is equivalent to USP method" and "The data for each verification characteristic described in this report meets the acceptance criteria".

**Why it is a deficiency** — A result exceeding the specification limit is reported as satisfying an acceptance criterion that explicitly requires all impurities to be within specification, with no investigation, justification, or explanation (e.g. that the USP procedure does not resolve the specified impurities, which is implied by the "N/A" entries but never stated). Separately, the summary table as printed is arithmetically impossible because the qualifying footnote was omitted. (Scope note: the source table, Table 19, is §1.4.8; the entries cited here are in Table 1.)

**Confidence: CERTAIN**

---

### 12. Non-compendial impurity working standards: chromatographic area-percent purity used as the assigned potency, with reported water content ignored and no standard-qualification data
**Evidence**
- §1.2, PDF p.10: "17 α-Estradiol | 113M4057V (Purity: **99.50%**)". Appendix 3 (Sigma-Aldrich E8750 CoA), PDF p.31, reports "Purity (HPLC) — spec 98.00% — result **99.50%**" **and** "Water (by Karl Fischer) — **0.92%**". Using 99.50% without the water correction overstates the as-is potency by ~0.9% (99.50 × 0.9908 = 98.58%).
- §1.2, PDF p.10: "Δ9,11-Estradiol | RY-5-031-c-01S-032713 (Purity: **98.4%**)". Appendix 2 (Dalton Pharma Services CoA), PDF p.30: "Purity: **98.4% by AUC at 260 nm (HPLC)**" — a chromatographic area-percent at a wavelength different from the method's 280 nm detection (§1.1, PDF p.5); no water, residual solvent, or mass-balance assay is reported for this lot.
- Neither material is a compendial reference standard, and no in-house qualification/characterisation of either as a quantitative reference standard is presented in §1.2 or any appendix.

**Why it is a deficiency** — Area-percent chromatographic purity is not an assigned mass potency; using it directly (and ignoring a reported 0.92% water content) introduces bias into the impurity concentrations used for linearity, LOD/LOQ, the absorptivity factors, and recovery. FDA expects non-compendial impurity standards to be fully characterised and their assigned potency corrected for water, residual solvents, and inorganic residue.

**Confidence: LIKELY**

---

### 13. The verification protocol and the governing SOP are referenced but never identified
**Evidence**
- §1.3, PDF p.10: "No deviation was observed from **the protocol** during the method verification…" — no protocol number, version, or approval date is given anywhere in the report (searched full text).
- §1.1, PDF p.5: "…this method is verified by Amneal Pharmaceuticals … as per USP general chapter and **current in-house SOP**" — the SOP is not identified by number or version.
- §1.6, PDF p.55, records only change-control numbers (PW-13-0018, CC_2016_0203), not a protocol reference.

**Why it is a deficiency** — A statement that no deviations from the protocol occurred is not traceable or auditable when the protocol is not identified; a verification report must be linked to its approved, pre-defined protocol (parameters, acceptance criteria, number of determinations) so the reviewer can confirm the acceptance criteria were pre-established rather than set after the data were obtained.

**Confidence: LIKELY**

---

### 14. The report's issue date precedes the preparation and quality-approval signature dates
**Evidence**
- Every page header, PDF pp.2–55: "Method Verification Report No.: MVR-1381-RC, Version No.: 02 — **May 02, 2016**".
- Approval page, PDF p.1: "Prepared By … Date: **05/06/2016** — Sumana Giddu, Analytical R&D"; reviewer/approver dates read 05/06/2016, 05/09/2016 and, for "Approved By … Jitendra Patel — Quality Management", **05/10/2016**.
- The document therefore carries an issue/effective date four days before the author signed it and eight days before Quality approved it. (Signature dates are handwritten and OCR-degraded; the prepared date 05/06/2016 appears twice and is unambiguous, as is the May 02, 2016 header.)

**Why it is a deficiency** — Under good documentation practice a controlled document cannot bear an effective date earlier than the date of its authoring and quality approval; the discrepancy raises a data-integrity/document-control question about when the report content was finalised relative to approval.

**Confidence: LIKELY**

---

## Items explicitly checked and found NOT deficient (recorded so they are not scored as misses)
- **Tables 3–6 regressions**: slope, intercept and correlation coefficient are exactly reproducible from the tabulated concentration/area pairs for all four analytes (e.g. Estradiol slope 6920.93, intercept −377.49 recomputed to the same 2 dp). No arithmetic error.
- **Table 1 vs detail tables (in-scope parameters)**: correlation coefficients in Table 1 (PDF p.6 — 0.998 / 0.999 / 0.999 / 0.998) match Tables 3–6 exactly; notebook references (8135/24, 21, 22, 23) match.
- **Table 2 RRTs** are internally consistent with the retention times (0.87, 1.12, 1.39 = 10.4/12.0, 13.4/12.0, 16.7/12.0) and with Appendix 7.
- **Linearity level concentrations** are consistent multiples of each 100% level and consistent with a 1000 µg/mL sample and each analyte's own limit (Estradiol 0.978 µg/mL ≈ 0.10%; Δ9,11 1.002 ≈ 0.1%; 17α 2.554 ≈ 0.25%; Estrone 1.999 ≈ 0.2%).
- **Appendix 8 (linearity) traceability**: the 100%-level peak areas in the Appendix 8 peak table (PDF p.42) — Δ9,11 16 315, Estradiol 6645, 17α 16 461 — match Tables 3–5 level 5 exactly.
- **Impurity limits in §1.1 (PDF p.5)** match the Aspen Oss CoA specification (Appendix 5, PDF p.35) exactly for all five entries.
- **Standard purities vs CoAs**: Δ9,11 98.4% and 17α 99.50% match Appendices 2 and 3; Estrone 99.9% is correct on the as-is basis per Appendix 4.
- **Standard/material validity at the time of analysis**: chromatograms were acquired 12/08/2014 (Appendices 6, 7, 8). Δ9,11 CoA expiry 04/09/2016; 17α recommended retest JUL2017; Estradiol RS certificate dated 07-Nov-2014; drug substance lot L00036941 retest 20 March 2019 — all valid. No expiry deficiency.
- **Diluent chromatogram at the analyte retention times**: Appendix 6 (PDF p.38) lists Δ9,11, Estradiol, 17α and Estrone as "Missing" — the retention-time-specific part of the specificity criterion is genuinely met.
- **Resolution values** in Appendix 7 (PDF p.40): 3.5 (Estradiol/Δ9,11), 2.9 (17α), 5.8 (Estrone) all exceed NLT 2.5 — no resolution failure (the deficiency in finding 3 is that they are not tabulated, not that they fail).
- **Absorptivity factors** (Table 11, PDF p.18) are exactly reproducible as the mean of area/concentration at the 60%, 100% and 150% linearity levels of Tables 3–6 (Estradiol 6559.877, Δ9,11 16 262.040, 17α 6371.493, Estrone 6871.372), with Response Factor = ratio and AF = 1/RF. Internally consistent.
- **Correlation coefficients all pass** the NLT 0.990 criterion (lowest computed r² = 0.9978). No linearity acceptance-criterion failure.
- **USP method with five standard injections** (Table 18, PDF p.24, injection #6 = N/A) is consistent with USP <621> for a ≤2.0% RSD limit — not a protocol deviation.
- **Retention-time differences** between Table 2 (13.4, 16.7 min) and Appendices 6/8 (13.5, 16.8 min) reflect different HPLC systems (HPLC_04 vs HPLC_07) and the "~ min" qualifier in the Table 2 header — not a contradiction.

TOTAL: 14 (CERTAIN: 6, LIKELY: 8)
