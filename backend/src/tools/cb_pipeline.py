"""Minimal wrappers for the pinned ConformationalBiasing ProteinMPNN workflow."""
from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib.metadata as metadata
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
from typing import Annotated

from fastmcp import FastMCP

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT / "repo" / "ConformationalBiasing"
REVISION = "e6328bc0b3b57ed095f61943732ee4df55376c48"
REFERENCE = f"https://github.com/alicetinglab/ConformationalBiasing/blob/{REVISION}/examples/example_lpla_proteinmpnn.ipynb"
MODEL_NAME = "v_48_020"
NOTEBOOK_SHA256 = "2a9285a2928a188f0ce835da273baa0ddf9410154686a44744310ad53eafa539"
_LOCK = threading.RLock()
cb_pipeline_mcp = FastMCP(name="cb_pipeline")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cb():
    path = REPO / "utilities" / "cbutils.py"
    if not path.is_file():
        raise RuntimeError(f"Pinned ConformationalBiasing implementation is missing: {path}")
    spec = importlib.util.spec_from_file_location("_conformational_biasing_cbutils", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _file(value: str, label: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"{label} file does not exist: {path}")
    return path


def _canonical(sequence: str, label: str, alphabet: set) -> None:
    if not sequence or set(sequence) - alphabet:
        raise ValueError(f"{label} must be a nonempty uppercase sequence of the 20 canonical amino acids.")


def _state(cb, value: str, chain: str, label: str) -> dict:
    import gemmi

    path = _file(value, label)
    if len(chain) != 1 or chain == ",":
        raise ValueError(f"{label}_chain must identify exactly one PDB chain.")
    structure = gemmi.read_pdb(str(path))
    if not len(structure) or chain not in [c.name for c in structure[0]]:
        raise ValueError(f"Chain {chain!r} is absent from the first PDB model of {path}.")
    residues = cb.list_chain_residues(str(path), chain)
    if not residues:
        raise ValueError(f"No supported polymer amino-acid residues in {label} chain {chain!r}.")
    sequence = cb.get_chain_seq(str(path), chain)
    scoring_sequence = cb.get_chain_seq_for_scoring(str(path), chain)
    issues = []
    if any(str(r["icode"]).strip() for r in residues):
        issues.append("Insertion codes are unsupported by the native scoring parser.")
    numbers = [r["seqnum"] for r in residues]
    if len(numbers) != len(set(numbers)):
        issues.append("Repeated residue numbers would be collapsed by upstream sequence extraction.")
    if len(residues) != len(scoring_sequence) or "".join(r["one_letter"] for r in residues) != scoring_sequence:
        issues.append("Utility scoring sequence disagrees with the raw polymer residue count or order.")
    return {"state": label, "pdb_path": str(path), "pdb_sha256": _sha(path), "chain": chain,
            "model_index_zero_based": 0, "number_of_models": len(structure),
            "sequence_with_numbering_gaps": sequence, "scoring_sequence": scoring_sequence,
            "residues": residues, "scoring_issues": issues}


def _pair(cb, pdb1, chain1, pdb2, chain2, reference) -> dict:
    if reference is not None:
        _canonical(reference, "reference_sequence", cb.AA_ALPHABET)
    states = [_state(cb, pdb1, chain1, "state1"), _state(cb, pdb2, chain2, "state2")]
    sequences = ([reference] if reference is not None else []) + [s["sequence_with_numbering_gaps"] for s in states]
    consensus = cb.make_consensus_sequence(sequences)
    if not consensus:
        raise ValueError("Upstream consensus sequence is empty.")
    aligner = cb.setup_aligner()
    maps = []
    for state in states:
        alignment = aligner.align(consensus, state["scoring_sequence"])[0]
        mapping = cb.alignment_to_mapping(alignment)
        maps.append(mapping)
        state.update({"alignment": str(alignment),
                      "mapping_zero_based_pairs": [[int(k), int(v)] for k, v in sorted(mapping.items())],
                      "mapping_one_based_pairs": [[int(k)+1, int(v)+1] for k, v in sorted(mapping.items())],
                      "excluded_consensus_positions_one_based": [i+1 for i in range(len(consensus)) if i not in mapping],
                      "coverage": len(mapping)/len(consensus)})
    shared = set(maps[0]) & set(maps[1])
    return {"reference_sequence": reference, "reference_policy": "Reference, when supplied, is prepended to the native consensus inputs and may be extended.",
            "consensus_sequence": consensus, "consensus_length": len(consensus),
            "consensus_sha256": hashlib.sha256(consensus.encode()).hexdigest(), "states": states,
            "shared_consensus_positions_one_based": [i+1 for i in sorted(shared)],
            "excluded_consensus_positions_one_based": [i+1 for i in range(len(consensus)) if i not in shared],
            "warnings": (["Both states have identical PDB content; this can serve as a negative control."]
                         if states[0]["pdb_sha256"] == states[1]["pdb_sha256"] else []),
            "numbering": "Consensus positions and reported PDB seqnum are distinct; mapping targets index the utility scoring sequence."}


def _parser_check(state: dict, pdb: dict) -> None:
    from colabdesign.mpnn.model import order_aa
    import numpy as np

    sequence = "".join(order_aa.get(int(x), "X") for x in pdb["batch"]["aatype"])
    numbers = np.asarray(pdb["idx"]["residue"]).astype(int).tolist()
    state["parser"] = {"sequence": sequence, "residue_numbers": numbers,
                       "lengths": [int(x) for x in pdb["lengths"]],
                       "missing_ca_count": int(np.sum(pdb["batch"]["all_atom_mask"][:, 1] == 0))}
    if sequence != state["scoring_sequence"]:
        state["scoring_issues"].append("Native parser sequence or length disagrees with the utility scoring sequence.")
    if numbers != [r["seqnum"] for r in state["residues"]]:
        state["scoring_issues"].append("Native parser residue order or length disagrees with the utility polymer residues.")
    if state["parser"]["missing_ca_count"]:
        state["scoring_issues"].append("Native parser retains residues without CA coordinates; full-residue score interpretation is unsupported.")


def _directory(base, task) -> Path:
    parent = Path(base).expanduser().resolve() if base is not None else Path(tempfile.gettempdir()).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"cb-{task}-", dir=parent)).resolve()


