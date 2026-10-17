# Validation scope

Initial validation date: **2026-10-17**. Platform: **macOS arm64, Python 3.12.14, CPU**.

- All 19 unit tests passed. They cover parental-reference consistency, residue-number mapping, missing positions, duplicate biological sequences, truncated identity searches, empty results versus service failures, configuration preservation, backups, conflict handling, and idempotent installation.
- Both real stdio MCP servers started from the repository checkout. The three upstream tools and two CB tools were discoverable. A real installer invocation using an isolated configuration directory also passed.
- The bundled LplA structures and three-variant panel were scored using the real ProteinMPNN checkpoint. Every raw score, WT baseline, WT-relative value, standardized value, and bias column matched the existing independent native reference calculation. Absolute tolerance was `1e-7`, allowing only numerical CSV round-trip differences in the pinned computation.
- Live UniProt/RCSB queries passed, resolving human HBA1 to P69905. Independent upstream forward testing also covered human STING resolution, unresolved species ambiguity, and a real example with no experimental structure hits.
- The existing local workflow completed protein-name lookup, structure checks, panel preparation, and actual CB scoring for STING WT/G166E. This demonstrates execution of the workflow; it does not experimentally validate a prediction of STING activation.
- The backend scientific source and pinned wheel were copied from an earlier delivery that passed independent numerical and interface acceptance checks. Checksums were verified after copying, and provenance and license notices were retained.

GitHub Actions runs the 19 lightweight tests described above. Model-level numerical checks require a separate `scripts/check_runtime.py --score` invocation. A passing Actions run does not establish numerical reproducibility on every platform, reproduction of the entire paper, or biological validity.

For research use, verify the target identity, allele background, evidence for both states, and mutation coverage. Analyses with different backbones, constructs, panels, seeds, or platforms need their own provenance records and appropriate validation.
