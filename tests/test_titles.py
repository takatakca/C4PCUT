import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import captions
import engine
import projects
import titles

class TitleTests(unittest.TestCase):
    def test_validation_and_clipping(self):
        item={"start":.5,"end":2,"text":r"Hi {\pos(0,0)}","position":"top"}
        valid=titles.validate([item],3)
        self.assertNotIn(r"\pos",titles.to_ass(valid))
        self.assertEqual(titles.for_output(valid,1)[0]["end"],1)
        self.assertEqual(titles.for_output(valid,.4),[])
        for bad in ([item,item],[{**item,"position":"bad"}],[{**item,"style":"invalid"}],[{**item,"end":4}],[{**item,"start":True}]):
            with self.assertRaises(ValueError):titles.validate(bad,3)
    def test_project_legacy_and_title_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);(folder/"source.media").write_bytes(b"source")
            meta={"duration":3,"width":160,"height":120,"audio":False}
            clips=engine.segments(3,[])
            job={"folder":folder,"metadata":meta,"clips":clips}
            item={"start":0,"end":1,"text":"Opening","position":"center"}
            projects.save(job,{"name":"Title","selected":[0],"titles":[item]})
            self.assertEqual(projects.read(folder)["state"]["titles"],[{**item,"style":"classic"}])
            styled={**item,"position":"lower_left","style":"purple_banner"}
            projects.save(job,{"name":"Styled","selected":[0],"titles":[styled]})
            self.assertEqual(projects.read(folder)["state"]["titles"],[styled])
            self.assertEqual(projects.validate_state({"name":"Legacy"},clips,meta,False)["titles"],[])
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg required")
    def test_title_pixels_and_soft_caption_coexist(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);src=root/"source.mp4";out=root/"output.mp4";srt=root/"captions.srt"
            engine.run(["ffmpeg","-nostdin","-y","-f","lavfi","-i","color=black:s=320x180:r=25:d=2","-c:v","libx264","-pix_fmt","yuv420p",str(src)])
            srt.write_text(captions.to_srt([{"start":0,"end":1,"text":"Caption"}]),encoding="utf-8")
            layer=titles.to_ass(titles.validate([{"start":0,"end":1,"text":"TITLE","position":"center"}],2))
            engine.render(src,out,[{"start":0,"end":2}],False,srt,title_ass=layer)
            def frame(at):
                return subprocess.run(["ffmpeg","-v","error","-ss",str(at),"-i",str(out),"-frames:v","1","-f","rawvideo","-pix_fmt","rgb24","-"],check=True,capture_output=True).stdout
            self.assertGreater(max(frame(.5)),180)
            self.assertLess(max(frame(1.5)),30)
            data=json.loads(engine.run(["ffprobe","-v","error","-show_streams","-of","json",str(out)]).stdout)
            self.assertTrue(any(s["codec_type"]=="subtitle" for s in data["streams"]))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg required")
    def test_lower_third_graphic_background_in_real_render(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);src=root/"source.mp4";out=root/"output.mp4"
            engine.run(["ffmpeg","-nostdin","-y","-f","lavfi","-i","color=black:s=320x180:r=25:d=2","-c:v","libx264","-pix_fmt","yuv420p",str(src)])
            layer=titles.to_ass(titles.validate([{"start":0,"end":1,"text":"ARTIST","position":"lower_left","style":"purple_banner"}],2))
            self.assertIn("lower_left_purple_banner",layer)
            engine.render(src,out,[{"start":0,"end":2}],False,title_ass=layer)
            frame=subprocess.run(["ffmpeg","-v","error","-ss",".5","-i",str(out),"-frames:v","1","-f","rawvideo","-pix_fmt","rgb24","-"],check=True,capture_output=True).stdout
            # A purple box, not only white text, must survive the encoder.
            colored=sum(1 for r,g,b in zip(frame[0::3],frame[1::3],frame[2::3]) if r>65 and b>90 and b>g+35 and r>g+20)
            self.assertGreater(colored,50)