def _write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False)+"\n")


def _provenance(cb):
    return {"created_at_utc": datetime.now(timezone.utc).isoformat(), "source_revision": REVISION,
            "source_reference": REFERENCE, "source_file": str(Path(cb.__file__).resolve()),
            "source_sha256": _sha(Path(cb.__file__)),
            "notebook_sha256": NOTEBOOK_SHA256,
            "wrapper_sha256": _sha(Path(__file__)), "state_orientation": "state1 is the first caller structure; state2 is the second caller structure."}


def _pair_artifacts(out, pair):
    data = out / "structure_pair.json"
    fasta = out / "consensus.fasta"
    _write_json(data, pair)
    fasta.write_text(f">consensus\n{pair['consensus_sequence']}\n")
    return [{"description": "Consensus, residue metadata, alignments, mappings and parser readiness", "path": str(data)},
            {"description": "Native consensus sequence for constructing full-sequence panels", "path": str(fasta)}]


@cb_pipeline_mcp.tool()
def cb_prepare_structure_pair(
    state1_pdb_path: Annotated[str, "Local first-state PDB file; only the first model is used."],
    state1_chain: Annotated[str, "Explicit single PDB chain identifier for the first state."],
    state2_pdb_path: Annotated[str, "Local second-state PDB file; only the first model is used."],
    state2_chain: Annotated[str, "Explicit single PDB chain identifier for the second state."],
    reference_sequence: Annotated[str | None, "Optional canonical reference prepended to native consensus inputs; consensus may extend it."] = None,
    output_dir: Annotated[str | None, "Base output directory; each call creates a fresh subdirectory."] = None,
) -> dict:
    """Prepare native consensus mappings and assess two single-chain structures for scoring.
    Input is two local PDBs and explicit chains; output is consensus, coverage and parser-readiness artifacts."""
    with _LOCK, redirect_stdout(sys.stderr):
        cb = _cb()
        pair = _pair(cb, state1_pdb_path, state1_chain, state2_pdb_path, state2_chain, reference_sequence)
        from colabdesign.af.prep import prep_pdb

        for state in pair["states"]:
            try:
                pdb = prep_pdb(state["pdb_path"], chain=state["chain"], ignore_missing=True)
                _parser_check(state, pdb)
            except Exception as exc:
                state["scoring_issues"].append(f"Native parser failed: {type(exc).__name__}: {exc}")
        canonical = not (set(pair["consensus_sequence"]) - cb.AA_ALPHABET)
        pair["scoring_ready"] = canonical and bool(pair["shared_consensus_positions_one_based"]) and all(not s["scoring_issues"] for s in pair["states"])
        pair["consensus_is_canonical"] = canonical
        pair["provenance"] = _provenance(cb)
        out = _directory(output_dir, "prepare")
        artifacts = _pair_artifacts(out, pair)
        return {"message": "Structure-pair preparation completed; inspect scoring_ready and coverage before constructing a panel.",
                "reference": REFERENCE, "artifacts": artifacts, "consensus_length": pair["consensus_length"],
                "shared_position_count": len(pair["shared_consensus_positions_one_based"]),
                "excluded_position_count": len(pair["excluded_consensus_positions_one_based"]),
                "scoring_ready": pair["scoring_ready"], "warnings": pair["warnings"],
                "state_summaries": [{"state": s["state"], "residue_count": len(s["residues"]), "coverage": s["coverage"],
                                     "scoring_issues": s["scoring_issues"]} for s in pair["states"]]}


