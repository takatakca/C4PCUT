import tempfile
import unittest
from pathlib import Path
import engine
import projects
import captions

class SceneSplitTests(unittest.TestCase):
    def test_split_reordered_trimmed_scene_and_keep_other_edits(self):
        clips=engine.segments(6,[2,4])
        edits={"0":{"start":.2,"end":1.8,"effect":"warm"},"1":{"start":2.2,"end":3.8,"effect":"mono"},"2":{"start":4.1,"end":5.9,"effect":"contrast"}}
        before=engine.validate_edits([0,2],clips,edits,[2,0])
        result=engine.split_scene(clips,[0,2],edits,[2,0],0,1)
        self.assertEqual(result["order"],[3,0,1])
        self.assertEqual(result["selected"],[0,1,3])
        self.assertEqual(result["current"],1)
        self.assertEqual(result["edits"]["0"],{"start":.2,"end":1,"effect":"warm"})
        self.assertEqual(result["edits"]["1"],{"start":1,"end":1.8,"effect":"warm"})
        self.assertEqual(result["edits"]["2"],edits["1"])
        self.assertEqual(result["edits"]["3"],edits["2"])
        projects.validate_segments(result["clips"],6)
        after=engine.validate_edits(result["selected"],result["clips"],result["edits"],result["order"])
        self.assertAlmostEqual(sum(c["end"]-c["start"] for c in before),sum(c["end"]-c["start"] for c in after))
        # Splitting can divide caption cues, but their total retained coverage is unchanged.
        cues=[{"start":.5,"end":1.5,"text":"hello"}]
        self.assertAlmostEqual(sum(c["end"]-c["start"] for c in captions.remap(cues,before)),sum(c["end"]-c["start"] for c in captions.remap(cues,after)))
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);(folder/"source.media").write_bytes(b"source")
            job={"folder":folder,"metadata":{"duration":6},"clips":result["clips"]}
            projects.save(job,{"name":"Split","selected":result["selected"],"order":result["order"],"edits":result["edits"]})
            data=projects.read(folder)
            self.assertEqual(data["clips"],result["clips"])
            self.assertEqual(data["state"]["order"],result["order"])
    def test_invalid_split_is_rejected_without_mutating_input(self):
        clips=engine.segments(4,[2]);edits={"0":{"start":.5,"end":1.5}}
        for scene,at in [(0,.5),(0,.55),(0,1.45),(1,3),(True,1),(0,float("nan")),(0,"1")]:
            with self.assertRaises(ValueError):engine.split_scene(clips,[0],edits,[0],scene,at)
        self.assertEqual(clips,engine.segments(4,[2]))
        self.assertEqual(edits,{"0":{"start":.5,"end":1.5}})
        full=engine.segments(60,list(range(1,60)))
        with self.assertRaises(ValueError):engine.split_scene(full,[0],{},[0],0,.5)
