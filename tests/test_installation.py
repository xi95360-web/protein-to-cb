import importlib.util
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import connections,toml_blocks
from install_codex import install

class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.cfg=self.root/'config.toml';self.skills=self.root/'skills';self.python=sys.executable
        self.cfg.write_text('# preserve comments\nmodel = "example"\n[mcp_servers.other]\ncommand = "unchanged"\n')
        self.original=self.cfg.read_bytes()

    def test_append_preserves_unrelated_settings_and_repeat_is_idempotent(self):
        with patch('install_codex.subprocess.run'):
            result=install(self.cfg,self.skills,self.python)
            before=tomllib.loads(self.original.decode());after=tomllib.loads(self.cfg.read_text())
            for name in ('pdbank','conformational_biasing'):after['mcp_servers'].pop(name)
            self.assertEqual(before,after);self.assertTrue(self.cfg.read_bytes().startswith(self.original))
            self.assertEqual(Path(result['backup']).read_bytes(),self.original)
            installed=self.cfg.read_bytes();again=install(self.cfg,self.skills,self.python)
            self.assertEqual(self.cfg.read_bytes(),installed);self.assertEqual(again['new_connections'],[])

    def test_conflicting_connection_preserved_before_any_install(self):
        self.cfg.write_text(self.cfg.read_text()+'\n[mcp_servers.pdbank]\ncommand = "other-server"\n');before=self.cfg.read_bytes()
        with self.assertRaisesRegex(ValueError,'managed elsewhere'):install(self.cfg,self.skills,self.python)
        self.assertEqual(before,self.cfg.read_bytes());self.assertFalse(self.skills.exists())

    def test_preview_makes_no_changes(self):
        result=install(self.cfg,self.skills,self.python,preview=True)
        self.assertTrue(result['preview']);self.assertEqual(self.cfg.read_bytes(),self.original);self.assertFalse(self.skills.exists())
        self.assertEqual(set(tomllib.loads(result['toml'])['mcp_servers']),{'pdbank','conformational_biasing'})

    def test_paths_with_spaces_and_unicode_roundtrip(self):
        entries=connections('/some path/环境/bin/python',self.root/'skill folder')
        parsed=tomllib.loads(toml_blocks(entries))['mcp_servers']
        self.assertEqual(parsed,entries)

if __name__=='__main__':unittest.main()