@cb_pipeline_mcp.tool()
def cb_score_variant_panel(
    state1_pdb_path: Annotated[str, "Local first-state PDB file; only the first model is used."],
    state1_chain: Annotated[str, "Explicit single PDB chain identifier for the first state."],
    state2_pdb_path: Annotated[str, "Local second-state PDB file; only the first model is used."],
    state2_chain: Annotated[str, "Explicit single PDB chain identifier for the second state."],
    variants_path: Annotated[str, "CSV with unique nonempty variant_id and canonical full sequence columns; all sequences match consensus length."],
    reference_sequence: Annotated[str | None, "Optional canonical reference prepended to native consensus inputs; consensus may extend it."] = None,
    seed: Annotated[int, "Native ColabDesign random seed; a nonnegative 32-bit integer."] = 0,
    output_dir: Annotated[str | None, "Base output directory; each call creates a fresh subdirectory."] = None,
) -> dict:
    """Score a caller-provided sequence panel for relative ProteinMPNN compatibility with two states.
    Input is two PDB chains and a full-sequence CSV; output is raw, WT-relative and native panel-scaled score artifacts."""
    with _LOCK, redirect_stdout(sys.stderr):
        import numpy as np
        import pandas as pd

        if not 0 <= seed <= 2**32-1:
            raise ValueError("seed must be a nonnegative 32-bit integer.")
        cb = _cb()
        pair = _pair(cb, state1_pdb_path, state1_chain, state2_pdb_path, state2_chain, reference_sequence)
        consensus = pair["consensus_sequence"]
        _canonical(consensus, "Native consensus", cb.AA_ALPHABET)
        for state in pair["states"]:
            if state["scoring_issues"]:
                raise ValueError(f"{state['state']} is unsupported: {' '.join(state['scoring_issues'])}")
        path = _file(variants_path, "variants_path")
        panel = pd.read_csv(path, dtype=str, keep_default_na=False)
        if not {"variant_id", "sequence"}.issubset(panel.columns) or panel.empty:
            raise ValueError("variants_path must contain at least one row and the columns variant_id,sequence.")
        panel = panel[["variant_id", "sequence"]].copy()
        if panel.variant_id.str.strip().eq("").any() or panel.variant_id.duplicated().any():
            raise ValueError("variant_id values must be nonempty and unique.")
        shared = {i-1 for i in pair["shared_consensus_positions_one_based"]}
        if not shared:
            raise ValueError("The structures have no shared consensus positions for comparable variant scoring.")
        for row in panel.itertuples(index=False):
            _canonical(row.sequence, f"Variant {row.variant_id!r}", cb.AA_ALPHABET)
            if len(row.sequence) != len(consensus):
                raise ValueError(f"Variant {row.variant_id!r} has length {len(row.sequence)}; consensus length is {len(consensus)}.")
            missing = [i+1 for i, (a, b) in enumerate(zip(consensus, row.sequence)) if a != b and i not in shared]
            if missing:
                raise ValueError(f"Variant {row.variant_id!r} edits consensus positions absent from one or both mappings: {missing}.")
        from colabdesign.mpnn import mk_mpnn_model
        import colabdesign
        import jax

        # Notebook cell 5: one model, per-state prep, mapped-consensus baseline,
        # then mapped full-sequence scores. Scientific scoring remains in cbutils.
        model = mk_mpnn_model(MODEL_NAME, backbone_noise=0.0, dropout=0.0, seed=seed)
        baselines = {}
        for state in pair["states"]:
            label = state["state"]
            model.prep_inputs(pdb_filename=state["pdb_path"], chain=state["chain"], homooligomer=False,
                              fix_pos=None, inverse=True, verbose=True)
            _parser_check(state, model.pdb)
            if state["scoring_issues"]:
                raise ValueError(f"{label} is unsupported: {' '.join(state['scoring_issues'])}")
            mapping = dict(state["mapping_zero_based_pairs"])
            wt = cb.mapping_to_sequence(consensus, state["scoring_sequence"], mapping)
            baseline = float(cb.mpnn_score(wt, model))
            scores = [float(cb.mpnn_score(cb.mapping_to_sequence(seq, state["scoring_sequence"], mapping), model))
                      for seq in panel.sequence]
            if not np.isfinite(baseline) or not np.isfinite(scores).all():
                raise RuntimeError(f"Native {label} score is non-finite; no replacement scoring formula is applied.")
            baselines[label] = {"raw_score": baseline, "mapped_consensus_sequence": wt}
            panel[f"raw_{label}"] = scores
            panel[f"wt_{label}"] = baseline
            panel[f"pmpnn_{label}"] = np.asarray(scores) - baseline
        # Notebook cell 7, retaining native population scaling over caller panel only.
        cb.add_scaled_outputs(panel, "pmpnn", state1_col="state1", state2_col="state2")
        if not np.isfinite(panel.select_dtypes(include="number").to_numpy()).all():
            raise RuntimeError("Native panel scaling produced non-finite outputs.")
        package = Path(colabdesign.__file__).resolve().parent
        provenance = _provenance(cb)
        provenance.update({"variants_path": str(path), "variants_sha256": _sha(path), "seed": seed,
                           "model": MODEL_NAME, "backbone_noise": 0.0, "dropout": 0.0,
                           "prep_inputs": {"homooligomer": False, "fix_pos": None, "inverse": True, "ignore_missing": True},
                           "checkpoint_sha256": _sha(package / "mpnn" / "weights" / f"{MODEL_NAME}.pkl"),
                           "colabdesign_direct_url": json.loads(metadata.distribution("colabdesign").read_text("direct_url.json") or "null"),
                           "source_hashes": {name: _sha(package / name) for name in ["mpnn/model.py", "mpnn/score.py", "af/prep.py", "shared/protein.py"]},
                           "versions": {name: metadata.version(name) for name in ["colabdesign", "jax", "jaxlib", "numpy", "pandas", "fastmcp"]},
                           "jax_devices": [str(d) for d in jax.devices()], "wt_baselines": baselines,
                           "score_semantics": "Raw sums of conditional natural-log probabilities; pmpnn_stateN = raw_stateN - separately scored mapped-consensus WT. Higher raw is more compatible.",
                           "normalization": "Native ddof=0 population scaling over the supplied panel only; zero variance yields zeros. state1_bias = state1_scaled - state2_scaled; state2_bias is its negative.",
                           "limitations": ["Fixed-backbone single-chain sequence compatibility; no activity, occupancy, free-energy or kinetic prediction.",
                                           "Validated reference is bundled LplA on the pinned CPU environment; other proteins and devices require appropriate validation.",
                                           "Insertion codes and parser/utility residue disagreement are unsupported; edits require mapping coverage in both structures."]})
        pair["scoring_ready"] = True
        out = _directory(output_dir, "score")
        artifacts = _pair_artifacts(out, pair)
        score_path, provenance_path = out / "variant_scores.csv", out / "provenance.json"
        panel.to_csv(score_path, index=False, float_format="%.17g")
        _write_json(provenance_path, provenance)
        artifacts += [{"description": "Panel sequences, raw scores, WT baselines, deltas and native scaled scores and biases", "path": str(score_path)},
                      {"description": "Input, source, checkpoint, seed, model, score and normalization provenance", "path": str(provenance_path)}]
        return {"message": "ProteinMPNN panel scoring completed; scaled biases depend on the supplied panel.",
                "reference": REFERENCE, "artifacts": artifacts, "variant_count": len(panel),
                "consensus_length": len(consensus), "shared_position_count": len(shared),
                "model": MODEL_NAME, "seed": seed, "wt_raw_scores": {k: v["raw_score"] for k, v in baselines.items()}}
