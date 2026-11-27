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
