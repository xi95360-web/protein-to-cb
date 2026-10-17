"""Create a local runtime, or reuse one explicitly supplied by the user."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from common import ROOT

def main():
    p=argparse.ArgumentParser(description='Prepare Protein to CB. Does not modify Codex settings.')
    p.add_argument('--reuse-python',help='Reuse an existing compatible Python; never install into that environment.')
    args=p.parse_args()
    if args.reuse_python:
        python=str(Path(args.reuse_python).expanduser().absolute())
    else:
        if sys.version_info[:2]!=(3,12):raise SystemExit('Use Python 3.12 to run setup, or supply --reuse-python.')
        python=str(ROOT/'.venv/bin/python')
        if not Path(python).is_file():subprocess.run([sys.executable,'-m','venv',str(ROOT/'.venv')],check=True)
        subprocess.run([python,'-m','pip','install','-r','src/requirements.txt'],cwd=ROOT/'backend',check=True)
        subprocess.run([python,'-m','pip','check'],check=True)
    subprocess.run([python,str(ROOT/'scripts/check_runtime.py')],check=True)
    (ROOT/'.runtime.json').write_text(json.dumps({'python':python},indent=2)+'\n')
    print('Runtime is ready. Next: python scripts/install_codex.py')

if __name__=='__main__':main()

