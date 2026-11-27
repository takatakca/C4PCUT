import unittest
import tempfile
import capabilities
import usage

def profiles():
    return {p:{"capabilities":{"max_output_edge":1280 if p=="free" else 3840,"max_render_seconds":30,"max_projects":2,"qualities":["compact","high"],"features":["clipper"]},"monthly_render_seconds":30 if p=="free" else 100} for p in capabilities.PLANS}

class PlanProfilesTests(unittest.TestCase):
    def test_intersection_never_expands(self):
        config=profiles()
        parsed=capabilities.parse_profiles(config)
        local=capabilities.parse({"max_output_edge":1920,"max_render_seconds":10,"max_projects":1,"qualities":["standard"],"features":["music"]})
        effective=capabilities.intersect(parsed["pro"].policy,local)
        self.assertEqual(effective.max_output_edge,1920)
        self.assertEqual(effective.max_render_seconds,10)
        self.assertEqual(effective.max_projects,1)
        self.assertEqual(effective.qualities,frozenset())
        self.assertEqual(effective.features,frozenset())
        config["free"]["monthly_render_seconds"]=None
        with self.assertRaises(ValueError):capabilities.parse_profiles(config)
        config.pop("pro")
        with self.assertRaises(ValueError):capabilities.parse_profiles(config)
    def test_quota_shared_across_plan_changes(self):
        with tempfile.TemporaryDirectory() as d:
            ledger=usage.Ledger(d,80)
            ident=ledger.reserve("p","main",50,100)
            ledger.finish(ident,"completed")
            self.assertEqual(ledger.summary(100)["remaining_seconds"],30)
            self.assertEqual(ledger.summary(30)["remaining_seconds"],0)
            with self.assertRaises(usage.QuotaExceeded):ledger.reserve("p","main",1,30)
            with self.assertRaises(usage.QuotaExceeded):ledger.reserve("p","main",31,100)
            self.assertEqual(ledger.summary()["attempted_seconds"],50)
