"""Public RCSB/UniProt I/O and explicit sequence-panel preparation for CB."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

AA = set('ACDEFGHIKLMNPQRSTVWY')
RCSB = 'https://data.rcsb.org/rest/v1/core'
SEARCH = 'https://search.rcsb.org/rcsbsearch/v2/query'
UNIPROT = 'https://rest.uniprot.org/uniprotkb'
REFERENCE = 'https://search.rcsb.org/'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def directory(base, prefix):
    parent = Path(base).expanduser().resolve() if base else Path(tempfile.gettempdir()).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix+'-', dir=parent)).resolve()


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def artifact(path, description):
    return {'path': str(path.resolve()), 'description': description}


def fetch(url, payload=None):
    """Bounded public requests; an empty search result is distinct from an outage."""
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {'User-Agent': 'ProteinToCB/1.0 public-research-client', 'Accept': 'application/json'}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    for attempt in range(2):
        try:
            request = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read(30_000_001)
                if len(data) > 30_000_000:
                    raise ValueError('Response exceeds the 30 MB limit; use a dedicated bulk download.')
                return data, {'url': url, 'method': 'POST' if body else 'GET', 'query': payload,
                              'status': response.status, 'headers': {k: response.headers[k] for k in ('X-Total-Results','Link','Last-Modified','ETag') if k in response.headers},
                              'sha256': sha(data), 'bytes': len(data), 'retrieved_at_utc': datetime.now(timezone.utc).isoformat()}
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 502, 503, 504) and attempt == 0:
                try: delay = min(max(float(exc.headers.get('Retry-After','1')),0),5)
                except ValueError: delay = 1
                time.sleep(delay)
                continue
            raise RuntimeError(f'Public API request failed: HTTP {exc.code} from {url}') from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == 0:
                time.sleep(1)
                continue
            raise RuntimeError(f'Public API unavailable at {url}: {exc}') from exc


def json_request(url, out, name, log, payload=None):
    data, record = fetch(url, payload)
    path = out / (name+'.json')
    if record['status'] == 204 or not data:
        value = {'total_count': 0, 'result_set': []}
        path.write_bytes(data)
        record['empty_http_response'] = True
        record['returned_normalization'] = 'Empty HTTP response represented as zero search hits; raw file remains exact bytes.'
    else:
        value = json.loads(data)
        path.write_bytes(data)
    record['raw_file'] = str(path)
    log.append(record)
    return value


def accession_id(value):
    value = value.strip().upper()
    if not re.fullmatch(r'[A-Z0-9]{6,10}(?:-[1-9][0-9]*)?', value):
        raise ValueError('Provide a UniProt accession, such as Q86WV6; arbitrary URLs are not accepted.')
    return value


def pdb_id(value):
    value = value.strip().upper()
    if not re.fullmatch(r'[1-9][A-Z0-9]{3}', value):
        raise ValueError('This connector accepts a four-character experimental PDB ID, such as 6NT5.')
    return value


def protein_summary(protein):
    names = protein.get('proteinDescription', {})
    name = (names.get('recommendedName') or next(iter(names.get('submissionNames',[])),{})).get('fullName',{}).get('value')
    return {'accession': protein.get('primaryAccession'), 'entry_id': protein.get('uniProtkbId'),
            'protein_name': name, 'organism': protein.get('organism'), 'genes': protein.get('genes',[]),
            'sequence_length': protein.get('sequence',{}).get('length'), 'entry_type': protein.get('entryType')}


def exact_alias(protein, query):
    values = []
    for gene in protein.get('genes', []):
        values.append(gene.get('geneName',{}).get('value',''))
        values.extend(x.get('value','') for x in gene.get('synonyms',[]))
    desc = protein.get('proteinDescription',{})
    for record in [desc.get('recommendedName',{})] + desc.get('alternativeNames',[]):
        values.append(record.get('fullName',{}).get('value',''))
        values.extend(x.get('value','') for x in record.get('shortNames',[]))
    return query.casefold() in {v.casefold() for v in values}


def sequence_background(reference, entity_sequence):
    """Expose deposited construct differences even when RCSB reports zero mutations."""
    from Bio.Align import PairwiseAligner
    sequence=''.join(entity_sequence.split())
    aligner=PairwiseAligner();aligner.mode='global';aligner.match_score=2;aligner.mismatch_score=-0.5;aligner.open_gap_score=-10;aligner.extend_gap_score=-0.5
    alignments=aligner.align(reference,sequence);alignment=alignments[0]
    try:alignments[1]
    except IndexError:unique=True
    else:unique=False
    differences=[];mapped=[]
    for (b,e),(c,f) in zip(*alignment.aligned):
        for i,j in zip(range(int(b),int(e)),range(int(c),int(f))):
            mapped.append(i+1)
            if reference[i]!=sequence[j]:differences.append({'reference_position_one_based':i+1,'reference_residue':reference[i],'entity_residue':sequence[j]})
    return {'alignment_is_unique':unique,'substitutions':differences,'aligned_reference_positions_one_based':mapped,
            'unmapped_reference_position_count':len(reference)-len(mapped),'entity_unaligned_residue_count':len(sequence)-len(mapped),
            'interpretation':'Deposited sequence versus selected reference, not coordinate coverage. Differences may be alleles, tags, fusions or engineered changes; mutation_count=0 does not prove identical background.'}


def search_protein(protein_name, taxonomy_id=None, uniprot_accession=None, max_structures=20, start=0, min_sequence_length=None, output_dir=None):
    if not protein_name.strip() or len(protein_name)>200:
        raise ValueError('protein_name must be a nonempty protein/gene name of at most 200 characters.')
    if taxonomy_id is not None and (type(taxonomy_id) is not int or taxonomy_id<=0):
        raise ValueError('taxonomy_id must be a positive NCBI taxonomy integer.')
    if not 1 <= max_structures <= 100 or start < 0:
        raise ValueError('max_structures must be 1..100 and start must be nonnegative.')
    if min_sequence_length is not None and min_sequence_length<=0:
        raise ValueError('min_sequence_length must be positive.')
    out = directory(output_dir,'pdb-search'); raw = out/'raw'; raw.mkdir(); log=[]
    if uniprot_accession:
        protein = json_request(f'{UNIPROT}/{accession_id(uniprot_accession)}.json',raw,'uniprot-entry',log)
        if taxonomy_id and protein.get('organism',{}).get('taxonId') != taxonomy_id:
            raise ValueError('The supplied UniProt accession does not match taxonomy_id.')
        proteins=[protein]; identity_rule='explicit UniProt accession'; identity_truncated=False
    else:
        quoted = protein_name.replace('\\','\\\\').replace('"','\\"')
        query = f'(gene:"{quoted}" OR protein_name:"{quoted}") AND reviewed:true'
        if taxonomy_id: query += f' AND organism_id:{taxonomy_id}'
        response = json_request(UNIPROT+'/search?'+urllib.parse.urlencode({'query':query,'format':'json','size':25}),raw,'uniprot-search',log)
        proteins=response.get('results',[])
        exact=[p for p in proteins if exact_alias(p,protein_name)]
        if exact: proteins=exact
        identity_rule='exact gene/name alias among returned reviewed candidates' if exact else 'reviewed name-search candidates'
        # A truncated non-exact search must not be mistaken for an unambiguous identity.
        total=int(log[-1]['headers'].get('X-Total-Results',len(response.get('results',[]))))
        identity_truncated=total>25
    candidates=[protein_summary(p) for p in proteins]
    report={'status':'identity_resolution_required','query':protein_name,'taxonomy_id':taxonomy_id,
            'identity_rule':identity_rule,'identity_search_truncated':identity_truncated,'protein_candidates':candidates,'structures':[],
            'caveats':['Canonical UniProt sequence is a declared reference choice, not confirmation of the user construct or allele.',
                       'Sequence coverage in metadata is not coordinate coverage; inspect downloaded coordinates with CB.',
                       'Apo/ligand-bound wording is a structural annotation, not an automatically verified active/inactive state.']}
    artifacts=[]
    if len(proteins)==1 and not identity_truncated:
        protein=proteins[0]; accession=protein['primaryAccession']; sequence=protein['sequence']['value']
        fasta=out/'reference.fasta';fasta.write_text(f'>{accession} canonical reference; taxon={protein["organism"]["taxonId"]}\n{sequence}\n')
        artifacts.append(artifact(fasta,'Canonical reference sequence; confirm experimental background separately'))
        term={'type':'terminal','service':'text','parameters':{'attribute':'rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession','operator':'exact_match','value':accession}}
        if min_sequence_length:
            term={'type':'group','logical_operator':'and','nodes':[term,{'type':'terminal','service':'text','parameters':{'attribute':'entity_poly.rcsb_sample_sequence_length','operator':'greater_or_equal','value':min_sequence_length}}]}
        payload={'query':term,'return_type':'polymer_entity','request_options':{'paginate':{'start':start,'rows':max_structures},'results_content_type':['experimental']}}
        results=json_request(SEARCH,raw,'rcsb-search',log,payload)
        cache={}; errors=[]
        for hit in results.get('result_set',[]):
            entity_identifier=hit['identifier']; identifier,entity_id=entity_identifier.rsplit('_',1)
            try:
                entity=json_request(f'{RCSB}/polymer_entity/{identifier}/{entity_id}',raw,'entity-'+entity_identifier,log)
                if identifier not in cache:
                    cache[identifier]=json_request(f'{RCSB}/entry/{identifier}',raw,'entry-'+identifier,log)
                entry=cache[identifier];ids=entity.get('rcsb_polymer_entity_container_identifiers',{});poly=entity.get('entity_poly',{});content=entry.get('rcsb_entry_container_identifiers',{})
                refs=ids.get('uniprot_ids',[])
                if accession not in refs:
                    errors.append({'entity':entity_identifier,'error':'Search hit did not confirm the requested UniProt accession in retrieved metadata.'});continue
                report['structures'].append({'pdb_id':identifier,'entity_id':entity_id,'entity_identifier':entity_identifier,
                  'title':entry.get('struct',{}).get('title'),'methods':[x.get('method') for x in entry.get('exptl',[])],
                  'resolution_angstrom':entry.get('rcsb_entry_info',{}).get('resolution_combined'),
                  'source_organisms':entity.get('rcsb_entity_source_organism',[]),'author_chain_ids':ids.get('auth_asym_ids',[]),
                  'label_chain_ids':ids.get('asym_ids',[]),'uniprot_accessions':refs,
                  'entity_sequence_length':poly.get('rcsb_sample_sequence_length'), 'mutation_count':poly.get('rcsb_mutation_count'),
                  'engineered_mutations':entity.get('rcsb_polymer_entity',{}).get('pdbx_mutation'),
                  'reference_alignment':entity.get('rcsb_polymer_entity_align',[]),'entity_sequence':poly.get('pdbx_seq_one_letter_code_can'),
                  'sequence_background':sequence_background(sequence,poly['pdbx_seq_one_letter_code_can']),
                  'coordinate_coverage_checked':False,'nonpolymer_entity_ids':content.get('non_polymer_entity_ids',[]),
                  'assembly_ids':content.get('assembly_ids',[]),'primary_citation':entry.get('rcsb_primary_citation'),
                  'source_url':f'https://www.rcsb.org/structure/{identifier}'})
            except (RuntimeError, ValueError, KeyError) as exc:
                errors.append({'entity':entity_identifier,'error':str(exc)})
            time.sleep(0.1)
        total=results.get('total_count',0);next_start=start+len(results.get('result_set',[]))
        report.update(status='structures_found' if report['structures'] else 'no_structures_found' if not results.get('result_set') else 'metadata_unavailable',
                      resolved_protein=protein_summary(protein),reference_fasta_path=str(fasta),total_structure_entities=total,
                      page_start=start,returned_search_hits=len(results.get('result_set',[])),next_start=next_start if next_start<total else None,
                      search_truncated=next_start<total,metadata_errors=errors)
    report_path=out/'catalog.json';save_json(report_path,report);manifest=out/'requests.json';save_json(manifest,log)
    artifacts=[artifact(report_path,'Protein identity candidates and structure metadata, with explicit pagination'),artifact(manifest,'Public endpoint requests, response hashes and raw JSON locations')]+artifacts
    return {'message':'Protein/structure lookup completed; resolve identity and justify conformational states before CB.', 'reference':REFERENCE,'artifacts':artifacts,
            'status':report['status'],'protein_candidate_count':len(candidates),'structure_candidate_count':len(report['structures']),
            'catalog_path':str(report_path),'resolved_accession':report.get('resolved_protein',{}).get('accession'),
            'reference_fasta_path':report.get('reference_fasta_path'),'next_start':report.get('next_start')}


def fetch_entry(identifier, output_dir=None):
    import gemmi
    identifier=pdb_id(identifier);out=directory(output_dir,'pdb-'+identifier);raw=out/'raw';raw.mkdir();log=[]
    entry=json_request(f'{RCSB}/entry/{identifier}',raw,'entry',log)
    cif_data,record=fetch(f'https://files.rcsb.org/download/{identifier}.cif');cif=out/(identifier+'.cif');cif.write_bytes(cif_data);record['raw_file']=str(cif);log.append(record)
    structure=gemmi.read_structure(str(cif));chains=[]
    if not len(structure):raise ValueError('Downloaded mmCIF contains no coordinate model.')
    for chain in structure[0]:
        residues=[]
        for residue in chain.get_polymer():
            info=gemmi.find_tabulated_residue(residue.name)
            if info.is_amino_acid():
                residues.append({'pdb_seqnum':residue.seqid.num,'insertion_code':residue.seqid.icode.strip(' \x00'),
                                 'resname':residue.name,'one_letter':info.one_letter_code.upper()})
        if residues:chains.append({'author_chain_id':chain.name,'resolved_amino_acid_count':len(residues),'residues':residues})
    pdb=None;issues=[]
    try:
        data,record=fetch(f'https://files.rcsb.org/download/{identifier}.pdb');pdb=out/(identifier+'.pdb');pdb.write_bytes(data);record['raw_file']=str(pdb);log.append(record)
        parsed=gemmi.read_pdb(str(pdb))
        if not len(parsed) or sum(len(c) for c in parsed[0])==0:raise ValueError('Legacy PDB response has no atoms.')
        # Compare the author numbering, residue identities and all atomic coordinates with the authoritative mmCIF.
        def atoms(s):
            return sorted([(c.name,r.seqid.num,r.seqid.icode.strip(' \x00'),r.name,a.name,a.altloc,a.pos.x,a.pos.y,a.pos.z) for c in s[0] for r in c for a in r],key=lambda x:x[:6])
        a,b=atoms(structure),atoms(parsed)
        if len(a)!=len(b) or any(x[:6]!=y[:6] or max(abs(u-v) for u,v in zip(x[6:],y[6:]))>0.0011 for x,y in zip(a,b)):
            issues.append('Legacy PDB differs from mmCIF atom order/identifiers/coordinates; do not use without inspection.')
    except (RuntimeError,ValueError) as exc:
        issues.append(f'No verified legacy PDB for this entry: {exc}');pdb=None
    entities={}
    for entity_id in entry.get('rcsb_entry_container_identifiers',{}).get('polymer_entity_ids',[]):
        entities[entity_id]=json_request(f'{RCSB}/polymer_entity/{identifier}/{entity_id}',raw,'entity-'+entity_id,log)
    nonpolymers={}
    for entity_id in entry.get('rcsb_entry_container_identifiers',{}).get('non_polymer_entity_ids',[]):
        nonpolymers[entity_id]=json_request(f'{RCSB}/nonpolymer_entity/{identifier}/{entity_id}',raw,'nonpolymer-'+entity_id,log)
    for c in chains:
        if len(c['author_chain_id'])!=1:issues.append(f'Chain {c["author_chain_id"]!r} is unsupported by the current single-character PDB chain interface.')
    report={'pdb_id':identifier,'title':entry.get('struct',{}).get('title'),'model_count':len(structure),'coordinate_scope':'Deposited asymmetric unit; only first model summarized. Not an automatically reconstructed biological assembly.',
            'source_url':f'https://www.rcsb.org/structure/{identifier}','mmcif_path':str(cif),'pdb_path':str(pdb) if pdb else None,
            'legacy_pdb_matches_mmcif':pdb is not None and not any('differs' in i for i in issues),
            'chains':chains,'issues':issues,'polymer_entities':entities,'nonpolymer_entities':nonpolymers,
            'assembly_ids':entry.get('rcsb_entry_container_identifiers',{}).get('assembly_ids',[]),
            'primary_citation':entry.get('rcsb_primary_citation'),'requests':log}
    report_path=out/'structure.json';save_json(report_path,report);save_json(out/'requests.json',log)
    artifacts=[artifact(report_path,'Source, chain/residue metadata, ligands and coordinate integrity checks'),artifact(cif,'Authoritative original mmCIF'),artifact(out/'requests.json','Public endpoints and raw-response hashes')]
    if pdb:artifacts.append(artifact(pdb,'Original legacy PDB for downstream CB, subject to readiness checks'))
    return {'message':'Downloaded original experimental coordinates; select author chains and validate with CB.', 'reference':f'https://www.rcsb.org/structure/{identifier}',
            'artifacts':artifacts,'pdb_id':identifier,'pdb_path':str(pdb) if pdb else None,'mmcif_path':str(cif),
            'chain_ids':[c['author_chain_id'] for c in chains],'legacy_pdb_matches_mmcif':report['legacy_pdb_matches_mmcif'],'issues':issues,'metadata_path':str(report_path)}


def prepare_panel(reference_fasta_path, structure_pair_json_path, variants, output_dir=None):
    from Bio.Align import PairwiseAligner
    fasta=Path(reference_fasta_path).expanduser().resolve();pair_path=Path(structure_pair_json_path).expanduser().resolve()
    text=fasta.read_text().splitlines();headers=[l for l in text if l.startswith('>')]
    if len(headers)!=1:raise ValueError('reference_fasta_path must contain exactly one FASTA record.')
    sequence=''.join(l.strip() for l in text if l.strip() and not l.startswith('>'))
    if not sequence or set(sequence)-AA:raise ValueError('Reference must contain only the 20 uppercase canonical amino acids.')
    pair=json.loads(pair_path.read_text());consensus=pair['consensus_sequence']
    if not pair.get('scoring_ready'):raise ValueError('Structure pair is not scoring_ready; resolve its reported issues first.')
    if pair.get('reference_sequence') != sequence:
        raise ValueError('The FASTA must exactly match reference_sequence used for cb_prepare_structure_pair; prepare the pair again with this parental reference.')
    if not consensus or set(consensus)-AA:raise ValueError('CB consensus contains unresolved/noncanonical residues.')
    if not variants or len(set(variants))!=len(variants):raise ValueError('Provide a nonempty list of unique variant specifications.')
    if sequence==consensus: mapping={i:i for i in range(len(sequence))};mapping_method='identical reference and consensus'
    else:
        aligner=PairwiseAligner();aligner.mode='global';aligner.open_gap_score=-10;aligner.extend_gap_score=-0.5;aligner.match_score=2;aligner.mismatch_score=-0.5
        alignments=aligner.align(sequence,consensus);alignment=alignments[0]
        try:alignments[1]
        except IndexError:pass
        else:raise ValueError('Reference-to-consensus alignment has multiple optimal solutions; supply an unambiguous construct reference instead of guessing numbering.')
        mapping={}
        for (s1,e1),(s2,e2) in zip(*alignment.aligned):
            for i,j in zip(range(int(s1),int(e1)),range(int(s2),int(e2))):
                if sequence[i]==consensus[j]:mapping[i]=j
        mapping_method='unique global reference-to-consensus alignment; exact residue matches only'
    shared={x-1 for x in pair['shared_consensus_positions_one_based']};rows=[];edits=[]
    for specification in variants:
        if not isinstance(specification,str) or not specification.strip():raise ValueError('Each variant must be WT or explicit notation such as G166E or R71H/G230A.')
        label=specification.strip();mutations=[] if label.upper()=='WT' else re.split(r'[/,+;\s]+',label)
        mutated=list(consensus);seen=set();record=[]
        for mutation in mutations:
            match=re.fullmatch(r'([ACDEFGHIKLMNPQRSTVWY])([1-9][0-9]*)([ACDEFGHIKLMNPQRSTVWY])',mutation)
            if not match:raise ValueError(f'Unresolved mutation {mutation!r}; shorthand labels like HAQ require explicit substitutions.')
            old,position,new=match.group(1),int(match.group(2)),match.group(3)
            if position in seen:raise ValueError(f'Duplicate substitution at reference position {position}.')
            seen.add(position)
            if position>len(sequence) or sequence[position-1]!=old:raise ValueError(f'{mutation}: reference residue does not match the supplied FASTA.')
            index=mapping.get(position-1)
            if index is None or index not in shared:raise ValueError(f'{mutation}: position is not identically mapped and resolved in both conformations; no score can be produced for this edit.')
            if old==new:raise ValueError(f'{mutation} does not change a residue; use WT for a baseline.')
            mutated[index]=new;record.append({'mutation':mutation,'reference_position_one_based':position,'consensus_position_one_based':index+1})
        rows.append({'variant_id':label,'sequence':''.join(mutated)});edits.append({'variant_id':label,'substitutions':record})
    if len({r['variant_id'] for r in rows})!=len(rows):raise ValueError('Variant identifiers are duplicated after whitespace normalization.')
    if len({r['sequence'] for r in rows})!=len(rows):
        raise ValueError('Variant specifications produce duplicate sequences; include each sequence once to avoid reweighting panel-dependent CB normalization.')
    out=directory(output_dir,'cb-panel');csv_path=out/'variants.csv'
    with csv_path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['variant_id','sequence']);writer.writeheader();writer.writerows(rows)
    manifest={'reference_fasta_path':str(fasta),'reference_sha256':sha(fasta.read_bytes()),'reference_header':headers[0],
              'structure_pair_path':str(pair_path),'structure_pair_sha256':sha(pair_path.read_bytes()),'mapping_method':mapping_method,
              'numbering':'Substitutions use one-based positions in the supplied reference FASTA; CSV sequences use CB consensus coordinates.',
              'consensus_length':len(consensus),'variants':edits,'panel_sha256':sha(csv_path.read_bytes()),
              'limitations':['No mutant structure is generated or required. Each variant is scored on both chosen reference backbones.',
                             'Standardized CB bias is panel-dependent. A WT+one-mutant panel is too small for a population-calibrated ranking; inspect raw/WT-relative per-state scores.']}
    save_json(out/'panel.json',manifest)
    return {'message':'Built the full-sequence panel after checking reference residues and both-state coordinate coverage.',
            'reference':'https://github.com/alicetinglab/ConformationalBiasing','artifacts':[artifact(csv_path,'Full sequence CSV for cb_score_variant_panel'),artifact(out/'panel.json','Explicit mutation, numbering and input provenance')],
            'variants_path':str(csv_path),'variant_count':len(rows),'consensus_length':len(consensus)}
