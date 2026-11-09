# Al-Mu'allim: Qur'an study and live-audio studio

Al-Mu'allim is a Streamlit Qur'an study and memorisation app. The existing study workflow in `app.py` remains available; the multipage **Live Studio** adds a separate browser-WebRTC teacher and live Arabic-recognition session. API credentials remain on the backend, never in the browser or Streamlit page.

## What the Live Studio does (and does not do)

- **Live teacher:** WebRTC to the OpenAI Realtime API, using a short-lived client secret minted by the private FastAPI service. The browser streams the microphone directly to the provider; generated speech is not prerecorded. Semantic voice activity detection allows the student to interrupt. Male/Female selects the `cedar`/`marin` generated voice and the two supplied repository portraits.
- **Live recitation:** browser audio is downsampled to mono PCM16 at 16 kHz and streamed over WebSocket to Google Cloud Speech-to-Text. Interim and final Arabic transcripts are displayed. Word-by-word shading compares the evolving transcript with the optional ayah text entered in the sidebar.
- **Limits:** transcript alignment is approximate; interim results can change. Speech recognition mismatch is not proof of an omission or pronunciation error. The current integration does **not** make an acoustically validated Tajweed assessment or separate confirmed pronunciation errors from Tajweed errors. Consult a qualified Qur'an teacher for those judgments. No live feature is claimed to work until external services, HTTPS, browser permissions and provider access are configured and tested in the deployment environment.
- **Existing app:** the pre-existing lesson, tafsir, reciter, memorisation planner and request/response coach remain in `app.py` without being replaced.

## Requirements

- Python 3.10+ and the packages in `requirements.txt`.
- OpenAI API account/project with Realtime API access and an API key.
- Google Cloud project with Speech-to-Text enabled, billing configured, and credentials authorized for streaming recognition in Arabic (`ar-SA` by default). Confirm the selected recognition model and language availability in your Cloud region.
- HTTPS for the deployed Streamlit site and the API service. Browser microphone APIs do not work on ordinary remote HTTP origins. Configure CORS to allow the exact Streamlit origin.
- Existing features in `app.py` may additionally require `GEMINI_API_KEY` and `ELEVENLABS_API_KEY` in Streamlit secrets (or adapt existing configuration to environment variables). These are independent of the live studio.

## Local setup

Install dependencies and run both services in separate terminals:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt

# Terminal 1: private API/backend. Never expose this port publicly without TLS and access controls.
export OPENAI_API_KEY="..."
export GOOGLE_CLOUD_PROJECT="your-google-cloud-project"
export GOOGLE_APPLICATION_CREDENTIALS="/secure/path/service-account.json"
export ALLOWED_ORIGINS="http://localhost:8501"
uvicorn live_backend:app --host 127.0.0.1 --port 8000

# Terminal 2: Streamlit UI
export AL_MUALLIM_API_URL="http://localhost:8000"
streamlit run app.py
```

Alternatively provide Google credentials as `GOOGLE_CLOUD_CREDENTIALS_JSON` (the JSON service-account document). Do not commit credentials. Optional settings: `OPENAI_REALTIME_MODEL` (defaults to `gpt-realtime`), `GOOGLE_SPEECH_LANGUAGE` (defaults to `ar-SA`), and `GOOGLE_SPEECH_MODEL` (defaults to `latest_long`).

In Streamlit Community Cloud, set `AL_MUALLIM_API_URL` to the separately deployed HTTPS backend. Add `OPENAI_API_KEY`, Google credentials and `ALLOWED_ORIGINS` to the backend host's secret environment, and allow the exact deployed Streamlit origin. Streamlit secrets may be used for Streamlit-only keys, but the live API keys belong on the backend host. Do not embed keys in page HTML or browser JavaScript.

## Deployment and diagnostics

Deploy the Streamlit and FastAPI services separately; the Streamlit Community Cloud process does not automatically run `live_backend.py`. Put the API behind HTTPS, configure origin allowlisting and service authentication/rate limits at the gateway before public launch. The `/health` endpoint checks that the backend process is up, not that provider credentials work. Google credentials need Speech-to-Text permissions; OpenAI key must have Realtime access. Browser users must grant microphone permissions. Network/firewall must permit HTTPS/WSS.

From the repository root, run:

```bash
pytest -q
python -m compileall -q app.py live_backend.py pages tests
python -c "import live_backend; print(live_backend.app.title)"
```

Then manually verify `/health`, the page load, microphone allow/deny and stop paths, live teacher connect/speak/interruption/disconnect, and Arabic interim/final transcript streaming with a real browser and configured providers. These live provider and browser flows cannot be verified in an offline repository-edit session; passing unit/import checks alone must not be reported as proof that production real-time audio works.

## Data and safety

Audio is sent to OpenAI Realtime during teacher sessions and to Google Cloud Speech-to-Text during recitation sessions. Review the providers' current retention, regional processing, consent and billing terms before deployment. This educational tool is not a certified Tajweed assessment or religious authority.
