import unittest
import tempfile
import shutil
from pathlib import Path
import engine
import clipper
import captions

class ClipperTests(unittest.TestCase):
    def test_distinct_bounded_suggestions(self):
        scenes=engine.segments(180,list(range(10,180,10)))
        cues=[{"start":30,"end":50,"text":"Speech"}]
        beats=[x/2 for x in range(60,100)]
        result=clipper.suggest(180,scenes,cues,beats,15,10,"cinematic")
        self.assertEqual(len(result),10)
        for c in result:
            self.assertGreaterEqual(c["start"],0)
            self.assertLessEqual(c["end"],180)
            self.assertAlmostEqual(c["duration"],15)
            self.assertEqual(c["effect"],"warm")
        for i,a in enumerate(result):
            for b in result[i+1:]:
                self.assertLessEqual(max(0,min(a["end"],b["end"])-max(a["start"],b["start"])),15*.65+1e-8)
        self.assertTrue(result[0]["start"]<=35)
        self.assertGreater(result[0]["score"],0)
    def test_short_and_invalid(self):
        scenes=engine.segments(5,[2])
        result=clipper.suggest(5,scenes,[],[],60,10,"clean")
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["duration"],5)
        self.assertEqual(clipper.ranges(result[0],scenes),[{"start":0,"end":2,"effect":"none"},{"start":2,"end":5,"effect":"none"}])
        for target,count,style in [(1,2,"clean"),(15,11,"clean"),(15,True,"clean"),(15,1,"unsafe")]:
            with self.assertRaises(ValueError):
                clipper.suggest(5,scenes,[],[],target,count,style)
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg required")
    def test_clip_render_and_caption_mapping(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);src=root/"source.mp4";out=root/"clip.mp4"
            engine.run(["ffmpeg","-nostdin","-y","-f","lavfi","-i","color=blue:s=160x120:r=25:d=4","-c:v","libx264","-pix_fmt","yuv420p",str(src)])
            candidate={"start":1,"end":3,"effect":"contrast"}
            ranges=clipper.ranges(candidate,engine.segments(4,[2]))
            mapped=captions.remap([{"start":1.5,"end":2.5,"text":"hello"}],ranges)
            self.assertAlmostEqual(mapped[0]["start"],.5)
            self.assertAlmostEqual(mapped[-1]["end"],1.5)
            engine.render(src,out,ranges,False)
            self.assertAlmostEqual(engine.probe(out)["duration"],2,delta=.15)
