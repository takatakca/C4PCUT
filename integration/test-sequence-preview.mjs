import {test} from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import {readFileSync} from "node:fs";
const ui=vm.runInNewContext(readFileSync(new URL("../web/sequence-preview.js",import.meta.url),"utf8")+"\nSequencePreview;");
const clips=[{id:0,start:0,end:2},{id:1,start:2,end:4},{id:2,start:4,end:6}];
test("edited output clock excludes trims and unselected source gaps",()=>{
  const p=ui.build(clips,{0:{start:.5,end:1.5},2:{start:4.5,end:6}},new Set([2,0]));
  assert.equal(p.total,2.5);assert.equal(p.ranges.length,2);
  assert.equal(p.ranges[1].offset,1);
  assert.equal(ui.locate(p,0).source,.5);
  assert.equal(ui.locate(p,1).source,4.5);
  assert.equal(ui.locate(p,1.5).source,5);
  assert.equal(ui.locate(p,2.5).source,6);
  assert.equal(ui.position(p.ranges[1],5),1.5);
  assert.equal(ui.position(p.ranges[0],8),1);
});
test("empty and invalid ranges are safe",()=>{
  assert.equal(ui.locate(ui.build(clips,{},new Set()),0),null);
  assert.equal(ui.build(clips,{0:{start:-1,end:2}},new Set([0])).total,0);
  assert.equal(ui.locate(ui.build(clips,{},new Set([0])),NaN),null);
});
