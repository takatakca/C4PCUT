import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
spec=importlib.util.spec_from_file_location("manage_grants",ROOT/"integration/manage-grants.py")
admin=importlib.util.module_from_spec(spec)
spec.loader.exec_module(admin)
A="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
B="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

class PrivateGrantTests(unittest.TestCase):
    def test_grant_revoke_audit(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"grants.json"
            admin.change(p,A,"grant","pro",200,now=100)
            admin.change(p,A,"grant","standard",300,now=150)
            admin.change(p,A,"revoke",now=160)
            data=admin.read_registry(p)
            self.assertFalse(data["grants"][A]["active"])
            self.assertEqual(data["audit"][1]["before"]["plan"],"pro")
            self.assertEqual(len(data["audit"]),3)
            self.assertEqual(os.stat(p).st_mode & 0o777,0o600)
            before=p.read_bytes()
            for args in [(A,"grant","bad",200),(B,"grant","free",99),("../bad","revoke",None,None),(B,"revoke",None,None)]:
                with self.assertRaises(ValueError):admin.change(p,*args,now=100)
            self.assertEqual(p.read_bytes(),before)
    @unittest.skipUnless(shutil.which("node"),"Node required")
    def test_node_lookup_after_revocation(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"grants.json"
            admin.change(p,A,"grant","free",200,now=100)
            script="""import {lookupPrivateGrant} from './integration/grant-registry.mjs'; console.log(JSON.stringify(await lookupPrivateGrant(process.argv[1],process.argv[2],150)));"""
            def lookup(client):
                return json.loads(subprocess.run(["node","--input-type=module","-e",script,str(p),client],cwd=ROOT,check=True,text=True,capture_output=True,timeout=10).stdout)
            self.assertEqual(lookup(A)["plan"],"free")
            self.assertIsNone(lookup(B))
            admin.change(p,A,"revoke",now=140)
            self.assertIsNone(lookup(A))
            p.write_text("corrupt")
            self.assertIsNone(lookup(A))
