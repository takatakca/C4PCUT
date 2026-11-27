import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import engine
import projects
import transitions

class TransitionTests(unittest.TestCase):
    def test_validation_and_short_boundaries(self):
        clips=engine.segments(2,[.4])
        s=transitions.validate({"mode":"dip_white","seconds":2})
        self.assertAlmostEqual(transitions.halves(clips,s)[0],.4/3)
        self.assertEqual(transitions.filter_for(0,clips[0],transitions.halves(clips,s),s).count("fade="),1)
        self.assertEqual(transitions.validate(None)["mode"],"cut")
        for bad in ({"mode":"custom","seconds":.5},{"mode":"dip_black","seconds":True},{"mode":"dip_white","seconds":3}):
            with self.assertRaises(ValueError):transitions.validate(bad)
    def test_project_state(self):
        clips=engine.segments(2,[1]);meta={"duration":2}
        s={"mode":"dip_white","seconds":.6}
        self.assertEqual(projects.validate_state({"name":"x","selected":[0,1],"transition":s},clips,meta,False)["transition"],s)
        self.assertEqual(projects.validate_state({"name":"old"},clips,meta,False)["transition"]["mode"],"cut")
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg required")
    def test_real_white_and_black_dips_preserve_duration_and_audio(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"source.mp4"
            engine.run(["ffmpeg","-v","error","-y","-f","lavfi","-i","color=red:s=160x120:r=30:d=2","-f","lavfi","-i","sine=frequency=440:duration=2","-c:v","libx264","-c:a","aac","-shortest","-pix_fmt","yuv420p",str(src)])
            clips=engine.segments(2,[1])
            for mode in ("dip_white","dip_black"):
                out=Path(d)/(mode+".mp4")
                engine.render(src,out,clips,True,transition={"mode":mode,"seconds":.6})
                meta=engine.probe(out)
                self.assertAlmostEqual(meta["duration"],2,delta=.15)
                self.assertTrue(meta["audio"])
                def pixel(at):
                    return subprocess.run(["ffmpeg","-v","error","-ss",str(at),"-i",str(out),"-frames:v","1","-vf","scale=1:1","-f","rawvideo","-pix_fmt","rgb24","-"],check=True,capture_output=True).stdout
                self.assertGreater(pixel(.3)[0],180)
                if mode=="dip_white":self.assertGreater(min(pixel(1.0)),190)
                else:self.assertLess(max(pixel(1.0)),40)
                self.assertGreater(pixel(1.7)[0],180)
