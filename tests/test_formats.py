import shutil
import tempfile
import unittest
from pathlib import Path
import engine

class FormatTests(unittest.TestCase):
    def test_allowlist(self):
        self.assertEqual(engine.validate_format("vertical_hd","crop"),(1080,1920))
        self.assertIsNone(engine.validate_format("original","fit"))
        for p,m in [("arbitrary","fit"),("vertical","bad"),([], "fit")]:
            with self.assertRaises(ValueError):
                engine.validate_format(p,m)
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg required")
    def test_fit_and_crop(self):
        with tempfile.TemporaryDirectory() as d:
            src,out=Path(d)/"source.mp4",Path(d)/"out.mp4"
            engine.run(["ffmpeg","-nostdin","-y","-f","lavfi","-i","color=red:s=160x120:r=25:d=1","-c:v","libx264","-pix_fmt","yuv420p",str(src)])
            for preset,framing,dims in [("vertical","fit",(720,1280)),("square","crop",(720,720)),("landscape","fit",(1280,720))]:
                engine.render(src,out,[{"start":0,"end":1}],False,preset=preset,framing=framing)
                info=engine.probe(out)
                self.assertEqual((info["width"],info["height"]),dims)
                self.assertAlmostEqual(info["duration"],1,delta=.15)
