import unittest
from unittest.mock import patch, MagicMock
import json
import director
import engine

class DirectorTests(unittest.TestCase):
    def setUp(self):
        self.clips=engine.segments(10,[3,6])
        self.cues=[{"start":3,"end":5,"text":"Hello"}]
        self.beats=[3.2,3.7,4.2]
    def test_presets(self):
        result=director.plan("Short edit",4,"social","preset",self.clips,self.cues,self.beats)
        self.assertEqual(result["provider"],"preset")
        self.assertAlmostEqual(result["duration"],4)
        self.assertEqual(result["clips"],sorted(result["clips"]))
        self.assertIn(1,result["clips"])
        self.assertEqual(len(engine.validate_edits(result["clips"],self.clips,result["edits"])),2)
    def test_reject_invalid(self):
        for p in [
            {"clips":[0],"edits":{"0":{"effect":"shell"}},"reason":"x"},
            {"clips":[0],"edits":{"1":{"effect":"fade"}},"reason":"x"},
            {"clips":[0],"edits":{},"reason":"x","command":"bad"},
            {"clips":[0,1],"edits":{},"reason":"too long"},
            {"clips":[True],"edits":{},"reason":"bad"},
        ]:
            with self.assertRaises(ValueError):
                director.validate_plan(p,self.clips,4)
    def test_ollama_contract(self):
        reply={"clips":[1],"edits":{"1":{"start":3,"end":5,"effect":"warm"}},"reason":"Uses speech"}
        opener=MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value=json.dumps({"response":json.dumps(reply)}).encode()
        with patch.dict("os.environ",{"C4PCUT_OLLAMA_MODEL":"local-model"}),patch("director.urllib.request.build_opener",return_value=opener):
            result=director.plan("Warm edit",2,"cinematic","ollama",self.clips,self.cues,self.beats)
        self.assertEqual(result["duration"],2)
        request=opener.open.call_args.args[0]
        self.assertEqual(request.full_url,"http://127.0.0.1:11434/api/generate")
        data=json.loads(request.data)
        self.assertEqual(data["format"],"json")
        self.assertIn("Hello",data["prompt"])
