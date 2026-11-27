import {test} from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import {readFileSync} from "node:fs";
const ui=vm.runInNewContext(readFileSync(new URL("../web/plan-ui.js",import.meta.url),"utf8")+"\nPlanUI;");
const p={max_output_edge:1280,max_render_seconds:30,qualities:["compact"],features:[]};
test("export policy mirrors permitted edge and render settings",()=>{
  assert.equal(ui.preset(p,"vertical"),true);
  assert.equal(ui.preset(p,"landscape_hd"),false);
  assert.equal(ui.preset(p,"original",{width:1920,height:1080}),false);
  const settings={preset:"vertical",quality:"compact",caption_mode:"soft",use_music:false};
  assert.equal(ui.render(p,settings,null,30),true);
  assert.equal(ui.render(p,settings,null,31),false);
  assert.equal(ui.render(p,{...settings,quality:"high"},null,1),false);
  assert.equal(ui.render(p,{...settings,caption_mode:"bold"},null,1),false);
  assert.equal(ui.render(p,{...settings,use_music:true},null,1),false);
  assert.equal(ui.render(null,settings,null,500),true);
});
test("usage handles exhausted, zero, unlimited and unavailable caps",()=>{
  assert.equal(ui.usage({attempted_seconds:50,limit_seconds:100}).ratio,.5);
  assert.equal(ui.usage({attempted_seconds:150,limit_seconds:100}).ratio,1);
  assert.equal(ui.usage({attempted_seconds:0,limit_seconds:0}).ratio,1);
  assert.equal(ui.usage({attempted_seconds:4,limit_seconds:null}).ratio,null);
  assert.equal(ui.usage({enabled:false}),null);
  assert.equal(ui.usage({attempted_seconds:4}),null);
});
