import assert from "node:assert/strict";
import test from "node:test";
import {matchesMeaning} from "../apps/web/lib/meaningQuiz.mjs";

test("accepts the typed meaning for Al-Baqarah 2:57:6",()=>{
  for(const answer of ["manna","the manna"," MANNA! "])
    assert.equal(matchesMeaning(answer,"[the] manna"),true);
});
test("ignores typography while requiring a complete answer",()=>{
  assert.equal(matchesMeaning("and we said","And We said,"),true);
  for(const answer of ["","...","man","mana","manna and quails"])
    assert.equal(matchesMeaning(answer,"[the] manna"),false);
  assert.equal(matchesMeaning("you","[over] you"),false);
});

test("accepts optional words in a published gloss and preserves meaning-bearing differences",()=>{
  for(const answer of ["asked for water","asked water"," Asked (for) water! "])
    assert.equal(matchesMeaning(answer,"asked (for) water"),true);
  assert.equal(matchesMeaning("and quails","and [the] quails"),true);
  for(const answer of ["water","asked for","asked for food","never asked for water","water asked"])
    assert.equal(matchesMeaning(answer,"asked (for) water"),false);
  assert.equal(matchesMeaning("did ask","did (not) ask"),false);
});

test("difficult words need two delayed recalls; early retries cannot accelerate the schedule",async()=>{
  const {updateWordReview}=await import("../apps/web/lib/meaningQuiz.mjs");
  let item=updateWordReview(undefined,false,100);
  assert.deepEqual(item,{stage:0,misses:1,due:101});
  assert.equal(updateWordReview(item,true,100),item);
  item=updateWordReview(item,true,101);
  assert.deepEqual(item,{stage:1,misses:1,due:104});
  assert.equal(updateWordReview(item,true,103),item);
  item=updateWordReview(item,true,108);
  assert.deepEqual(item,{stage:2,misses:1,due:115});
  assert.deepEqual(updateWordReview(item,false,109),{stage:0,misses:2,due:110});
  assert.equal(updateWordReview(undefined,true,100),undefined);
});
