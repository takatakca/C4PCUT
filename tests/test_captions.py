import shutil
import tempfile
import unittest
from pathlib import Path
import captions
import engine
import json

class CaptionTests(unittest.TestCase):
    def test_parse_and_remap(self):
        cues = captions.parse_srt("1\n00:00:01,000 --> 00:00:05,000\nHello\n\n2\n00:00:06,000 --> 00:00:07,000\nSalut\n", 8)
        mapped = captions.remap(cues, [{"start":2,"end":3},{"start":6,"end":8}])
        self.assertEqual(mapped, [{"start":0,"end":1,"text":"Hello"},{"start":1,"end":2,"text":"Salut"}])
        self.assertIn("00:00:01,000 --> 00:00:02,000", captions.to_srt(mapped))
    def test_validation(self):
        for c in [{"start":0,"end":9,"text":"x"},{"start":True,"end":2,"text":"x"},{"start":0,"end":1,"text":""}]:
            with self.assertRaises(ValueError):
                captions.validate([c], 8)
        self.assertNotIn("<", captions.validate([{"start":0,"end":1,"text":"<b>"}],8)[0]["text"])
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
    def test_embed_subtitle(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            src,out,srt=root/"source.mp4",root/"output.mp4",root/"captions.srt"
            engine.run(["ffmpeg","-nostdin","-y","-f","lavfi","-i","color=blue:s=160x120:r=25:d=2","-c:v","libx264","-pix_fmt","yuv420p",str(src)])
            srt.write_text(captions.to_srt([{"start":0,"end":1,"text":"Hello"}]),encoding="utf-8")
            engine.render(src,out,[{"start":0,"end":2}],False,srt)
            data=json.loads(engine.run(["ffprobe","-v","error","-show_streams","-of","json",str(out)]).stdout)
            self.assertTrue(any(s["codec_type"]=="subtitle" and s["codec_name"]=="mov_text" for s in data["streams"]))
