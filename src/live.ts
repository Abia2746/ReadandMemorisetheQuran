/**
 * Live recitation.
 *
 * Two engines behind one hook, because no single one covers every device:
 *
 *  - `speech`  the browser's own recogniser. Truly instant: interim results
 *              arrive while you are still speaking, so words light as you say
 *              them. No key, no cost. Chrome, Edge, Samsung Internet, Chrome on
 *              Android. NOT Safari or any iOS browser — they are all WebKit and
 *              none of them expose SpeechRecognition.
 *
 *  - `cloud`   MediaRecorder plus a rolling upload to Gemini. Every couple of
 *              seconds the recording so far is sent and the transcript comes
 *              back. Works on iOS Safari, costs a request per tick, and runs
 *              roughly a second behind your voice.
 *
 * Lighting is monotonic. Interim transcripts get revised by the recogniser, and
 * an un-lit word looks like a mistake the reader did not make, so a word once lit
 * never goes dark.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { WordState } from './align'
import { createRecogniser, speechSupported, type Recogniser } from './speech'
import { transcribeArabic } from './gemini'

const RANK: Record<WordState, number> = { pending: 0, missed: 1, close: 2, correct: 3 }

const DIACRITICS = /[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]/g
const NON_LETTERS = /[^\u0621-\u064A\s]/g

export function normaliseArabic(raw: string): string {
  return raw
    .replace(DIACRITICS, '')
    .replace(/[إأآٱ]/g, 'ا')
    .replace(/ى/g, 'ي')
    .replace(/ة/g, 'ه')
    .replace(NON_LETTERS, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function levenshtein(a: string, b: string): number {
  if (a === b) return 0
  if (!a.length) return b.length
  if (!b.length) return a.length
  let previous = Array.from({ length: b.length + 1 }, (_, i) => i)
  for (let i = 1; i <= a.length; i += 1) {
    const current = [i]
    for (let j = 1; j <= b.length; j += 1) {
      current[j] = Math.min(
        previous[j] + 1,
        current[j - 1] + 1,
        previous[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1),
      )
    }
    previous = current
  }
  return previous[b.length]
}

function scoreWord(expected: string, heard: string): number {
  if (expected === heard) return 2
  if (expected.startsWith(heard) && heard.length >= 2) return 1
  if (heard.startsWith(expected) && expected.length >= 2) return 1
  if (Math.abs(expected.length - heard.length) <= 1 && levenshtein(expected, heard) <= 1) return 1
  return 0
}

export interface LiveAlignment {
  states: WordState[]
  cursor: number
  matched: number
}

/**
 * Align a partial transcript. Anything past the last word actually recognised
 * stays `pending` rather than `missed`, because the reader has not reached it
 * yet — calling it missed mid-recitation is a lie that shows up as a red word
 * jumping ahead of the voice.
 */
export function alignLive(expectedWords: string[], transcript: string): LiveAlignment {
  const expected = expectedWords.map((w) => normaliseArabic(w).replace(/\s+/g, '')).filter(Boolean)
  const heard = normaliseArabic(transcript).split(' ').filter(Boolean)
  const states: WordState[] = new Array(expected.length).fill('pending')

  if (!expected.length || !heard.length) {
    return { states, cursor: 0, matched: 0 }
  }

  const n = expected.length
  const m = heard.length
  const table: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0))
  for (let i = 1; i <= n; i += 1) table[i][0] = -i
  for (let j = 1; j <= m; j += 1) table[0][j] = -j

  for (let i = 1; i <= n; i += 1) {
    for (let j = 1; j <= m; j += 1) {
      const s = scoreWord(expected[i - 1], heard[j - 1])
      table[i][j] = Math.max(
        table[i - 1][j - 1] + s,
        table[i - 1][j] - 1,
        table[i][j - 1] - 1,
      )
    }
  }

  let i = n
  let j = m
  let lastMatched = -1
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0) {
      const s = scoreWord(expected[i - 1], heard[j - 1])
      if (table[i][j] === table[i - 1][j - 1] + s) {
        if (s > 0) {
          states[i - 1] = s === 2 ? 'correct' : 'close'
          if (lastMatched < 0) lastMatched = i - 1
        } else {
          states[i - 1] = 'missed'
        }
        i -= 1
        j -= 1
        continue
      }
    }
    if (i > 0 && table[i][j] === table[i - 1][j] - 1) {
      states[i - 1] = 'missed'
      i -= 1
      continue
    }
    j -= 1
  }

  for (let k = lastMatched + 1; k < n; k += 1) states[k] = 'pending'

  const cursor = states.findIndex((s) => s === 'pending' || s === 'missed')
  return {
    states,
    cursor: cursor === -1 ? n : cursor,
    matched: states.filter((s) => s === 'correct' || s === 'close').length,
  }
}

export type Engine = 'speech' | 'cloud' | 'none'

