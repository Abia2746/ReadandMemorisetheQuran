// Shared by the React reader and the Streamlit classroom.
function normalized(text) {
  return text.normalize("NFKC").toLowerCase().replace(/['’]/gu, "")
    .replace(/[\p{P}\p{Z}\s]+/gu, " ").trim();
}

export function matchesMeaning(answer, meaning) {
  const typed = normalized(answer);
  if (!typed) return false;
  const target = normalized(meaning);
  return typed === target || typed === target.replace(/^(a|an|the) /u, "");
}

/** @param {HTMLElement} host @param {{arabic:string,meaning:string,ref:string}[]} words */
export function mountMeaningQuiz(host, words) {
  const deck = words.filter(word => word.arabic.trim() && normalized(word.meaning));
  let round = deck, index = 0, missed = [];
  function node(tag, text, className) {
    const el = document.createElement(tag);
    el.textContent = text;
    if (className) el.className = className;
    return el;
  }
  function draw(focus) {
    host.replaceChildren();
    if (deck.length < words.length) host.append(node("p", (words.length-deck.length)+" words have no available meaning and are skipped."));
    if (!deck.length) {
      host.append(node("p", "Word meanings are unavailable for this passage."));
      return;
    }
    if (index === round.length) {
      const summary = node("p", "Round complete · "+(round.length-missed.length)+" of "+round.length+" meanings matched.");
      const restart = node("button", missed.length ? "Retry missed words" : "Practise again", "am-button am-small-action");
      restart.type = "button";
      restart.onclick = () => { round = missed.length ? missed : deck; missed = []; index = 0; draw(true); };
      host.append(summary, restart);
      if (focus) restart.focus();
      return;
    }
    const word = round[index];
    const progress = node("p", "Word "+(index+1)+" of "+round.length+" · "+word.ref);
    const arabic = node("p", word.arabic, "am-quiz-arabic");
    arabic.lang = "ar"; arabic.dir = "rtl";
    const form = document.createElement("form");
    const label = node("label", "What does this word mean?");
    const input = document.createElement("input");
    input.className = "am-field"; input.required = true; input.autocomplete = "off"; input.dir = "auto";
    label.append(input);
    const check = node("button", "Check answer", "am-button am-small-action");
    check.type = "submit";
    const reveal = node("button", "Show meaning", "am-button am-small-action");
    reveal.type = "button";
    const feedback = node("p", "");
    feedback.setAttribute("role", "status");
    let graded = false;
    function grade(correct) {
      if (graded) return;
      graded = true;
      if (!correct) missed.push(word);
      feedback.textContent = (correct ? "Matched. " : "For review. ")+"Passage meaning: "+word.meaning;
      input.readOnly = true; reveal.hidden = true;
      check.textContent = index+1 === round.length ? "See results" : "Next word";
      check.focus();
    }
    form.onsubmit = event => {
      event.preventDefault();
      if (graded) { index++; draw(true); }
      else if (input.value.trim()) grade(matchesMeaning(input.value, word.meaning));
    };
    reveal.onclick = () => { input.required = false; grade(false); };
    form.append(label, check, reveal, feedback);
    host.append(progress, arabic, form);
    if (focus) input.focus();
  }
  draw(false);
}
