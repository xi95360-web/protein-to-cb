---
name: protein-to-cb
description: Find RCSB PDB structures from protein or gene names, prepare explicitly requested mutant sequences, and coordinate conformational-bias scoring with CB. Use for protein-name-to-CB workflows and structure-readiness requests.
---

# Protein name → structures → CB

Provide an autonomous structure-discovery and CB workflow in the user's language. Use the installed `pdbank` MCP tools upstream of `conformational_biasing`. Public RCSB PDB and UniProt requests need no API keys. Retain source metadata and raw JSON as artifacts rather than flooding the chat.

## Discover identity and structures

Use `pdb_find_protein_structures` with the supplied protein/gene name. Use organism/accession/background already established in the current request or project; do not ask again for known information. If species is not established, do not silently choose the first species. Infer an intended human target only when the surrounding context supports it and disclose that assumption. If several plausible identities remain, report the candidates and ask the smallest necessary identity question before scoring.

The result supplies a canonical reference FASTA when identity resolves, plus a paginated catalog and raw source JSON. Exact reviewed gene/name aliases take priority over partial matches. A truncated identity search is not unique identity. `next_start` signals more experimental entities; inspect further pages or use a construct-length filter when the first page lacks a credible state pair. Do not claim the first page is the whole PDB.

Prefer the user's actual parental FASTA/construct when available. A UniProt canonical sequence is an explicitly declared working reference, not proof of the experimental allele, tag or isoform. Inspect `sequence_background` before selection: RCSB `mutation_count=0` does not prove that two deposited sequences have the same allele. Prefer matched parental backgrounds and state any working-reference change explicitly. If no construct was supplied, label the result exploratory for the declared PDB background; do not claim it describes the user's unverified construct. Do not infer the meanings of unresolved shorthand such as HAQ/H/HA/Q. Use exact substitutions and only the panel established in the current task.

Choose two biological conformations by source evidence, not by taking the top two resolutions or calling WT/mutant two states. Read [structure-selection.md](references/structure-selection.md) when selecting a pair or interpreting missing structures. Use primary structural studies and the deposited metadata to justify state labels. Then download selected entries with `pdb_fetch_structure`. It retains the original mmCIF and original legacy PDB, reports atom-coordinate integrity and author chain IDs, and lists ligands/assemblies. It does not synthesize a biological assembly or repair coordinates.

## Prepare and score

1. Call `cb_prepare_structure_pair` with the downloaded original PDBs, matched author chain IDs and the agreed full parental `reference_sequence` from FASTA. Use only a legacy PDB marked as matching the mmCIF. Preserve state orientation and sources.
2. Inspect `scoring_ready`, construct differences, resolved coverage and excluded positions. A metadata alignment covering the full reference is not evidence that the coordinates resolve every residue. Verify each requested mutation has shared coordinate coverage and correct WT residue identity.
3. Call `cb_build_variant_panel` with the parental FASTA, CB's `structure_pair.json`, and explicit substitutions such as `["WT", "G166E"]`. It validates one-based parental numbering and writes full consensus-length sequences. Substitutions in both-state gaps/mismatches, wrong parental residues, duplicate sites, ambiguous remapping and shorthand fail clearly. Do not edit or relabel structure residues to bypass those failures.
4. Call `cb_score_variant_panel` with the same structures, chains, parental reference and the generated CSV. Keep the tested ProteinMPNN model and seed unless the user supplies another supported choice. Use a persistent project output directory.
5. Report the selected structures/states, identity/background, source citations, evaluated positions, full raw/WT-relative results, output links and limitations. Read source metadata/score artifacts before interpreting them. Model compatibility is not measured activity, occupancy, affinity or free energy.

For score interpretation or a function/activation question, read [score-interpretation.md](references/score-interpretation.md). Separate the model's descriptive signal, independent functional evidence and untested mechanisms. Do not turn a two-row standardized zero into a no-effect conclusion.

When the user supplies only a protein name, autonomously resolve identity, find/download a defensible pair and assess readiness. If the variant panel is already known, continue through scoring without another permission question. Otherwise provide WT structural readiness/baselines when meaningful, and state that no mutant list was supplied; do not invent mutations or launch an exhaustive scan. With just WT plus one mutant, native standardized bias is highly panel-dependent and is not a calibrated ranking; emphasize per-state raw scores and mutant-minus-WT deltas.

## Missing mutant structures

A mutant does **not** ordinarily need its own PDB: its sequence is scored on both selected reference-state backbones. Prefer matched-background reference structures over a WT-versus-mutant structure pairing. Current native mapping excludes sequence mismatches; a mutant template can therefore remove precisely the edited site from shared coverage.

If only one useful conformation is available, distinguish optional single-structure compatibility analysis from CB and report CB as not yet evaluable. A lone AlphaFold prediction, duplicated backbone or unsupported open/closed label is not a substitute for two validated states. Multistate prediction/modeling can be a separately scoped follow-up; do not fabricate an alternate structure or imply that one automatically exists. Missing backbone at the edit, sequence/numbering mismatch or an interface-dependent mechanism beyond the current single-chain model also limits evaluation.

## Local fallback and deployment

If `pdbank` has been configured but is absent from the current tool catalog, reload the MCP connection/client. Its server is this skill's `scripts/pdbank_mcp.py`; logic is in `scripts/pdb_workflow.py`. It uses Python 3.12, FastMCP, Biopython and Gemmi already present in the verified local CB interpreter. The installed MCP configuration records that interpreter. Do not reinstall scientific models just to look up structures. The companion CB server remains separate and unchanged.
