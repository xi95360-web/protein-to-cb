# Protein to CB 🧬

**Describe a protein and its variants in Codex. Find reference structures, check coverage, and run Conformational Biasing through chat.**

> Use CB to analyze human STING WT and G166E. Find suitable reference conformations and explain the results.

Protein to CB connects RCSB PDB and UniProt to the authors' CB method while retaining structure provenance, sequence backgrounds, residue mappings, and scoring records. The scientific model and scoring method come from [Ting Lab's ConformationalBiasing](https://github.com/alicetinglab/ConformationalBiasing). This project provides the chat workflow, MCP wrappers, input checks, installation, and maintenance tools.

## Everyday use

Ask naturally in Codex, or invoke `$protein-to-cb` explicitly:

- “Find two reference conformations of human STING suitable for CB.”
- “Evaluate WT and G166E against these reference structures and explain the scores.”
- “I only have a protein name, without a mutant PDB. Check whether scoring is possible.”

With a protein name alone, the workflow first resolves identity and assesses structural readiness. If an explicit variant panel is already established in the chat, it continues through scoring. It asks when species is ambiguous and reports missing evidence when no credible second conformation or resolved mutation site is available. It does not treat the first two search hits as two biological states or expand the mutation panel without a request.

**A mutant usually does not need its own PDB.** Its sequence is scored against two selected reference-state backbones, provided the edited position maps correctly to both. CB does not generate a new mutant structure.

## First-time installation

Validated platform: **macOS arm64, Python 3.12, CPU**. Other platforms and GPUs have not undergone equivalent numerical validation. Network access is needed to install dependencies and query public databases. No PDB or UniProt API key is required. You must already have a working Codex installation.

Clone the repository and run the setup once:

```sh
git clone https://github.com/xi95360-web/protein-to-cb.git
cd protein-to-cb
python3.12 scripts/setup.py
python3.12 scripts/install_codex.py
```

Restart Codex or its MCP connections to load the tools and skill. Everyday use then takes place in chat.

The installer preserves unrelated Codex settings and creates a private backup before changing an existing configuration. If a connection with the same name points elsewhere, installation stops and preserves that connection. Users with an existing working installation can continue using it; maintaining this repository does not require reinstalling it.

To reuse a compatible environment without installing packages into it:

```sh
python3.12 scripts/setup.py --reuse-python /absolute/path/to/python
```

The interpreter location is stored in a local file excluded from Git. To preview the proposed Codex configuration, run `python3.12 scripts/install_codex.py --preview`.

## Reading the results

Outputs include structure sources, the declared reference background, shared coverage, full variant sequences, per-state raw scores, WT-relative changes, and native standardized scores. Each MCP call creates a separate output directory.

- Higher raw scores indicate greater model compatibility between a sequence and the fixed backbone.
- `mutant − WT < 0` means lower compatibility in that state; it does not directly mean lower activity.
- Differences between states can suggest a conformational preference. They are not free energies, state probabilities, or activity fold changes.
- With only WT and one mutant, panel standardization can be degenerate. Same-direction changes in both states yield identical ±1 values and a zero bias, which does not establish the absence of a conformational effect.
- Activation, binding, enzyme activity, or selectivity require independent evidence linking the selected states to those functions. This workflow is not a general-purpose functional predictor.

See [Score interpretation and experimental evidence](docs/scoring.md) for details.

## Checks and maintenance

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/check_runtime.py --score --network
```

The second command starts both real MCP servers, checks pinned source and model artifacts, runs numerical acceptance checks on a three-variant LplA panel, and queries public databases. Outputs are written to the Git-ignored `runs/doctor/` directory. If you reused an environment, replace `.venv/bin/python` with its interpreter.

Investigate numerical differences on another platform rather than loosening tolerances to hide them. GitHub Actions runs lightweight unit tests; it does not reproduce model scores or biological experiments. Repository maintenance uses ordinary commits and pull requests. No automatic deployment, scheduled analysis, or client update is configured.

See [Contributing and maintenance](CONTRIBUTING.md) and [Validation scope](docs/validation.md).

## Repository layout

| Path | Contents |
|---|---|
| `skills/protein-to-cb/` | Automatically discoverable Codex skill, RCSB/UniProt MCP tools, and variant-panel preparation |
| `backend/` | Validated CB MCP package, pinned upstream source, and ColabDesign wheel with model weights |
| `scripts/` | Runtime setup, configuration installation, and real-server checks |
| `tests/` | Identity, sequence, coverage, and configuration checks, plus fixed LplA acceptance inputs |

The backend includes a pinned model wheel of approximately 24 MB, but no Python virtual environment. Personal Codex settings, credentials, paper PDFs, and local run directories are excluded from version control.

## Sources and citation

- CB: Cavanagh et al., *Science* (2026), [10.1126/science.adv7953](https://doi.org/10.1126/science.adv7953). Pinned revisions and checksums are recorded in `backend/SOURCE_PROVENANCE.json`.
- ProteinMPNN: [10.1126/science.add2187](https://doi.org/10.1126/science.add2187).
- [RCSB Search API](https://search.rcsb.org/), [RCSB Data API](https://data.rcsb.org/), and [UniProt REST API](https://www.uniprot.org/help/api).
- Third-party attribution and licenses are documented in [backend/THIRD_PARTY_NOTICES.md](backend/THIRD_PARTY_NOTICES.md). Workflow integration code is MIT-licensed; third-party components retain their own licenses.
