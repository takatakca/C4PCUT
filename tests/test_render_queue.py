import threading
import time
import tempfile
import unittest
import shutil
from pathlib import Path
from render_queue import RenderQueue, Cancelled
import engine

def wait_terminal(queue, ident):
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        state=queue.status(ident)
        if state["status"] in ("completed","cancelled","failed"):
            return state
        time.sleep(.01)
    raise AssertionError("Render did not finish")

class RenderQueueTests(unittest.TestCase):
    def test_queue_order_and_cancel(self):
        q=RenderQueue(capacity=2)
        started=threading.Event()
        def work(cancel,progress):
            progress(35)
            started.set()
            if cancel.wait(3):
                raise Cancelled()
            return {"url":"test"}
        try:
            a=q.submit("a",work)
            self.assertTrue(started.wait(1))
            b=q.submit("b",lambda c,p:{"url":"second"})
            self.assertEqual(q.status(a)["progress"],35)
            with self.assertRaises(ValueError):
                q.submit("c",work)
            self.assertEqual(q.cancel(b),"cancelled")
            c=q.submit("c",lambda c,p:{"url":"third"})
            q.cancel(a)
            self.assertEqual(wait_terminal(q,a)["status"],"cancelled")
            self.assertEqual(wait_terminal(q,c)["result"],{"url":"third"})
            self.assertFalse(q.busy())
        finally:
            q.shutdown()
    def test_quality_and_limits(self):
        self.assertEqual(engine.validate_format("vertical_4k","fit"),(2160,3840))
        self.assertEqual(engine.validate_quality("high"),18)
        with self.assertRaises(ValueError):
            engine.validate_render_budget("landscape_4k","fit",61,"standard")
        with self.assertRaises(ValueError):
            engine.validate_quality("invalid")
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg required")
    def test_real_render_and_precancel(self):
        with tempfile.TemporaryDirectory() as d:
            src,out=Path(d)/"source.mp4",Path(d)/"out.mp4"
            engine.run(["ffmpeg","-nostdin","-y","-f","lavfi","-i","color=blue:s=160x120:r=25:d=1","-c:v","libx264","-pix_fmt","yuv420p",str(src)])
            cancel=threading.Event()
            engine.render(src,out,[{"start":0,"end":1}],False,quality="compact",cancel=cancel)
            self.assertAlmostEqual(engine.probe(out)["duration"],1,delta=.15)
            cancel.set()
            with self.assertRaises(Cancelled):
                engine.render(src,out,[{"start":0,"end":1}],False,cancel=cancel)