export function pickEngine(hasKey: boolean): Engine {
  if (speechSupported()) return 'speech'
  if (hasKey && typeof MediaRecorder !== 'undefined') return 'cloud'
  return 'none'
}

export interface LiveControls {
  engine: Engine
  listening: boolean
  states: WordState[]
  cursor: number
  transcript: string
  matched: number
  error: string | null
  start: () => void
  stop: () => void
  reset: () => void
}

const CHUNK_MS = 2200

export function useLiveRecitation(words: string[], apiKey: string, model: string): LiveControls {
  const signature = useMemo(() => words.join('|'), [words])
  const blank = useMemo<WordState[]>(
    () => new Array(words.length).fill('pending') as WordState[],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [signature],
  )

  const [states, setStates] = useState<WordState[]>(blank)
  const [cursor, setCursor] = useState(0)
  const [listening, setListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [matched, setMatched] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const statesRef = useRef<WordState[]>(blank)
  const recorderRef = useRef<Recogniser | null>(null)
  const mediaRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<number | null>(null)
  const busyRef = useRef(false)
  const aliveRef = useRef(false)

  const engine = pickEngine(Boolean(apiKey))

  const reset = useCallback(() => {
    statesRef.current = blank
    setStates(blank)
    setCursor(0)
    setTranscript('')
    setMatched(0)
    setError(null)
  }, [blank])

  // A new ayah means a clean slate; carrying old highlights across would score
  // the new verse against the previous recitation.
  useEffect(() => {
    reset()
  }, [signature, reset])

  const accept = useCallback(
    (text: string) => {
      const live = alignLive(words, text)
      const merged = live.states.map((s, idx) =>
        RANK[s] > RANK[statesRef.current[idx] ?? 'pending'] ? s : statesRef.current[idx] ?? 'pending',
      ) as WordState[]
      statesRef.current = merged
      setStates(merged)
      setTranscript(text)
      setMatched(merged.filter((s) => s === 'correct' || s === 'close').length)
      setCursor(merged.findIndex((s) => s === 'pending'))
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [signature],
  )

  const stop = useCallback(() => {
    aliveRef.current = false
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
    recorderRef.current?.stop()
    recorderRef.current = null
    if (mediaRef.current && mediaRef.current.state !== 'inactive') {
      mediaRef.current.stop()
    }
    mediaRef.current = null
    setListening(false)
  }, [])

  const startSpeech = useCallback(() => {
    const recogniser = createRecogniser('ar-SA', {
      onTranscript: (text) => {
        if (aliveRef.current) accept(text)
      },
      onError: (code) => {
        if (code === 'not-allowed' || code === 'service-not-allowed') {
          setError('Microphone access was blocked. Allow it in the browser, then try again.')
          stop()
        } else if (code === 'no-speech') {
          setError('I could not hear anything. Move closer to the mic.')
        } else if (code !== 'aborted') {
          setError(`The recogniser stopped (${code}).`)
        }
      },
      onEnd: () => {
        // Chrome ends the session after a pause; restart while the user is live.
        if (aliveRef.current) {
          try {
            recogniser?.start()
          } catch {
            /* already restarting */
          }
        }
      },
    })
    if (!recogniser) {
      setError('This browser has no speech recogniser.')
      return
    }
    recorderRef.current = recogniser
    recogniser.start()
  }, [accept, stop])

  const startCloud = useCallback(async () => {
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setError('Microphone access was blocked. Allow it in the browser, then try again.')
      return
    }

    const recorder = new MediaRecorder(stream, { mimeType: pickMime() })
    mediaRef.current = recorder
    chunksRef.current = []

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data)
    }

    const flush = async () => {
      if (busyRef.current || !chunksRef.current.length) return
      const blob = new Blob(chunksRef.current, { type: recorder.mimeType })
      if (blob.size < 4000) return
      busyRef.current = true
      try {
        const text = await transcribeArabic(blob, apiKey, model)
        if (text && aliveRef.current) accept(text)
      } catch {
        /* a dropped tick is not fatal; the next one carries the audio */
      } finally {
        busyRef.current = false
      }
    }

    recorder.start(500)
    timerRef.current = window.setInterval(() => {
      void flush()
    }, CHUNK_MS)

    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop())
      void flush()
    }
  }, [accept, apiKey, model])

  const start = useCallback(() => {
    if (listening) return
    if (engine === 'none') {
      setError(
        apiKey
          ? 'Live capture is unavailable in this browser.'
          : 'Live capture needs Chrome or Edge, or a Gemini key in Settings for iPhone.',
      )
      return
    }
    setError(null)
    aliveRef.current = true
    setListening(true)
    if (engine === 'speech') startSpeech()
    else void startCloud()
  }, [apiKey, engine, listening, startCloud, startSpeech])

  useEffect(() => stop, [stop])

  return { engine, listening, states, cursor, transcript, matched, error, start, stop, reset }
}

function pickMime(): string {
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg']
  for (const type of candidates) {
    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(type)) return type
  }
  return ''
}
