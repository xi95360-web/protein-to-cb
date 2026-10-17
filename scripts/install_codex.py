"""Install chat skill and append two connections without rewriting unrelated TOML."""
import argparse
from datetime import datetime,timezone
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tomllib
from common import ROOT,connections,runtime_python,toml_blocks

def hashes(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}

def install(config,skills,python,preview=False):
    source=ROOT/'skills/protein-to-cb';dest=skills/'protein-to-cb'
    raw=config.read_bytes() if config.exists() else b''
    before=tomllib.loads(raw.decode());entries=connections(python,dest)
    present=before.get('mcp_servers',{});missing={}
    for name,entry in entries.items():
        if name in present and present[name]!=entry:
            raise ValueError(f'Existing {name} connection is managed elsewhere; it has been left unchanged. Keep using it, or review a migration before replacing it.')
        if name not in present:missing[name]=entry
    if dest.exists() and hashes(dest)!=hashes(source):
        raise ValueError('An existing protein-to-cb skill differs; it has been left unchanged. Review the update before replacing it.')
    new=raw+toml_blocks(missing).encode() if missing else raw
    parsed=tomllib.loads(new.decode());expected=dict(before);expected['mcp_servers']={**present,**entries}
    assert parsed==expected
    if preview:return {'preview':True,'config':str(config),'new_connections':list(missing),'toml':toml_blocks(missing)}
    subprocess.run([python,str(ROOT/'scripts/check_runtime.py')],check=True)
    if not dest.exists():
        skills.mkdir(parents=True,exist_ok=True)
        shutil.copytree(source,dest,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    backup=None
    if new!=raw:
        config.parent.mkdir(parents=True,exist_ok=True)
        if config.exists():
            backup=config.with_name(config.name+'.bak-protein-to-cb-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
            fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as stream:stream.write(raw)
        # Preserve existing mode; a new configuration is private by default.
        fd=os.open(config,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(new);stream.flush();os.fsync(stream.fileno())
    return {'installed':True,'config':str(config),'skill':str(dest),'backup':str(backup) if backup else None,'new_connections':list(missing)}

def main():
    p=argparse.ArgumentParser(description='Install for Codex; existing conflicting connections are preserved.')
    p.add_argument('--python');p.add_argument('--config',type=Path,default=Path.home()/'.codex/config.toml')
    p.add_argument('--skills-dir',type=Path,default=Path.home()/'.codex/skills');p.add_argument('--preview',action='store_true')
    args=p.parse_args()
    try:result=install(args.config.expanduser().absolute(),args.skills_dir.expanduser().absolute(),runtime_python(args.python),args.preview)
    except ValueError as exc:raise SystemExit(str(exc))
    import json
    print(json.dumps(result,indent=2))
    if not args.preview:print('Restart the MCP connections/Codex to load the skill and tools.')

if __name__=='__main__':main()

