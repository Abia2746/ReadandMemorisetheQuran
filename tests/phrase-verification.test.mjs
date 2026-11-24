/** Regression tests for final phrase gate; no microphone needed. */
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {resolve,dirname} from "node:path";
import {fileURLToPath} from "node:url";
const root=resolve(dirname(fileURLToPath(import.meta.url)),"..");
const js=readFileSync(resolve(root,"studio.js"),"utf8");

const from=js.indexOf("  const PHRASE_WORDS=4;");
const until=js.indexOf("  function mark(index,confirm){",from);
assert.ok(from>=0&&until>from,"Phrase gate is present in studio");
const gate=js.slice(from,until);
const words=[
  {ayah:1,ar:"بسم"}, {ayah:1,ar:"الله"},
  {ayah:1,ar:"الرحمن"}, {ayah:1,ar:"الرحيم"},
  {ayah:2,ar:"الحمد"}, {ayah:2,ar:"لله"}
];
const expected=words.map(w=>w.ar);
function fixture(){
  const confirmed=[];
  const create=new Function("words","expected","mark",gate+
    "\nreturn {phraseEnd,phraseMatches,confirmPhrases,prefixSize};");
  const verifier=create(words,expected,(i,ok)=>{if(ok)confirmed.push(i)});
  return {verifier,confirmed};
}
{
  const {verifier,confirmed}=fixture();
  assert.equal(verifier.phraseEnd(0),4);
  assert.equal(verifier.phraseEnd(4),6);
  assert.equal(verifier.phraseMatches(["ب"],0),false,
    "first letter must never validate a word or phrase");
  assert.equal(verifier.phraseMatches(["بسم"],0),false,
    "the first completed word must not confirm the phrase");
  assert.equal(verifier.phraseMatches(["بسم","الله","الرحمن"],0),false,
    "three of four words is still an incomplete phrase");
  assert.equal(verifier.phraseMatches(["بسم","الله","الرحيم","الرحمن"],0),false,
    "reordering a phrase must not validate");
  assert.equal(verifier.phraseMatches(["بسم","الله","الرحمن","الرحين"],0),false,
    "wrong final word cannot be silently accepted");
  assert.deepEqual(verifier.confirmPhrases(["بسم","الله","الرحمن"],0),{cursor:0,used:0});
  assert.deepEqual(confirmed,[],"no words become green on a partial phrase");
  assert.deepEqual(verifier.confirmPhrases(["بسم","الله","الرحمن","الرحيم"],0),
    {cursor:4,used:4});
  assert.deepEqual(confirmed,[0,1,2,3],"all words must be recognised in order");
}
{
  const {verifier,confirmed}=fixture();
  const full=["بسم","الله","الرحمن","الرحيم","الحمد","لله"];
  assert.deepEqual(verifier.confirmPhrases(full,0),{cursor:6,used:6});
  assert.deepEqual(confirmed,[0,1,2,3,4,5]);
}
assert.doesNotMatch(js,/observedCounts\.get\(idx\)>=2\|\|sustained/,
  "repeated position-only observations may not grant green");
assert.match(js,/cloudAccum\.push\(\.\.\.fresh\)/,
  "final cloud speech segments must be buffered");
console.log("PASS: Full phrase gate rejects partial letters, missing/reordered words, and position-only confirmation.");
