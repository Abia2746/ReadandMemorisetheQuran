import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

type WordState = 'pending' | 'missed' | 'close' | 'correct'

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

  let previous = Array.from({ length: b.length + 1 }, (_, index) => index)
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
  if (expected === heard) return 3
  if (heard.length >= 2 && expected.startsWith(heard)) return 1
  if (expected.length >= 2 && heard.startsWith(expected)) return 1
  if (
    Math.min(expected.length, heard.length) >= 3
    && Math.abs(expected.length - heard.length) <= 1
    && levenshtein(expected, heard) <= 1
  ) return 1
  return -2
}

export interface LiveAlignment {
  /** Only recognized matches are marked. Unrecognized words remain pending. */
  states: WordState[]
  cursor: number
  matched: number
  activeIndex: number
}

/** Align speech-recognition text to this ayah. This is transcript matching, not phoneme or Tajweed assessment. */
export function alignLive(expectedWords: string[], transcript: string): LiveAlignment {
  const expected = expectedWords.map((word) => normaliseArabic(word).replace(/\s/g, '')).filter(Boolean)
  const heard = normaliseArabic(transcript).split(' ').filter(Boolean)
  const states: WordState[] = new Array(expected.length).fill('pending')

  if (!expected.length || !heard.length) {
    return { states, cursor: 0, matched: 0, activeIndex: -1 }
  }

  const n = expected.length
  const m = heard.length
  const table = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0))
  const trace = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(''))
  for (let i = 1; i <= n; i += 1) {
    table[i][0] = -i
    trace[i][0] = 'up'
  }
  for (let j = 1; j <= m; j += 1) {
    table[0][j] = -j
    trace[0][j] = 'left'
  }

  for (let i = 1; i <= n; i += 1) {
    for (let j = 1; j <= m; j += 1) {
      const wordScoreValue = scoreWord(expected[i - 1], heard[j - 1])
      const diagonal = table[i - 1][j - 1] + wordScoreValue
      const skipExpected = table[i - 1][j] - 1
      const skipHeard = table[i][j - 1] - 1
      const best = Math.max(diagonal, skipExpected, skipHeard)
      table[i][j] = best
      // Prefer a genuine word match; otherwise avoid turning noisy transcript
      // words into false misses during the live, partial-recognition phase.
      trace[i][j] = wordScoreValue > 0 && diagonal === best
        ? 'match'
        : skipExpected === best
          ? 'up'
          : 'left'
    }
  }

  let i = n
  let j = m
  let activeIndex = -1
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && trace[i][j] === 'match') {
      const value = scoreWord(expected[i - 1], heard[j - 1])
      states[i - 1] = value === 3 ? 'correct' : 'close'
      if (activeIndex < 0) activeIndex = i - 1
      i -= 1
      j -= 1
    } else if (i > 0 && (j === 0 || trace[i][j] === 'up')) {
      i -= 1
    } else {
      j -= 1
    }
  }

  const cursor = states.findIndex((state) => state === 'pending')
  return {
    states,
    cursor: cursor === -1 ? n : cursor,
    matched: states.filter((state) => state === 'correct' || state === 'close').length,
    activeIndex,
  }
}

export type Engine = 'browser-speech' | 'unavailable'
export type LiveStatus = 'idle' | 'connecting' | 'listening' | 'stopped' | 'unavailable' | 'error'

export function speechSupported(): boolean {
  if (typeof window === 'undefined') return false
  const speechWindow = window as Window & {
    SpeechRecognition?: unknown
    webkitSpeechRecognition?: unknown
  }
  return Boolean(speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition)
}

interface RecognitionResultLike {
  0: { transcript: string }
  isFinal: boolean
}

interface RecognitionEventLike {
  results: ArrayLike<RecognitionResultLike>
}

interface RecognitionErrorLike {
  error: string
}

