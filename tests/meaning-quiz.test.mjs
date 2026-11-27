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
