import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import projects
import engine

class ProjectTests(unittest.TestCase):
    def test_roundtrip_and_saved_music_isolation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/("a"*32);folder.mkdir()
            (folder/"source.media").write_bytes(b"source")
            (folder/"music.wav").write_bytes(b"saved track")
            meta={"duration":4,"width":160,"height":120,"audio":True}
            clips=engine.segments(4,[2])
            job={"folder":folder,"metadata":meta,"clips":clips}
            state=projects.save(job,{"name":"Music edit","selected":[1],"edits":{"1":{"start":2.2,"end":4,"effect":"warm"}},"use_music":True,"preset":"vertical"})
            (folder/"music.wav").write_bytes(b"unsaved track")
            self.assertEqual(projects.list_saved(root)[0]["name"],"Music edit")
            with patch("projects.music.analyze",return_value={"beats":[],"peaks":[],"estimated_bpm":None}):
                restored,saved=projects.restore(folder)
            self.assertEqual(saved,state)
            self.assertEqual(restored["clips"],clips)
            self.assertEqual((folder/"music.wav").read_bytes(),b"saved track")
            with self.assertRaises(ValueError):
                projects.save(job,{"name":"bad","selected":[99]})
            self.assertEqual(projects.read(folder)["state"],state)
    def test_scene_order_roundtrip_and_legacy_default(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);(folder/"source.media").write_bytes(b"source")
            meta={"duration":4,"width":160,"height":120,"audio":False}
            clips=engine.segments(4,[2]);job={"folder":folder,"metadata":meta,"clips":clips}
            projects.save(job,{"name":"Reordered","selected":[0,1],"order":[1,0]})
            self.assertEqual(projects.read(folder)["state"]["order"],[1,0])
            self.assertEqual(projects.validate_state({"name":"legacy","selected":[1,0]},clips,meta,False)["order"],[0,1])
            with self.assertRaises(ValueError):projects.save(job,{"name":"invalid","selected":[0,1],"order":[1,1]})
            self.assertEqual(projects.read(folder)["state"]["order"],[1,0])
    def test_empty_selection_and_invalid_state(self):
        meta={"duration":4}
        clips=engine.segments(4,[2])
        self.assertEqual(projects.validate_state({"name":"empty","selected":[]},clips,meta,False)["selected"],[])
        for payload in [{"name":"x","selected":[],"edits":{"1":{"effect":"bad"}}},{"name":"x","use_music":True},{"name":"x","preset":"bad"}]:
            with self.assertRaises(ValueError):
                projects.validate_state(payload,clips,meta,False)
        with self.assertRaises(ValueError):
            projects.validate_segments([{"id":0,"start":1,"end":4}],4)