interface SpeechRecognitionLike {
  lang: string
  continuous: boolean
  interimResults: boolean
  onstart: (() => void) | null
  onresult: ((event: RecognitionEventLike) => void) | null
  onerror: ((event: RecognitionErrorLike) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
  abort: () => void
}

interface SpeechRecognitionWindow extends Window {
  SpeechRecognition?: new () => SpeechRecognitionLike
  webkitSpeechRecognition?: new () => SpeechRecognitionLike
}

export interface LiveControls {
  engine: Engine
  status: LiveStatus
  statusMessage: string
  listening: boolean
  states: WordState[]
  cursor: number
  activeIndex: number
  transcript: string
  matched: number
  error: string | null
  start: () => void
  stop: () => void
  reset: () => void
}

export function useLiveRecitation(words: string[]): LiveControls {
  const signature = useMemo(() => words.join('|'), [words])
  const expectedWords = useMemo(() => words, [signature])
  const blank = useMemo<WordState[]>(
    () => new Array(words.length).fill('pending') as WordState[],
    [signature, words.length],
  )

  const [states, setStates] = useState<WordState[]>(blank)
  const [cursor, setCursor] = useState(0)
  const [activeIndex, setActiveIndex] = useState(-1)
  const [listening, setListening] = useState(false)
  const [status, setStatus] = useState<LiveStatus>('idle')
  const [transcript, setTranscript] = useState('')
  const [matched, setMatched] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const keepAliveRef = useRef(false)
  const restartTimerRef = useRef<number | null>(null)

  const reset = useCallback(() => {
    setStates(blank)
    setCursor(0)
    setActiveIndex(-1)
    setTranscript('')
    setMatched(0)
    setError(null)
    setStatus('idle')
  }, [blank])

  useEffect(() => {
    keepAliveRef.current = false
    if (restartTimerRef.current !== null) {
      window.clearTimeout(restartTimerRef.current)
      restartTimerRef.current = null
    }
    recognitionRef.current?.abort()
    recognitionRef.current = null
    setListening(false)
    reset()
  }, [signature, reset])

  const acceptTranscript = useCallback((text: string) => {
    const alignment = alignLive(expectedWords, text)
    setStates(alignment.states)
    setCursor(alignment.cursor)
    setActiveIndex(alignment.activeIndex)
    setTranscript(text)
    setMatched(alignment.matched)
  }, [expectedWords])

  const stop = useCallback(() => {
    keepAliveRef.current = false
    if (restartTimerRef.current !== null) {
      window.clearTimeout(restartTimerRef.current)
      restartTimerRef.current = null
    }
    const recognition = recognitionRef.current
    recognitionRef.current = null
    if (recognition) {
      try { recognition.stop() } catch { /* recognition may already have ended */ }
    }
    setListening(false)
    setStatus('stopped')
  }, [])

  const start = useCallback(() => {
    if (keepAliveRef.current) return
    setError(null)
    setTranscript('')
    setStates(blank)
    setMatched(0)
    setCursor(0)
    setActiveIndex(-1)

    if (typeof window === 'undefined' || !navigator.mediaDevices) {
      setStatus('unavailable')
      setError('Microphone capture is unavailable in this browser or page context.')
      return
    }

    const speechWindow = window as SpeechRecognitionWindow
    const Recognition = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition
    if (!Recognition) {
      setStatus('unavailable')
      setError('Live highlighting is not supported by this browser. No cloud-recognition service is configured, so audio will not be sent or falsely marked as recognized.')
      return
    }

    let recognition: SpeechRecognitionLike
    try {
      recognition = new Recognition()
    } catch {
      setStatus('error')
      setError('This browser could not create a speech-recognition session.')
      return
    }

    recognition.lang = 'ar-SA'
    recognition.continuous = true
    recognition.interimResults = true
    recognitionRef.current = recognition
    keepAliveRef.current = true
    setStatus('connecting')

    recognition.onstart = () => {
      if (keepAliveRef.current) {
        setListening(true)
        setStatus('listening')
      }
    }

    recognition.onresult = (event) => {
      if (!keepAliveRef.current) return
      const chunks: string[] = []
      for (let index = 0; index < event.results.length; index += 1) {
        const result = event.results[index]
        if (result?.[0]?.transcript) chunks.push(result[0].transcript)
      }
      const text = chunks.join(' ').trim()
      if (text) acceptTranscript(text)
    }

    recognition.onerror = (event) => {
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        keepAliveRef.current = false
        setListening(false)
        setStatus('error')
        setError('Microphone or speech-recognition permission was denied. Allow access in browser settings and try again.')
      } else if (event.error === 'audio-capture') {
        keepAliveRef.current = false
        setListening(false)
        setStatus('error')
        setError('The browser could not access a microphone. Check iPad/browser microphone permissions.')
      } else if (event.error === 'network') {
        setStatus('error')
        setError('The browser speech-recognition service lost its network connection. Stop and retry when online.')
      } else if (event.error !== 'no-speech' && event.error !== 'aborted') {
        setStatus('error')
        setError(`Speech recognition failed (${event.error}). No words were inferred.`)
      }
    }

    recognition.onend = () => {
      if (recognitionRef.current !== recognition) return
      if (!keepAliveRef.current) {
        recognitionRef.current = null
        setListening(false)
        if (status !== 'error') setStatus('stopped')
        return
      }
      // Some browser engines close recognition after pauses; show a reconnecting
      // state and retry without claiming the recognizer stayed continuously live.
      setListening(false)
      setStatus('connecting')
      restartTimerRef.current = window.setTimeout(() => {
        restartTimerRef.current = null
        if (!keepAliveRef.current || recognitionRef.current !== recognition) return
        try { recognition.start() } catch {
          keepAliveRef.current = false
          recognitionRef.current = null
          setStatus('error')
          setError('The browser speech recognizer could not reconnect. Stop and start again.')
        }
      }, 350)
    }

    try {
      recognition.start()
    } catch {
      keepAliveRef.current = false
      recognitionRef.current = null
      setStatus('error')
      setError('The browser could not start speech recognition. Check microphone permission and retry.')
    }
  }, [acceptTranscript, blank, status])

  useEffect(() => () => {
    keepAliveRef.current = false
    if (restartTimerRef.current !== null) window.clearTimeout(restartTimerRef.current)
    try { recognitionRef.current?.abort() } catch { /* unmount cleanup */ }
    recognitionRef.current = null
  }, [])

  const engine: Engine = speechSupported() ? 'browser-speech' : 'unavailable'
  const statusMessage = status === 'connecting'
    ? 'Connecting to browser speech recognition…'
    : status === 'listening'
      ? 'Listening with browser Arabic speech recognition. Highlights reflect recognized transcript matches, not word timing.'
      : status === 'stopped'
        ? 'Stopped. Unhighlighted words may be recognition errors or unspoken; this is not a Tajweed assessment.'
        : status === 'error'
          ? error ?? 'Speech recognition failed.'
          : status === 'unavailable'
            ? error ?? 'Live recognition is unavailable.'
            : 'Ready. Start to check whether this browser supports live Arabic speech recognition.'

  return { engine, status, statusMessage, listening, states, cursor, activeIndex, transcript, matched, error, start, stop, reset }
}
