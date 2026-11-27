// Each item is one reference site in a connected reading. A missing index
// leaves the hint at word level, preserving the original Uthmani spelling.
export const ruleNames={all:"All rules",madd:"Stretch",merge:"Merge",soften:"Soften",bounce:"Bounce",nasal:"Nasalize"};
export function wordRuleHints(word,tags,sites){
  const hints=[];
  for(const site of sites){
    const counts=site.label==="Pause-dependent madd"?"2/4/6":[...new Set(site.range)].join("–");
    hints.push({kind:"madd",label:"Stretch ×"+counts,
      tip:site.label==="Pause-dependent madd"?"When stopping here, hold the long vowel for 2, 4 or 6 counts.":
      "Hold the long vowel for "+counts+" counts"+(["Muttasil","Munfasil","Lazim"].includes(site.label)?" (Madd "+site.label+")": "")+"."});
  }
  for(const m of word.matchAll(/[قطبجد][ْۡ]/gu)){
    hints.push({kind:"bounce",index:m.index,label:"Bounce "+m[0][0],tip:"Give "+m[0][0]+" a light, brief bounce without adding a vowel."});
  }
  for(const m of word.matchAll(/[نم][\p{M}]*ّ[\p{M}]*/gu)){
    hints.push({kind:"nasal",index:m.index,label:"Nasalize "+m[0][0],tip:"Let the nasal sound resonate for two counts."});
  }
  for(const tag of tags){
    const kind=tag.includes("idghām")?"merge":tag.includes("ikhfā")?"soften":null;
    if(!kind)continue;
    const meem=tag.startsWith("Mīm");
    const letter=meem?"م":"ن";
    hints.push({kind,label:ruleNames[kind]+" "+letter,
      tip:kind==="merge"?"When joining, merge the sound into the following letter.":"When joining, soften the sound before the next letter with nasal resonance."});
  }
  return hints;
}
