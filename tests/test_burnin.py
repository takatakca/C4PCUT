import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import captions
import engine

class BurnTests(unittest.TestCase):
    def test_safe_ass(self):
        cue={"start":0,"end":1,"text":r"{\pos(0,0)} hello"}
        ass=captions.to_ass([cue],"karaoke")
        self.assertNotIn(r"{\pos",ass)
        self.assertIn(r"{\kf50}",ass)
        self.assertIn("0:00:01.00",ass)
        with self.assertRaises(ValueError):
            captions.validate_mode("arbitrary")
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg required")
    def test_burned_pixels_and_duration(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            src,out=root/"source.mp4",root/"output.mp4"
            engine.run(["ffmpeg","-nostdin","-y","-f","lavfi","-i","color=black:s=320x180:r=25:d=2","-c:v","libx264","-pix_fmt","yuv420p",str(src)])
            ass=captions.to_ass([{"start":.2,"end":1.5,"text":"TEST CAPTION"}],"bold")
            engine.render(src,out,[{"start":0,"end":2}],False,burn_ass=ass)
            frame=subprocess.run(["ffmpeg","-v","error","-ss","0.7","-i",str(out),"-frames:v","1","-f","rawvideo","-pix_fmt","gray","-threads","1","-"],capture_output=True)
            self.assertEqual(frame.returncode,0,frame.stderr.decode(errors="replace"))
            pixels=frame.stdout
            self.assertEqual(len(pixels),320*180)
            self.assertGreater(sum(x>180 for x in pixels),10)
            self.assertAlmostEqual(engine.probe(out)["duration"],2,delta=.15)
