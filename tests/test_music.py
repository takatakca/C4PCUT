import math
import shutil
import tempfile
import unittest
from pathlib import Path
import engine
import music

class MusicTests(unittest.TestCase):
    def test_onsets_and_cuts(self):
        energy=[.001]*250
        for i in (25,50,75,100,125,150,175,200,225):
            energy[i]=.4
        beats=music.detect_onsets(energy,.02)
        self.assertEqual(beats,[.5,1,1.5,2,2.5,3,3.5,4,4.5])
        clips=music.beat_cuts(5,beats,2)
        self.assertEqual([c["start"] for c in clips],[0,1,2,3,4])
        self.assertEqual(music.detect_onsets([.2]*100,.02),[])
        for invalid in (-1,2,True,float("nan")):
            with self.assertRaises(ValueError):
                music.validate_gain(invalid)
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg required")
    def test_audio_mix_and_short_track(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            src,track,out=root/"source.mp4",root/"music.wav",root/"output.mp4"
            engine.run(["ffmpeg","-nostdin","-y","-f","lavfi","-i","color=red:s=160x120:r=25:d=3","-f","lavfi","-i","sine=frequency=440:duration=3","-c:v","libx264","-c:a","aac","-shortest",str(src)])
            engine.run(["ffmpeg","-nostdin","-y","-f","lavfi","-i","sine=frequency=660:duration=1","-ar","48000","-ac","2",str(track)])
            analysis=music.analyze(track,3)
            self.assertGreater(max(analysis["peaks"]),0)
            self.assertEqual(analysis["peaks"][-1],0)
            engine.render(src,out,[{"start":0,"end":1},{"start":2,"end":3}],True,music_path=track,music_gain=.5,source_gain=.5)
            self.assertTrue(engine.probe(out)["audio"])
            self.assertAlmostEqual(engine.probe(out)["duration"],2,delta=.2)
            engine.render(src,out,[{"start":2,"end":3}],False,music_path=track)
            self.assertTrue(engine.probe(out)["audio"])
            self.assertAlmostEqual(engine.probe(out)["duration"],1,delta=.2)
