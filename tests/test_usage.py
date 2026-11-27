import tempfile
import unittest
import threading
from render_queue import RenderQueue, Cancelled
from usage import Ledger, QuotaExceeded, limit_from_env

class UsageTests(unittest.TestCase):
    def test_limits_restart_and_idempotent_outcome(self):
        with tempfile.TemporaryDirectory() as d:
            ledger=Ledger(d,10)
            a=ledger.reserve("p","main",4.1)
            b=ledger.reserve("p","clipper",5)
            with self.assertRaises(QuotaExceeded):
                ledger.reserve("p","main",.1)
            ledger.finish(a,"completed")
            ledger.finish(a,"failed")
            ledger.finish(b,"rejected")
            c=ledger.reserve("p","main",2)
            again=Ledger(d,10)
            summary=again.summary()
            self.assertEqual(summary["attempted_seconds"],7)
            self.assertEqual(summary["remaining_seconds"],3)
            self.assertEqual(summary["outcomes"]["completed"]["seconds"],5)
            self.assertEqual(summary["outcomes"]["interrupted"]["seconds"],2)
            again.finish(c,"completed")
            self.assertEqual(again.summary(),summary)
    def test_concurrent_reservation(self):
        with tempfile.TemporaryDirectory() as d:
            ledger=Ledger(d,5)
            results=[]
            def work():
                try:
                    ledger.reserve("p","main",5)
                    results.append("accepted")
                except QuotaExceeded:
                    results.append("denied")
            threads=[threading.Thread(target=work) for _ in range(2)]
            for t in threads:t.start()
            for t in threads:t.join()
            self.assertCountEqual(results,["accepted","denied"])
    def test_queue_outcomes(self):
        with tempfile.TemporaryDirectory() as d:
            ledger=Ledger(d,20)
            queue=RenderQueue()
            started=threading.Event()
            def work(cancel,progress):
                started.set()
                if cancel.wait(3):
                    raise Cancelled()
                return {}
            try:
                a=ledger.reserve("a","main",5)
                task=queue.submit("a",work,lambda status:ledger.finish(a,status))
                self.assertTrue(started.wait(2))
                b=ledger.reserve("b","main",5)
                pending=queue.submit("b",work,lambda status:ledger.finish(b,status))
                queue.cancel(pending)
                queue.cancel(task)
            finally:
                queue.shutdown()
            self.assertEqual(ledger.summary()["outcomes"]["cancelled"],{"attempts":2,"seconds":10})
    def test_config(self):
        self.assertIsNone(limit_from_env(None))
        self.assertEqual(limit_from_env("0"),0)
        for bad in ["-1","1.5","unlimited"]:
            with self.assertRaises(ValueError):
                limit_from_env(bad)
