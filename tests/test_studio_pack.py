import unittest
import tempfile
from pathlib import Path
import studio_pack
import projects

def pack():
    return {"studio":"TAKATAKSTUDIO","version":1,"kind":"production_request_pack",
            "project":{"title":"BANDIDO","brief":"Create a promotional clip","audience":"Music fans","language":"French","clientId":"other"},
            "characters":[{"name":"Artist","profile":"","secret":"discard"}],
            "jobs":[{"command":"never run"}],"billing":{"approved":True},"workspaceId":"other"}

class StudioPackTests(unittest.TestCase):
    def test_whitelist(self):
        brief=studio_pack.parse_pack(pack())
        self.assertEqual(set(brief),{"title","brief","audience","language","characters"})
        self.assertEqual(brief["language"],"fr")
        self.assertEqual(brief["characters"],[{"name":"Artist","profile":""}])
        prompt=studio_pack.director_prompt(brief)
        self.assertIn("BANDIDO",prompt)
        self.assertNotIn("never run",prompt)
        self.assertNotIn("other",prompt)
    def test_invalid(self):
        for bad in [None,{},{"version":True},[]]:
            with self.assertRaises(ValueError):
                studio_pack.parse_pack(bad)
        p=pack();p["project"]["brief"]="x"*1001
        with self.assertRaises(ValueError):studio_pack.parse_pack(p)
        p=pack();p["characters"][0]["profile"]="   "
        with self.assertRaises(ValueError):studio_pack.parse_pack(p)
        p=pack();p["characters"]*=2
        with self.assertRaises(ValueError):studio_pack.parse_pack(p)
    def test_saved_project_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);(folder/"source.media").write_bytes(b"source")
            job={"folder":folder,"metadata":{"duration":4,"width":160,"height":120,"audio":False}}
            brief=studio_pack.parse_pack(pack())
            saved=projects.save(job,{"name":"BANDIDO","studio_brief":brief})
            self.assertEqual(projects.read(folder)["state"]["studio_brief"],brief)
            self.assertEqual(saved["studio_brief"],brief)
            self.assertIsNone(projects.save(job,{"name":"BANDIDO"})["studio_brief"])
