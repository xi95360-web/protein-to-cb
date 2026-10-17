from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]

def runtime_python(explicit=None):
    # Do not resolve interpreter symlinks: doing so can escape a virtual environment.
    if explicit:return str(Path(explicit).expanduser().absolute())
    saved=ROOT/'.runtime.json'
    if saved.exists():return json.loads(saved.read_text())['python']
    candidate=ROOT/'.venv/bin/python'
    if candidate.is_file():return str(candidate)
    raise SystemExit('Run scripts/setup.py first, or supply --python /absolute/path/to/python.')

def connections(python,skill_dir):
    env={'JAX_PLATFORMS':'cpu','XLA_PYTHON_CLIENT_PREALLOCATE':'false',
         'MPLCONFIGDIR':str(ROOT/'runs/cache/matplotlib'),'XDG_CACHE_HOME':str(ROOT/'runs/cache')}
    return {
      'pdbank':{'command':python,'args':[str(skill_dir/'scripts/pdbank_mcp.py')],'cwd':str(skill_dir),'enabled':True,
                'startup_timeout_sec':60,'tool_timeout_sec':900,
                'enabled_tools':['pdb_find_protein_structures','pdb_fetch_structure','cb_build_variant_panel']},
      'conformational_biasing':{'command':python,'args':[str(ROOT/'backend/src/ConformationalBiasing_mcp.py')],
                'cwd':str(ROOT/'backend'),'enabled':True,'startup_timeout_sec':60,'tool_timeout_sec':900,
                'enabled_tools':['cb_prepare_structure_pair','cb_score_variant_panel'],'env':env}}

def toml_blocks(entries):
    lines=[]
    for name,values in entries.items():
        lines.append(f'\n[mcp_servers.{name}]')
        for key,value in values.items():
            if key!='env':lines.append(f'{key} = {json.dumps(value)}')
        if values.get('env'):
            lines.append(f'\n[mcp_servers.{name}.env]')
            lines.extend(f'{key} = {json.dumps(value)}' for key,value in values['env'].items())
    return '\n'.join(lines)+'\n'

