"""Check installed dependencies, pinned scientific artifacts and both real stdio servers."""
import argparse
import asyncio
import csv
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import sys
from common import ROOT,connections

os.environ.setdefault('JAX_PLATFORMS','cpu')
os.environ.setdefault('XLA_PYTHON_CLIENT_PREALLOCATE','false')
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'runs/cache/matplotlib'))
os.environ.setdefault('XDG_CACHE_HOME',str(ROOT/'runs/cache'))

def check_pins():
    if sys.version_info[:2]!=(3,12):raise RuntimeError('The validated runtime requires Python 3.12.')
    import colabdesign
    pins={'fastmcp':'4.0.3','biopython':'1.85','gemmi':'0.7.3','colabdesign':'1.1.1','jax':'0.8.0','numpy':'2.3.3','pandas':'2.3.3'}
    for package,version in pins.items():
        if metadata.version(package)!=version:raise RuntimeError(f'{package}: expected {version}, found {metadata.version(package)}')
    source=json.loads((ROOT/'backend/SOURCE_PROVENANCE.json').read_text())
    paths=[(ROOT/'backend'/source['cb']['included_source'],source['cb']['source_sha256']),
           (ROOT/'backend'/source['colabdesign']['wheel'],source['colabdesign']['sha256']),
           (Path(colabdesign.__file__).parent/'mpnn/weights/v_48_020.pkl',source['proteinmpnn_checkpoint']['sha256'])]
    for path,wanted in paths:
        if hashlib.sha256(path.read_bytes()).hexdigest()!=wanted:raise RuntimeError(f'Pinned artifact mismatch: {path.name}')
    return pins

async def check(score=False,network=False):
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport
    entries=connections(sys.executable,ROOT/'skills/protein-to-cb');out=ROOT/'runs/doctor';out.mkdir(parents=True,exist_ok=True)
    result={'versions':check_pins(),'servers':{},'score_check':None,'network_check':None}
    for name,entry in entries.items():
        env={**os.environ,**entry.get('env',{})}
        with (out/(name+'.log')).open('w') as log:
            transport=StdioTransport(command=entry['command'],args=entry['args'],cwd=entry['cwd'],env=env,log_file=log)
            async with Client(transport,timeout=900,init_timeout=60) as client:
                names=sorted(t.name for t in await client.list_tools());assert names==sorted(entry['enabled_tools'])
                result['servers'][name]=names
                if name=='pdbank' and network:
                    r=(await client.call_tool('pdb_find_protein_structures',{'protein_name':'HBA1','taxonomy_id':9606,'max_structures':1,'output_dir':str(out)})).data
                    assert r['resolved_accession']=='P69905' and r['status']=='structures_found';result['network_check']=r
                if name=='conformational_biasing' and score:
                    r=(await client.call_tool('cb_score_variant_panel',{'state1_pdb_path':str(ROOT/'tests/fixtures/3a7r.pdb'),'state1_chain':'A',
                        'state2_pdb_path':str(ROOT/'tests/fixtures/1x2g.pdb'),'state2_chain':'A','variants_path':str(ROOT/'tests/fixtures/panel.csv'),'output_dir':str(out),'seed':0})).data
                    scored=next(Path(x['path']) for x in r['artifacts'] if x['path'].endswith('variant_scores.csv'))
                    actual=list(csv.DictReader(scored.read_text().splitlines()));golden=list(csv.DictReader((ROOT/'tests/fixtures/expected-scores.csv').read_text().splitlines()))
                    assert len(actual)==len(golden)
                    for got,want in zip(actual,golden):
                        assert got.keys()==want.keys() and got['variant_id']==want['variant_id'] and got['sequence']==want['sequence']
                        for key in got.keys()-{'variant_id','sequence'}:
                            assert abs(float(got[key])-float(want[key]))<=1e-7,(key,got[key],want[key])
                    result['score_check']={'passed':True,'all_numeric_columns_match':True,'variant_count':len(actual),'result':r}
    result['success']=True;(out/'checks.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description='Check runtime; --score runs a real checkpoint; --network queries public RCSB/UniProt.')
    p.add_argument('--score',action='store_true');p.add_argument('--network',action='store_true');a=p.parse_args()
    print(json.dumps(asyncio.run(check(a.score,a.network)),indent=2))

