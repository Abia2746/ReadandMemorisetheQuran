import assert from "node:assert/strict";
import test from "node:test";
import {wordRuleHints} from "../mushaf_rules.mjs";
import {maddSites} from "../recording_tracker.mjs";
import {referenceTags} from "../recording_audit.mjs";

test("pause lengths preserve the distinct permitted counts",()=>{
  const word="ٱلرَّحِيمِ";
  const ayah={w:[word],o:[0],p:"ءَررَحِۦۦم"};
  const site=maddSites(ayah).values().next().value;
  assert.equal(wordRuleHints(word,[],[site])[0].label,"Stretch ×2/4/6");
});
test("word labels target the actual consonant and combine distinct rules",()=>{
  const word="أَنَّ",h=wordRuleHints(word,referenceTags(word,""),[]);
  assert.equal(h[0].label,"Nasalize ن");assert.equal(word[h[0].index],"ن");
  assert.equal(wordRuleHints("أَجْ",[],[])[0].label,"Bounce ج");
  assert.deepEqual(wordRuleHints("فِي",[],[]),[]);
  assert.equal(wordRuleHints("مِنْ",referenceTags("مِنْ","","رَبِّ"),[])[0].kind,"merge");
});
