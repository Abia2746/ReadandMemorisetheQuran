// Shared by the React reader and the Streamlit classroom.
function normalized(text) {
  return text.normalize("NFKC").toLowerCase().replace(/['’]/gu, "")
    .replace(/[\p{P}\p{Z}\s]+/gu, " ").trim();
}

export function matchesMeaning(answer, meaning) {
  const typed = normalized(answer);
  if (!typed) return false;
  // Only omit editorial articles and "for" when the source marks them optional.
  // Keep pronouns, negations, word order and the rest of the gloss intact.
  const parts = meaning.split(/(\([^()]*\)|\[[^\[\]]*\])/u);
  const tokens = typed.split(" ");
  let positions = new Set([0]);
  for (const part of parts) {
    const phrase = normalized(part);
    if (!phrase) continue;
    const optional = (part.startsWith("(") || part.startsWith("[")) && /^(?:a|an|the|for)$/u.test(phrase);
    for (const token of phrase.split(" ")) {
      const next = new Set();
      for (const pos of positions) {
        if (optional || (pos === 0 && /^(a|an|the)$/u.test(token))) next.add(pos);
        if (tokens[pos] === token) next.add(pos+1);
      }
      positions = next;
    }
  }
  return positions.has(tokens.length);
}

/** @param {HTMLElement} host @param {{arabic:string,meaning:string,ref:string}[]} words */
export function mountMeaningQuiz(host, words) {
  const deck = words.filter(word => word.arabic.trim() && normalized(word.meaning));
  const known = new Map();
  let soundOn = true;
  try { soundOn = localStorage.getItem("am.quiz.sound") !== "off"; } catch {}
  let round = deck, index = 0, missed = [];
  function node(tag, text, className) {
    const el = document.createElement(tag);
    el.textContent = text;
    if (className) el.className = className;
    return el;
  }
  function tone(correct) {
    if (!soundOn) return;
    try {
      const Audio = window.AudioContext || window.webkitAudioContext;
      if (!Audio) return;
      const ctx = new Audio();
      const play = () => {
        const start = ctx.currentTime;
        const oscillator = ctx.createOscillator();
        const gain = ctx.createGain();
        oscillator.type = "sine";
        oscillator.frequency.setValueAtTime(correct ? 440 : 330, start);
        oscillator.frequency.exponentialRampToValueAtTime(correct ? 554 : 294, start+.2);
        gain.gain.setValueAtTime(.0001, start);
        gain.gain.exponentialRampToValueAtTime(.042, start+.035);
        gain.gain.exponentialRampToValueAtTime(.0001, start+.32);
        oscillator.connect(gain); gain.connect(ctx.destination);
        oscillator.onended = () => { void ctx.close().catch(()=>{}); };
        oscillator.start(start); oscillator.stop(start+.34);
      };
      void ctx.resume().then(play).catch(()=>{ void ctx.close().catch(()=>{}); });
    } catch {}
  }
  function startRound(cards) {
    round = cards; missed = []; index = 0; draw(true);
  }
  function boxes(finished, updated) {
    const group = node("div", "", "am-quiz-boxes");
    for (const [state,title] of [[false,"Must review"],[true,"Know"]]) {
      const cards = deck.filter(card => known.get(card.ref) === state);
      const box = node("button", title+" · "+cards.length, "am-quiz-box");
      box.type = "button";
      box.dataset.box = state ? "know" : "review";
      if (updated === state) box.className += " am-quiz-box-updated";
      box.disabled = !finished || !cards.length;
      box.onclick = () => startRound(cards);
      group.append(box);
    }
    return group;
  }
  function draw(focus) {
    host.replaceChildren();
    if (deck.length < words.length) host.append(node("p", (words.length-deck.length)+" words have no available meaning and are skipped."));
    if (!deck.length) {
      host.append(node("p", "Word meanings are unavailable for this passage."));
      return;
    }
    const mute = node("button",soundOn ? "Sound on" : "Sound off","am-button am-small-action");
    mute.type = "button"; mute.setAttribute("aria-pressed",String(soundOn));
    mute.onclick = () => {
      soundOn = !soundOn;
      mute.textContent = soundOn ? "Sound on" : "Sound off";
      mute.setAttribute("aria-pressed",String(soundOn));
      try { localStorage.setItem("am.quiz.sound",soundOn ? "on" : "off"); } catch {}
    };
    host.append(mute);
    if (index === round.length) {
      const summary = node("p", "Round complete · "+(round.length-missed.length)+" of "+round.length+" meanings matched.");
      const restart = node("button", missed.length ? "Retry missed words" : "Practise again", "am-button am-small-action");
      restart.type = "button";
      restart.onclick = () => { round = missed.length ? missed : deck; missed = []; index = 0; draw(true); };
      host.append(summary, boxes(true), restart);
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
    const boxRow = node("div","");
    boxRow.append(boxes(false));
    let graded = false;
    function grade(correct) {
      if (graded) return;
      graded = true;
      if (!correct) missed.push(word);
      known.set(word.ref,correct);
      boxRow.replaceChildren(boxes(false,correct));
      const wash = node("div","","am-quiz-wash");
      wash.dataset.box = correct ? "know" : "review";
      wash.setAttribute("aria-hidden","true");
      host.append(wash);
      tone(correct);
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
    host.append(progress, arabic, form, boxRow);
    if (focus) input.focus();
  }
  draw(false);
}
