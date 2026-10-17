# Choosing a defensible CB pair

Rank metadata as a discovery aid. Biological state selection needs the primary structural evidence and inspection of the actual chain inputs.

- Confirm target identity with the same UniProt accession and source organism. Homologs from different species are not interchangeable states. For example, STING 6NT5 is human apo whereas 6NT7 is chicken cGAMP-bound; they must not silently become a human WT/G166E pair.
- Compare construct length, mutations, isoform/background and resolved residues. Prefer minimal sequence differences and comparable structural quality; sequence alignments in deposited metadata do not establish coordinate coverage.
- Establish state labels from the study and deposited ligand/assembly context. Apo/bound may be meaningful but is not automatically inactive/active. WT/mutant is a sequence distinction, not state proof.
- Download source mmCIF and legacy PDB, retain hashes, and verify chain IDs/numbering. The connector reports the asymmetric unit and leaves biological assembly decisions explicit. The downstream CB route evaluates a single selected chain; oligomer/ligand/side-chain effects are not represented merely by a state label.
- Validate the actual pair with CB. A requested edit outside either backbone, at a sequence mismatch excluded by native mapping, or with incorrect parental residue identity is not evaluable. Do not silently drop the edit or substitute another species.
- A nearly identical backbone pair can lack discriminating information. Do not interpret a small bias as proof of no biological effect. State inference remains conditional on the selected pair.

A protein-name-only run can finish as `ready`, `identity_resolution_required`, `state_evidence_required`, `no_alternative_state`, `position_not_covered` or an explicit service failure. A partial discovery outcome is useful; it is not a numerical prediction.

## Authoritative endpoints

- RCSB Search API documentation: https://search.rcsb.org/
- RCSB Data API documentation: https://data.rcsb.org/
- Experimental coordinates: `https://files.rcsb.org/download/{PDB_ID}.cif` and `.pdb`.
- UniProt REST: https://rest.uniprot.org/uniprotkb
- CB native workflow: https://github.com/alicetinglab/ConformationalBiasing

Public API requests are bounded and preserve raw responses, endpoints, timestamps and hashes. An empty search result is distinct from a service outage; pagination and metadata retrieval failures remain visible in catalog artifacts. No API credentials are required.
