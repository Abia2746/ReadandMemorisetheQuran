"""Private backend for Al-Mu'allim's live voice and Arabic-recitation page.

Run separately from Streamlit: uvicorn live_backend:app --host 0.0.0.0 --port 8000
The browser receives only short-lived OpenAI Realtime credentials. Provider API keys
and Google service-account credentials remain on this server.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Al-Mu'allim live audio API", version="1.0.0")
_origins = [x.strip() for x in os.getenv("ALLOWED_ORIGINS", "http://localhost:8501").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class RealtimeRequest(BaseModel):
    teacher: str = Field(pattern="^(Male|Female)$")
    ayah: str = Field(default="", max_length=4000)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "recitation": "google-cloud-speech"}


@app.post("/api/realtime/session")
async def create_realtime_session(request: RealtimeRequest) -> dict[str, str]:
    """Mint a short-lived Realtime client secret; never return the server API key."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Live teacher is not configured: OPENAI_API_KEY is missing.")

    voice = "cedar" if request.teacher == "Male" else "marin"
    ayah_context = f"The student is studying this Qur'an text: {request.ayah}" if request.ayah.strip() else ""
    body: dict[str, Any] = {
        "session": {
            "type": "realtime",
            "model": os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime"),
            "instructions": (
                "You are a warm, careful Qur'an learning companion. Speak naturally and concisely. "
                "Do not present yourself as a human or qualified religious authority. Never invent Qur'an text, "
                "Tajweed judgments, hadith, or rulings. If uncertain, say so and recommend checking with a "
                "qualified teacher. You may discuss the learner's recitation, but do not claim acoustic "
                "Tajweed assessment unless supported by evidence. " + ayah_context
            ),
            "audio": {
                "output": {"voice": voice},
                "input": {
                    "turn_detection": {
                        "type": "semantic_vad",
                        "create_response": True,
                        "interrupt_response": True,
                    }
                },
            },
        }
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.openai.com/v1/realtime/client_secrets",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
            )
        if response.is_error:
            # Keep provider response details out of the browser; it can include account metadata.
            raise HTTPException(status_code=502, detail="Realtime provider could not create a session. Check server configuration.")
        data = response.json()
        secret = (data.get("client_secret") or {}).get("value") or data.get("value")
        if not secret:
            raise HTTPException(status_code=502, detail="Realtime provider returned no temporary session credential.")
        return {"client_secret": secret}
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="Could not reach the realtime voice provider.") from exc


def _speech_client():
    """Build Google Speech client using ADC or a JSON service-account env var."""
    from google.cloud import speech_v1

    raw = os.getenv("GOOGLE_CLOUD_CREDENTIALS_JSON")
    if raw:
        from google.oauth2 import service_account

        credentials = service_account.Credentials.from_service_account_info(json.loads(raw))
        return speech_v1.SpeechAsyncClient(credentials=credentials), speech_v1
    return speech_v1.SpeechAsyncClient(), speech_v1


@app.websocket("/ws/recitation")
async def recitation_socket(websocket: WebSocket) -> None:
    """Stream mono 16-kHz PCM16 chunks to Google Speech and return interim/final Arabic text."""
    if not _origins or websocket.headers.get("origin") not in _origins:
        await websocket.close(code=1008, reason="Origin is not allowed")
        return
    try:
        client, speech = _speech_client()
    except Exception:
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": "Arabic speech recognition is not configured on the server."})
        await websocket.close(code=1011)
        return

    await websocket.accept()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=32)
    recognition_config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code=os.getenv("GOOGLE_SPEECH_LANGUAGE", "ar-SA"),
        model=os.getenv("GOOGLE_SPEECH_MODEL", "latest_long"),
        enable_automatic_punctuation=False,
    )
    streaming_config = speech.StreamingRecognitionConfig(config=recognition_config, interim_results=True)

    async def audio_requests():
        yield speech.StreamingRecognizeRequest(streaming_config=streaming_config)
        while True:
            audio = await queue.get()
            if audio is None:
                return
            yield speech.StreamingRecognizeRequest(audio_content=audio)

    async def receive_audio():
        try:
            while True:
                chunk = await websocket.receive_bytes()
                if len(chunk) > 64_000:
                    await websocket.send_json({"type": "error", "message": "Audio chunk exceeds the 2-second PCM limit."})
                    continue
                await queue.put(chunk)
        except WebSocketDisconnect:
            pass
        finally:
            await queue.put(None)

    async def send_transcripts():
        try:
            responses = await client.streaming_recognize(requests=audio_requests())
            async for response in responses:
                for result in response.results:
                    if not result.alternatives:
                        continue
                    alternative = result.alternatives[0]
                    await websocket.send_json({
                        "type": "transcript",
                        "text": alternative.transcript,
                        "final": bool(result.is_final),
                        "confidence": float(alternative.confidence),
                    })
        except WebSocketDisconnect:
            return
        except Exception:
            try:
                await websocket.send_json({"type": "error", "message": "Speech recognition stopped. Check server credentials, network and language support."})
            except Exception:
                pass
        finally:
            await client.close()

    reader = asyncio.create_task(receive_audio())
    writer = asyncio.create_task(send_transcripts())
    try:
        await asyncio.gather(reader, writer)
    finally:
        for task in (reader, writer):
            if not task.done():
                task.cancel()
        await asyncio.gather(reader, writer, return_exceptions=True)
