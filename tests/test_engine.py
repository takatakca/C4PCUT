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

if __name__ == "__main__":
    unittest.main()
