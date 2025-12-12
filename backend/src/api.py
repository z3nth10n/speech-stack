from __future__ import annotations

from typing import Optional

import anyio
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse

from tts_engine import VoiceCloneEngine


app = FastAPI(title="XTTS-v2 Voice Clone API", version="0.1")

# CORS para poder abrir el frontend desde otro puerto/origen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine: Optional[VoiceCloneEngine] = None


@app.on_event("startup")
def _startup() -> None:
    global engine
    engine = VoiceCloneEngine(
        model_name="tts_models/multilingual/multi-dataset/xtts_v2",
        work_dir="data",
        device=None,  # auto: cuda si existe
    )


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/voice/register")
async def register_voice(
    audio: UploadFile = File(...),
    warmup_text: str = Form(""),
    language: str = Form("es"),
    voice_id: str = Form(""),
):
    """
    Subes audio + warmup_text. El backend hace un primer tts_to_file
    usando speaker_wav + speaker=<voice_id> para cachear la voz.
    """
    if engine is None:
        raise HTTPException(status_code=500, detail="Engine no inicializado")

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio vacío")

    vid = voice_id.strip() or None

    try:
        vp = await anyio.to_thread.run_sync(
            engine.register_voice,
            audio_bytes,
            audio.filename or "ref.wav",
            warmup_text,
            language,
            vid,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error registrando voz: {e}")

    return JSONResponse(
        {
            "voice_id": vp.voice_id,
            "language": vp.language,
            "ready": True,
            "preview_url": f"/voice/{vp.voice_id}/preview",
        }
    )


@app.get("/voice/{voice_id}/status")
def voice_status(voice_id: str):
    if engine is None:
        raise HTTPException(status_code=500, detail="Engine no inicializado")
    return {"voice_id": voice_id, "ready": engine.is_ready(voice_id)}


@app.get("/voice/{voice_id}/preview")
def voice_preview(voice_id: str):
    if engine is None:
        raise HTTPException(status_code=500, detail="Engine no inicializado")
    vp = engine.get_profile(voice_id)
    if vp is None:
        raise HTTPException(status_code=404, detail="voice_id no registrado")
    try:
        data = open(vp.preview_wav_path, "rb").read()
    except Exception:
        raise HTTPException(status_code=500, detail="No se pudo leer preview.wav")
    return Response(content=data, media_type="audio/wav")


@app.post("/tts")
async def tts(
    voice_id: str = Form(...),
    text: str = Form(...),
    language: str = Form(""),
):
    if engine is None:
        raise HTTPException(status_code=500, detail="Engine no inicializado")

    try:
        wav_bytes = await anyio.to_thread.run_sync(
            engine.synthesize,
            voice_id,
            text,
            language or None,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="voice_id no registrado")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sintetizando: {e}")

    return Response(content=wav_bytes, media_type="audio/wav")
