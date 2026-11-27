import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import engine
import logos
import projects

class LogoTests(unittest.TestCase):
    def test_settings(self):
        self.assertFalse(logos.validate(None,False)["enabled"])
        for value in ({"enabled":True,"position":"top_right"},{"enabled":False,"position":"bad"}):
            with self.assertRaises(ValueError):logos.validate(value,False)
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg required")
    def test_normalization_export_and_saved_revision(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);raw=folder/"raw.png";logo=folder/"logo.png";src=folder/"source.media";out=folder/"out.mp4"
            engine.run(["ffmpeg","-v","error","-y","-f","lavfi","-i","color=red:s=64x64","-frames:v","1","-threads","1",str(raw)])
            logos.normalize(raw,logo)
            self.assertEqual(logos.dimensions(logo),(64,64))
            engine.run(["ffmpeg","-v","error","-y","-f","lavfi","-i","color=black:s=320x180:r=25:d=2","-c:v","libx264","-pix_fmt","yuv420p","-f","mp4",str(src)])
            meta=engine.probe(src);clips=engine.segments(meta["duration"],[])
            settings={"enabled":True,"position":"top_right"}
            projects.save({"folder":folder,"metadata":meta,"clips":clips},{"name":"Logo","selected":[0],"logo":settings})
            original=logo.read_bytes();logo.unlink()
            _,state=projects.restore(folder)
            self.assertEqual(state["logo"],{**settings,"size":20,"opacity":1,"start":0,"end":None});self.assertEqual(logo.read_bytes(),original)
            engine.render(src,out,clips,False,logo_path=logo,logo_position="top_right")
            self.assertAlmostEqual(engine.probe(out)["duration"],2,delta=.15)
            frame=subprocess.run(["ffmpeg","-v","error","-ss","0.5","-i",str(out),"-frames:v","1","-f","rawvideo","-pix_fmt","rgb24","-"],check=True,capture_output=True).stdout
            def pixel(x,y):return frame[(y*320+x)*3:(y*320+x)*3+3]
            self.assertGreater(pixel(290,25)[0],180)
            self.assertLess(max(pixel(10,25)),30)
            timed=folder/"timed.mp4"
            engine.render(src,timed,clips,False,logo_path=logo,logo_position="top_right",logo_size=30,logo_opacity=.5,logo_start=.5,logo_end=1.5)
            def timed_pixel(at):
                frame=subprocess.run(["ffmpeg","-v","error","-ss",str(at),"-i",str(timed),"-frames:v","1","-f","rawvideo","-pix_fmt","rgb24","-"],check=True,capture_output=True).stdout
                return frame[(25*320+280)*3]
            self.assertLess(timed_pixel(.2),30)
            self.assertGreater(timed_pixel(.8),70)
            self.assertLess(timed_pixel(.8),180)
            self.assertLess(timed_pixel(1.8),30)
            raw.write_bytes(b"not a PNG")
            with self.assertRaises(ValueError):logos.normalize(raw,folder/"invalid.png")
