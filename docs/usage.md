# Operating guide: use Protein to CB in Codex

This guide covers everyday use after installation. Start with the [README](../README.md) if you are installing the workflow for the first time.

## 1. Connect the local tools

The workflow uses two local MCP connections:

| Connection | Purpose | Tools |
|---|---|---|
| `pdbank` | Protein identity, experimental structures, and validated variant sequences | `pdb_find_protein_structures`, `pdb_fetch_structure`, `cb_build_variant_panel` |
| `conformational_biasing` | Two-state preparation and ProteinMPNN scoring | `cb_prepare_structure_pair`, `cb_score_variant_panel` |

Both connections must be enabled, and their interpreter, server script, and working-directory paths must exist. After installation or a configuration repair, restart the connections or the app. Check the active connection list with `/mcp` where supported. See the [official MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

A successful standalone local test does not automatically load tools into an already-open chat. If a chat reports that these tools are unavailable, reload the connections/client before trying again. The installed `protein-to-cb` skill guides the workflow; it does not replace the two running MCP services.

## 2. Run a first example

In a local Codex chat, paste:

> Use $protein-to-cb to analyze human STING WT and G166E. For this demonstration, use a clearly declared R232 parental background. Find and justify two suitable reference conformations, verify G166 coverage in both, and score only WT and G166E. Save all outputs in a persistent project folder. Report the selected structures and chains, raw scores, mutant-minus-WT scores, limitations, and output links. Explain any small-panel normalization problem.

The R232 background is an explicit demonstration assumption. It is not confirmation of your experimental construct. For research on your own construct, provide its parental FASTA and use that sequence as the reference.

You can ask in any language. English repository documentation does not require English chat prompts. The skill name is optional when Codex correctly recognizes the request; `$protein-to-cb` makes the intended workflow explicit.

A normal run proceeds through:

1. Resolve protein identity and source organism with UniProt.
2. Inspect experimental PDB candidates, sequence backgrounds, and structural evidence.
3. Download reference structures and check original PDB/mmCIF consistency.
4. Prepare the selected chains and check shared coverage at each requested edit.
5. Build the explicitly requested sequence panel and score it on both backbones.
6. Explain the result with sources, assumptions, limitations, and saved artifacts.

If a required input or state is genuinely ambiguous, the workflow asks a focused question or reports that scoring is not yet supported. A useful readiness report is a valid outcome; a numeric score is not guaranteed for every protein.

## 3. Start with discovery only

To inspect inputs before running a model, paste:

> Use $protein-to-cb to find reference conformations for human STING. Resolve its identity, compare deposited sequence backgrounds, and report whether G166 is covered in a defensible two-state pair. Stop after the readiness report; do not score variants yet.

With a protein name alone, discovery can proceed, but species and parental background may need clarification. Supply an organism or UniProt accession when possible. The workflow does not invent a variant panel or run a saturation scan without a request.

## 4. Supply your own reference and structures

Useful inputs are:

| Input | What to provide |
|---|---|
| Target | Protein/gene name plus organism; a UniProt accession is helpful |
| Parental sequence | A single-record FASTA for the exact construct or declared working reference |
| Variants | `WT` and explicit one-based substitutions such as `G166E` |
| Optional reference structures | Absolute paths to both local PDBs, author chain IDs, and evidence for their state labels |
| Output location | A persistent project folder where you want the artifacts saved |

For example:

> Use $protein-to-cb with the parental FASTA at `/absolute/path/parent.fasta`, state 1 PDB `/absolute/path/apo.pdb` chain A, and state 2 PDB `/absolute/path/bound.pdb` chain A. Evaluate only WT and G166E. Verify the reference residue, construct background, and shared coverage before scoring. Save outputs under `/absolute/path/results`.

Replace all example paths with real files. Mutation numbering follows the supplied parental FASTA, not an assumed PDB residue index. Labels such as HAQ require explicit substitutions; the workflow does not infer their meaning. Conflicting edits, duplicate resulting sequences, unsupported residues, and edits absent from either mapping are rejected.

**A mutant PDB is usually unnecessary.** The mutant sequence is evaluated on the two selected reference-state backbones. Missing a mutant structure is different from missing a credible reference state or missing backbone coverage at the edited position.

## 5. Read and retain the outputs

Each call creates a fresh subdirectory. Ask Codex to provide the actual paths rather than guessing generated folder names.

| Artifact | Use |
|---|---|
| `catalog.json` | Identity, experimental candidates, deposited sequence differences, pagination, and retrieval issues |
| `reference.fasta` | Canonical lookup reference; verify its suitability for your construct |
| `structure.json`, original `.cif` and `.pdb` | Download provenance, chains, residue metadata, and coordinate-integrity checks |
| `structure_pair.json` | Selected chain mappings, shared coverage, exclusions, and technical scoring readiness |
| `variants.csv`, `panel.json` | Full consensus-coordinate sequences, explicit edits, numbering, and input hashes |
| `variant_scores.csv` | Raw, WT-relative, and native standardized outputs |
| `provenance.json` | Scientific source, model, checkpoint, seed, device, and input provenance |
| `requests.json` and raw JSON files | Public endpoints and source responses |

Readiness confirms supported parsing and mapping. It does not, by itself, prove that the chosen structures represent biologically appropriate states.

Higher raw scores mean greater model sequence/backbone compatibility. A negative mutant-minus-WT value means reduced compatibility on that backbone. Neither is a direct activity measurement. Two-state comparisons do not yield free energies, activation barriers, or conformational percentages.

With WT plus one mutant, same-direction changes in both states can standardize to identical values and give a zero bias. Do not interpret that zero as proof of no effect. Read [Score interpretation](scoring.md) before drawing functional conclusions.

## 6. Verify a local installation

From the repository directory, using the environment prepared during setup:

```sh
.venv/bin/python scripts/check_runtime.py
.venv/bin/python scripts/check_runtime.py --network
.venv/bin/python scripts/check_runtime.py --score
```

If setup reused another interpreter, replace `.venv/bin/python` with that exact interpreter. Keep virtual-environment interpreter paths intact rather than resolving their symlinks to a base Python.

- The first command checks pinned artifacts and discovers all five tools through real stdio connections.
- `--network` additionally resolves a public example target through UniProt/RCSB.
- `--score` runs the bundled three-variant LplA acceptance example and compares every score column to the numerical reference. It is an installation check, not validation of a new protein's biology.

Results and server logs are saved under `runs/doctor/`. These checks launch services from the repository; they do not prove that an existing Codex configuration points to the same checkout. Inspect the configured connections separately when diagnosing chat failures.

## 7. Troubleshoot common problems

| Symptom | What to check or do |
|---|---|
| Skill is visible, but tools are missing | Enable both connections and reload the client. Skill discovery and server connectivity are separate. |
| “No such file or directory” at startup | Check the configured Python, server-script, and `cwd` paths. A moved project folder can invalidate all three. |
| The project was moved | Open the project at its new location. Back up the configuration, update only the affected connection paths and path-valued environment entries, then verify startup. Also check the ignored `.runtime.json` if you reused an interpreter. Do not globally rewrite unrelated settings. |
| Existing-connection conflict during installation | The installer preserves the current connection. Review the paths and choose a deliberate migration; repeated installation does not repair conflicting entries automatically. |
| Public lookup fails | Distinguish a network/service error from a valid search with zero hits. Retry when the service is available; do not infer that the protein has no structures from an outage. |
| Several protein identities remain | Specify species, accession, or parental FASTA. Do not select the first hit by convenience. |
| No credible second state is available | Report two-state CB as not yet evaluable. Duplicating one backbone does not create an alternative state. |
| A requested site is excluded | Inspect shared coverage and reference identity. Do not silently omit the edit or renumber a structure to force a score. |
| A two-row panel returns zero bias | Inspect raw and WT-relative columns and the normalization explanation. Zero may be a panel artifact. |
| A local test passes but chat still cannot call tools | Verify the saved Codex paths, then restart the MCP connections/client. A previous chat may retain its old tool catalog. |

When reporting a problem, include the connection name, exact error, platform, Python version, and relevant non-secret logs. Do not paste credentials or your entire personal Codex configuration.

## 8. Keep the workflow maintainable

Use the [public repository](https://github.com/xi95360-web/protein-to-cb) as the maintenance source. Pulling new code does not automatically update a copied global skill or migrate existing client settings. Follow [Contributing and maintenance](../CONTRIBUTING.md) when reviewing an update, and retain the [validation boundaries](validation.md).
