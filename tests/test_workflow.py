import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pdb_workflow', ROOT/'skills/protein-to-cb/scripts/pdb_workflow.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        self.fasta = self.out/'parent.fasta'
        self.fasta.write_text('>parent\nACDEFGHIK\n')
        self.pair = self.out/'structure_pair.json'
        self.set_pair()

    def set_pair(self, **overrides):
        d = dict(reference_sequence='ACDEFGHIK', consensus_sequence='ACDEFGHIK', scoring_ready=True,
                 shared_consensus_positions_one_based=list(range(2,10)))
        d.update(overrides)
        self.pair.write_text(json.dumps(d))

    def panel(self, variants):
        return w.prepare_panel(str(self.fasta),str(self.pair),variants,str(self.out))

    def test_panel_without_mutant_pdb(self):
        r = self.panel(['WT','G6E','C2S/G6E'])
        rows = list(csv.DictReader(Path(r['variants_path']).read_text().splitlines()))
        self.assertEqual([x['sequence'] for x in rows], ['ACDEFGHIK','ACDEFEHIK','ASDEFEHIK'])
        manifest = json.loads((Path(r['variants_path']).parent/'panel.json').read_text())
        self.assertEqual(manifest['panel_sha256'], w.sha(Path(r['variants_path']).read_bytes()))

    def test_construct_extension_remaps_numbering(self):
        self.set_pair(consensus_sequence='MACDEFGHIK', shared_consensus_positions_one_based=list(range(2,11)))
        r = self.panel(['WT','G6E'])
        rows = list(csv.DictReader(Path(r['variants_path']).read_text().splitlines()))
        self.assertEqual(rows[1]['sequence'], 'MACDEFEHIK')
        manifest = json.loads((Path(r['variants_path']).parent/'panel.json').read_text())
        self.assertEqual(manifest['variants'][1]['substitutions'][0]['consensus_position_one_based'],7)

    def test_missing_edited_backbone(self):
        with self.assertRaisesRegex(ValueError,'both conformations'): self.panel(['WT','A1E'])

    def test_wrong_parent_residue(self):
        with self.assertRaisesRegex(ValueError,'does not match'): self.panel(['WT','A6E'])

    def test_unready_pair(self):
        self.set_pair(scoring_ready=False)
        with self.assertRaisesRegex(ValueError,'not scoring_ready'): self.panel(['WT'])

    def test_wrong_reference_background(self):
        self.set_pair(reference_sequence='VCDEFGHIK')
        with self.assertRaisesRegex(ValueError,'exactly match reference_sequence'): self.panel(['WT','G6E'])

    def test_shorthand_noop_and_conflicting_site_rejected(self):
        for v in ['HAQ','G6G','G6E/G6A','G600E']:
            with self.subTest(v=v), self.assertRaises(ValueError): self.panel(['WT',v])

    def test_duplicate_sequences_rejected(self):
        for variants in [['WT','wt'],['WT',' WT '],['C2S/G6E','G6E+C2S']]:
            with self.subTest(variants=variants), self.assertRaises(ValueError): self.panel(variants)

    def test_ambiguous_numbering_rejected(self):
        self.fasta.write_text('>repeat\nAAAA\n')
        self.set_pair(reference_sequence='AAAA',consensus_sequence='AAAAA',shared_consensus_positions_one_based=list(range(1,6)))
        with self.assertRaisesRegex(ValueError,'multiple optimal'): self.panel(['WT','A2E'])

    def test_input_ids_cannot_be_urls_or_paths(self):
        for v in ['https://example.com/6NT5','../6NT5','0ABC','6NT55']:
            with self.subTest(v=v), self.assertRaises(ValueError):w.pdb_id(v)
        self.assertEqual(w.pdb_id('6nt5'),'6NT5')

    def test_exact_gene_alias_over_partial_name(self):
        data=json.loads((ROOT/'tests/fixtures/uniprot-sting.json').read_text())['results']
        matches=[x['primaryAccession'] for x in data if w.exact_alias(x,'STING')]
        self.assertEqual(matches,['Q86WV6'])

    def test_background_reports_allele_despite_zero_mutation_metadata(self):
        r=w.sequence_background('ACDEFGHIK','MACDEFAHIK')
        self.assertTrue(r['alignment_is_unique'])
        self.assertEqual(r['substitutions'],[{'reference_position_one_based':6,'reference_residue':'G','entity_residue':'A'}])
        self.assertEqual(r['entity_unaligned_residue_count'],1)

    def test_truncated_identity_search_does_not_autoresolve(self):
        protein=json.loads((ROOT/'tests/fixtures/uniprot-sting.json').read_text())['results'][0]
        def response(url,out,name,log,payload=None):
            log.append({'headers':{'X-Total-Results':'26'}})
            return {'results':[protein]}
        with patch.object(w,'json_request',side_effect=response):
            r=w.search_protein('STING',9606,output_dir=str(self.out))
        self.assertEqual(r['status'],'identity_resolution_required')
        self.assertIsNone(r['reference_fasta_path'])

    def test_empty_http_response_raw_bytes_preserved(self):
        log=[]
        with patch.object(w,'fetch',return_value=(b'',{'status':204})):
            result=w.json_request('https://search.rcsb.org/',self.out,'empty',log)
        self.assertEqual(result,{'total_count':0,'result_set':[]})
        self.assertEqual((self.out/'empty.json').read_bytes(),b'')
        self.assertTrue(log[0]['empty_http_response'])

    def test_outage_not_represented_as_no_structures(self):
        with patch.object(w,'fetch',side_effect=RuntimeError('HTTP 503')):
            with self.assertRaisesRegex(RuntimeError,'503'):w.search_protein('STING',9606,output_dir=str(self.out))


if __name__ == '__main__':unittest.main()
