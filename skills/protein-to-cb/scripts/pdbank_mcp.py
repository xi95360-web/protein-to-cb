"""PDB discovery upstream of the independently validated CB server."""
from typing import Annotated
from fastmcp import FastMCP
import pdb_workflow as workflow

mcp = FastMCP(name='PDBank for CB')

@mcp.tool()
def pdb_find_protein_structures(
    protein_name: Annotated[str, 'Protein or gene name; exact gene/name aliases take precedence over partial name matches.'],
    taxonomy_id: Annotated[int | None, 'Optional NCBI source-organism taxonomy ID; no organism is silently imposed.'] = None,
    uniprot_accession: Annotated[str | None, 'Explicit UniProt accession when identity is already established or name search is ambiguous.'] = None,
    max_structures: Annotated[int, 'Number of experimental polymer entities in this page, 1 to100.'] = 20,
    start: Annotated[int, 'Zero-based RCSB result offset; follow next_start to inspect more structures.'] = 0,
    min_sequence_length: Annotated[int | None, 'Optional minimum deposited construct length, not resolved-coordinate coverage.'] = None,
    output_dir: Annotated[str | None, 'Base output directory; every call creates a fresh subdirectory.'] = None,
) -> dict:
    """Resolve a protein through UniProt and find experimental RCSB PDB structure candidates.
    Input is a protein name and optional identity filters; output is reference FASTA, raw JSON and a paginated structure catalog."""
    return workflow.search_protein(protein_name,taxonomy_id,uniprot_accession,max_structures,start,min_sequence_length,output_dir)

@mcp.tool()
def pdb_fetch_structure(
    pdb_id: Annotated[str, 'Four-character experimental PDB accession, for example 6NT5.'],
    output_dir: Annotated[str | None, 'Base output directory; every call creates a fresh subdirectory.'] = None,
) -> dict:
    """Download original RCSB coordinates and inspect chains, ligands and metadata for CB.
    Input is a PDB accession; output is original mmCIF/PDB files and an integrity/chain report."""
    return workflow.fetch_entry(pdb_id,output_dir)

@mcp.tool()
def cb_build_variant_panel(
    reference_fasta_path: Annotated[str, 'Single-record canonical or user-verified parental FASTA; substitutions use its one-based numbering.'],
    structure_pair_json_path: Annotated[str, 'structure_pair.json returned by cb_prepare_structure_pair for the selected two backbones.'],
    variants: Annotated[list[str], 'Unique explicit variant specifications, e.g. WT, G166E, or R71H/G230A; no inferred shorthand.'],
    output_dir: Annotated[str | None, 'Base output directory; every call creates a fresh subdirectory.'] = None,
) -> dict:
    """Build CB full-sequence variant inputs without requiring mutant PDB structures.
    Input is parental FASTA, checked structure mappings and substitutions; output is a sequence CSV and numbering provenance."""
    return workflow.prepare_panel(reference_fasta_path,structure_pair_json_path,variants,output_dir)

if __name__ == '__main__':
    mcp.run(transport='stdio',show_banner=False)
