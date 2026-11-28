import tempfile
import unittest
from pathlib import Path
import projects

class MediaManagementTests(unittest.TestCase):
    def test_inventory_removal_preserves_saved_revision(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            (folder/"source.media").write_bytes(b"source")
            (folder/"logo.png").write_bytes(b"logo")
            (folder/"music.wav").write_bytes(b"music")
            job={"folder":folder,"metadata":{"duration":2},"clips":[],"music_analysis":{"beats":[]}}
            projects.save(job,{"name":"Media"})
            before=projects.read(folder)
            self.assertEqual({x["kind"]:x["bytes"] for x in projects.media_inventory(job)},{"music":5,"logo":4})
            projects.remove_media(job,"music")
            projects.remove_media(job,"logo")
            self.assertNotIn("music_analysis",job)
            self.assertEqual(projects.media_inventory(job),[])
            self.assertEqual(projects.read(folder),before)
            self.assertTrue((folder/"source.media").is_file())
            projects.save(job,{"name":"Media"})
            after=projects.read(folder)
            self.assertIsNone(after["music_revision"])
            self.assertIsNone(after["logo_revision"])
            self.assertFalse(list(folder.glob("saved-*.wav")))
            self.assertFalse(list(folder.glob("saved-logo-*.png")))
    def test_reject_unknown_media_and_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            source=folder/"source.media";source.write_bytes(b"source")
            (folder/"logo.png").symlink_to(source)
            job={"folder":folder}
            self.assertEqual(projects.media_inventory(job),[])
            for kind in ("source","../source.media",None,"logo"):
                with self.assertRaises(ValueError):projects.remove_media(job,kind)
            self.assertEqual(source.read_bytes(),b"source")
