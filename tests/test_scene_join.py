import unittest
import engine
import projects

class SceneJoinTests(unittest.TestCase):
    def test_join_split_roundtrip_preserves_order_and_duration(self):
        clips=engine.segments(6,[2,4])
        edits={"0":{"start":.2,"end":1.8,"effect":"warm"},"1":{"start":2.2,"end":3.8,"effect":"mono"}}
        split=engine.split_scene(clips,[0,2],edits,[2,0],0,1)
        joined=engine.join_scenes(split["clips"],split["selected"],split["edits"],split["order"],0)
        self.assertEqual(joined["clips"],clips)
        self.assertEqual(joined["order"],[2,0])
        self.assertEqual(joined["edits"],edits)
        self.assertEqual(joined["current"],0)
        projects.validate_segments(joined["clips"],6)
        before=engine.validate_edits([0,2],clips,edits,[2,0])
        after=engine.validate_edits(joined["selected"],joined["clips"],joined["edits"],joined["order"])
        self.assertEqual(before,after)
    def test_reject_gap_mismatched_effect_unselected_and_reordered(self):
        clips=engine.segments(4,[2])
        for ids,edits,order,scene in [
            ([0,1],{"0":{"end":1.8}},[0,1],0),
            ([0,1],{"0":{"effect":"warm"}},[0,1],0),
            ([0],{},[0],0),
            ([0,1],{},[1,0],0),
            ([0,1],{},[0,1],True),
        ]:
            with self.assertRaises(ValueError):engine.join_scenes(clips,ids,edits,order,scene)
        self.assertEqual(clips,engine.segments(4,[2]))
    def test_merge_outer_trims(self):
        clips=engine.segments(4,[2])
        joined=engine.join_scenes(clips,[0,1],{"0":{"start":.3},"1":{"end":3.6}},[0,1],0)
        self.assertEqual(joined["clips"],engine.segments(4,[]))
        self.assertEqual(joined["edits"]["0"],{"start":.3,"end":3.6,"effect":"none"})
