import subprocess
import shutil
import tempfile
import unittest
from pathlib import Path
import engine

class EngineTests(unittest.TestCase):
    def test_segments(self):
        self.assertEqual(engine.segments(4, [0.1, 2, 2.1, 3.9]), [{"id":0,"start":0.0,"end":2},{"id":1,"start":2,"end":4}])
    def test_selection(self):
        clips = engine.segments(4, [2])
        self.assertEqual(engine.validate_selection([1], clips), [clips[1]])
        for ids in ([], [0,0], [True], [-1], [2], "0"):
            with self.assertRaises(ValueError):
                engine.validate_selection(ids, clips)
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
    def test_render_synthetic_media(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d)/"input.mp4", Path(d)/"output.mp4"
            engine.run(["ffmpeg","-nostdin","-y","-f","lavfi","-i","color=red:s=160x120:r=25:d=2","-f","lavfi","-i","color=blue:s=160x120:r=25:d=2","-filter_complex","[0:v][1:v]concat=n=2:v=1:a=0[v]","-map","[v]","-c:v","libx264","-pix_fmt","yuv420p",str(src)])
            info = engine.probe(src)
            clips = engine.analyze(src, info)
            self.assertEqual(len(clips), 2)
            engine.render(src, out, clips[1:], False)
            self.assertAlmostEqual(engine.probe(out)["duration"], 2, delta=.2)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
    def test_visuals_with_real_audio(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d)/"input.mp4"
            engine.run(["ffmpeg","-nostdin","-y","-f","lavfi","-i","color=red:s=160x120:r=25:d=2","-f","lavfi","-i","sine=frequency=440:sample_rate=8000:duration=2","-c:v","libx264","-c:a","aac","-shortest",str(src)])
            info = engine.probe(src)
            clips = engine.segments(info["duration"], [1])
            data = engine.build_visuals(src, Path(d)/"visuals", clips, info)
            self.assertEqual(len(data), 2)
            for item in data:
                self.assertGreater(max(item["peaks"]), 0)
                self.assertTrue(all(0 <= p <= 1 for p in item["peaks"]))
                self.assertTrue((Path(d)/"visuals"/f"{item['id']}.jpg").read_bytes().startswith(b"\xff\xd8"))

    def test_edit_validation(self):
        clips = engine.segments(4, [2])
        edits = {"1": {"start": 2.25, "end": 3.75, "effect": "mono"}}
        self.assertEqual(engine.validate_edits([1], clips, edits)[0], {"id":1,"start":2.25,"end":3.75,"effect":"mono"})
        for invalid in ({"1":{"start":1}}, {"1":{"end":5}}, {"1":{"effect":"movie=/etc/passwd"}}, {"1":{"start":True}}, {"1":{"start":float("nan")}}, {"2":{}}, {"1":{"start":3,"end":3.01}}):
            with self.assertRaises(ValueError):
                engine.validate_edits([1], clips, invalid)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
    def test_render_trim_and_effect(self):
        with tempfile.TemporaryDirectory() as d:
            src,out=Path(d)/"source.mp4",Path(d)/"output.mp4"
            engine.run(["ffmpeg","-nostdin","-y","-f","lavfi","-i","color=red:s=160x120:r=25:d=2","-f","lavfi","-i","sine=frequency=440:duration=2","-c:v","libx264","-c:a","aac","-shortest",str(src)])
            info=engine.probe(src)
            clips=engine.validate_edits([0],engine.segments(info["duration"],[]),{"0":{"start":.5,"end":1.5,"effect":"mono"}})
            engine.render(src,out,clips,True)
            self.assertAlmostEqual(engine.probe(out)["duration"],1,delta=.15)
            pixel=subprocess.run(["ffmpeg","-v","error","-i",str(out),"-frames:v","1","-vf","scale=1:1","-f","rawvideo","-pix_fmt","rgb24","-"],check=True,capture_output=True).stdout
            self.assertEqual(len(pixel),3)
            self.assertLessEqual(max(pixel)-min(pixel),4)

if __name__ == "__main__":
    unittest.main()
