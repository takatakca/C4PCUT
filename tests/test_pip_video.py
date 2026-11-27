import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import engine
import pip_video

class PictureInPictureTests(unittest.TestCase):
    def test_validation(self):
        meta={"duration":2}
        settings={"enabled":True,"position":"bottom_right","size":30,"start":.5,"source_in":.2,"length":1}
        self.assertEqual(pip_video.validate(settings,meta),settings)
        for change in ({"size":60},{"position":"bad"},{"source_in":True},{"length":3},{"start":float("nan")},{"path":"/tmp/file"}):
            with self.assertRaises(ValueError):pip_video.validate({**settings,**change},meta)
        with self.assertRaises(ValueError):pip_video.validate(settings,None)
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg required")
    def test_normalized_pip_timed_render(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);src=root/"source.mp4";raw=root/"secondary.mp4";asset=root/"normalized.mp4";out=root/"output.mp4"
            engine.run(["ffmpeg","-v","error","-y","-f","lavfi","-i","color=black:s=320x180:r=25:d=3","-c:v","libx264","-pix_fmt","yuv420p",str(src)])
            engine.run(["ffmpeg","-v","error","-y","-f","lavfi","-i","color=red:s=160x120:r=25:d=2","-f","lavfi","-i","sine=frequency=880:duration=2","-c:v","libx264","-c:a","aac","-shortest","-pix_fmt","yuv420p",str(raw)])
            meta=pip_video.normalize(raw,asset)
            self.assertFalse(meta["audio"])
            self.assertLessEqual(max(meta["width"],meta["height"]),720)
            settings={"enabled":True,"position":"bottom_right","size":40,"start":.5,"source_in":.2,"length":1}
            engine.render(src,out,engine.segments(3,[]),False,pip_path=asset,pip_settings=settings)
            self.assertAlmostEqual(engine.probe(out)["duration"],3,delta=.15)
            self.assertFalse(engine.probe(out)["audio"])
            def pixel(at):
                data=subprocess.run(["ffmpeg","-v","error","-ss",str(at),"-i",str(out),"-frames:v","1","-f","rawvideo","-pix_fmt","rgb24","-"],check=True,capture_output=True).stdout
                return data[(145*320+280)*3:(145*320+280)*3+3]
            self.assertLess(max(pixel(.2)),30)
            self.assertGreater(pixel(.8)[0],180)
            self.assertLess(max(pixel(1.8)),30)
            raw.write_bytes(b"not an MP4")
            with self.assertRaises(ValueError):pip_video.normalize(raw,root/"invalid.mp4")
