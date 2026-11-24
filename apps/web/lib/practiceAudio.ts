// A user gesture that starts one audio activity interrupts the previous one.
export const practiceAudioEvent = "almuallim:audio-turn";
export function takeAudioTurn() {
  window.dispatchEvent(new Event(practiceAudioEvent));
}
