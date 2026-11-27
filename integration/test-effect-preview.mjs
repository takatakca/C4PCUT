import {test} from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import {readFileSync} from "node:fs";
const ui=vm.runInNewContext(readFileSync(new URL("../web/effect-preview.js",import.meta.url),"utf8")+"\nEffectPreview;");
const clips=[{id:0,start:0,end:2},{id:1,start:2,end:4}],selected=new Set([0]);
const at=(effect,time,enabled=true)=>ui.at(clips,{0:{start:.5,end:1.5,effect}},selected,time,enabled);
test("preview applies only selected trimmed source interval and respects toggle",()=>{
  assert.equal(at("mono",1).filter,"grayscale(1)");
  assert.equal(at("mono",.2).effect,"none");
  assert.equal(at("mono",1.5).effect,"none");
  assert.equal(at("mono",2.5).effect,"none");
  assert.equal(at("mono",1,false).effect,"none");
  assert.equal(at("unknown",1).effect,"none");
});
test("fade and zoom are bounded by trimmed duration",()=>{
  assert.equal(at("fade",.5).filter,"brightness(0.0000)");
  assert.equal(at("fade",1).filter,"brightness(1.0000)");
  assert.equal(at("zoom",.5).scale,1);
  assert.ok(Math.abs(at("zoom",1).scale-1.06)<1e-8);
  assert.ok(at("zoom",1.49).scale<1.12);
  assert.equal(at("warm",1).scale,1);
});
