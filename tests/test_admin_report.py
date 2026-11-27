import tempfile
import unittest
import json
import sqlite3
from pathlib import Path
import admin_report
import capabilities
import usage

CLIENT="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

class AdminReportTests(unittest.TestCase):
    def test_report_read_only_and_no_secrets(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/"workspaces"/"alpha";folder.mkdir(parents=True)
            (folder/("a"*32)).mkdir()
            ledger=usage.Ledger(folder,80)
            # The report must not initialize Ledger or interrupt an accepted job.
            ident=ledger.reserve("project","main",12)
            ws={"alpha":{"password_sha256":"SECRET_DIGEST","monthly_render_seconds":80}}
            policy={"max_output_edge":1280,"max_render_seconds":30,"max_projects":2,"qualities":["compact"],"features":[]}
            profiles={p:{"capabilities":policy,"monthly_render_seconds":40} for p in capabilities.PLANS}
            import time
            now=int(time.time())
            grant={"clientId":CLIENT,"product":"c4pcut","plan":"free","active":True,"status":"active","validFrom":now-10,"validUntil":now+10}
            registry={"version":1,"grants":{CLIENT:grant},"audit":[{"private":"SECRET_AUDIT"}]}
            result=admin_report.report(root,ws,{CLIENT:"alpha"},profiles,registry,now)
            row=result["workspaces"][0]
            self.assertEqual(row["grant_status"],"active")
            self.assertEqual(row["usage"]["remaining_seconds"],28)
            self.assertEqual(row["usage"]["outcomes"]["accepted"]["seconds"],12)
            self.assertEqual(row["projects"],1)
            serialized=json.dumps(result)
            self.assertNotIn(CLIENT,serialized)
            self.assertNotIn("SECRET",serialized)
            self.assertNotIn("project\"",serialized)
            self.assertEqual(ledger.summary()["outcomes"]["accepted"]["seconds"],12)
            expired=admin_report.report(root,ws,{CLIENT:"alpha"},profiles,registry,now+11)["workspaces"][0]
            self.assertEqual(expired["grant_status"],"expired")
            self.assertIsNone(expired["plan"])
            self.assertIsNone(expired["capabilities"])
            ledger.finish(ident,"completed")
    def test_missing_ledger_not_created(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            folder=root/"workspaces"/"alpha";folder.mkdir(parents=True)
            self.assertEqual(admin_report.monthly_usage(folder,"2026-11",60)["status"],"unavailable")
            self.assertFalse((folder/"usage.sqlite3").exists())
