import tempfile
import unittest
from pathlib import Path
from admin_dashboard import render_html,write_html

def sample():
    return {"month":"2026-11","mode":"private-pilot-read-only","billing_enabled":False,"audit_entries":3,"workspaces":[
        {"workspace":"alpha","grant_status":"active","plan":"free","expires_at":None,"projects":2,"capabilities":{"max_output_edge":1280,"max_render_seconds":30,"max_projects":2,"qualities":["compact"],"features":["clipper"]},"usage":{"status":"available","attempted_seconds":12,"limit_seconds":40,"remaining_seconds":28,"outcomes":{"completed":{"attempts":1,"seconds":12}}}},
        {"workspace":"<script>alert(1)</script>","grant_status":"expired","plan":None,"expires_at":0,"projects":0,"capabilities":None,"usage":{"status":"unavailable","limit_seconds":None}}]}

class AdminDashboardTests(unittest.TestCase):
    def test_private_snapshot_and_escaping(self):
        html=render_html(sample())
        self.assertIn("C4PCUT ADMIN",html)
        self.assertIn("28 seconds remaining",html)
        self.assertIn("Usage unavailable",html)
        self.assertIn("Expired",html)
        self.assertIn("Auto Clipper",html)
        self.assertIn("Billing disabled",html)
        self.assertIn("&lt;script&gt;",html)
        self.assertNotIn("<script>",html)
        self.assertIn("default-src 'none'",html)
        self.assertIn("Attempted seconds (known)",html)
    def test_output_exclusive_and_private(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"report.html"
            write_html(p,sample())
            self.assertEqual(p.stat().st_mode&0o777,0o600)
            self.assertIn("C4PCUT ADMIN",p.read_text())
            with self.assertRaises(FileExistsError):write_html(p,sample())
            link=Path(d)/"link.html";link.symlink_to(p)
            with self.assertRaises(FileExistsError):write_html(link,sample())
            with self.assertRaises(ValueError):write_html(Path("relative.html"),sample())
