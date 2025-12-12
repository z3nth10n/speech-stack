from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional

import torch
from TTS.api import TTS


# XTTS-v2 soporta (al menos) estos idiomas según docs (puede ampliarse con versiones futuras). :contentReference[oaicite:4]{index=4}
SUPPORTED_LANGS = {
    "en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko"
}


@dataclass
class VoiceProfile:
    voice_id: str
    ref_audio_path: str
    language: str
    preview_wav_path: str


class VoiceCloneEngine:
    """
    Motor de clonación + síntesis con Coqui TTS + XTTS-v2.
    - register_voice(): crea/cacha la voz usando speaker_wav + speaker_id (caché)
    - synthesize(): genera audio usando speaker_id (sin volver a pasar speaker_wav)
    """

    def __init__(
        self,
        model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2",
        work_dir: str = "data",
        device: Optional[str] = None,
    ) -> None:
        self.model_name = model_name
        self.work_dir = Path(work_dir)
        self.voices_dir = self.work_dir / "voices"
        self.voices_dir.mkdir(parents=True, exist_ok=True)

        self._index_path = self.voices_dir / "index.json"
        self._lock = threading.Lock()

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device

        # Carga del modelo (Coqui TTS API). :contentReference[oaicite:5]{index=5}
        # Nota: Coqui permite .to(device) y/o gpu=True en constructor según docs.
        self.tts = TTS(self.model_name).to(self.device)

        self._voices: Dict[str, VoiceProfile] = {}
        self._load_index()

    def _load_index(self) -> None:
        if not self._index_path.exists():
            return
        try:
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
            for item in data.get("voices", []):
                vp = VoiceProfile(**item)
                # mantenemos el índice aunque el caché interno de Coqui viva en su carpeta de modelo
                self._voices[vp.voice_id] = vp
        except Exception:
            # si se corrompe el index, no rompemos el arranque
            self._voices = {}

    def _save_index(self) -> None:
        payload = {"voices": [asdict(v) for v in self._voices.values()]}
        self._index_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def create_voice_id(self) -> str:
        return uuid.uuid4().hex

    def is_ready(self, voice_id: str) -> bool:
        return voice_id in self._voices

    def get_profile(self, voice_id: str) -> Optional[VoiceProfile]:
        return self._voices.get(voice_id)

    def register_voice(
        self,
        ref_audio_bytes: bytes,
        ref_filename: str,
        warmup_text: str,
        language: str = "es",
        voice_id: Optional[str] = None,
        split_sentences: bool = True,
    ) -> VoiceProfile:
        """
        Crea el "perfil de voz" y fuerza el caché de Coqui:
        tts_to_file(... speaker_wav=[ref], speaker=<voice_id> ...)
        Esto deja la voz cacheada bajo ese speaker ID para usos posteriores. :contentReference[oaicite:6]{index=6}
        """
        if not warmup_text.strip():
            warmup_text = "Hola. Esta es una prueba de clonación de voz."

        language = (language or "es").strip().lower()
        if language not in SUPPORTED_LANGS:
            # permitimos igualmente, pero avisamos por si el usuario mete algo raro
            # (Coqui puede fallar si el código no coincide con los soportados por XTTS-v2)
            raise ValueError(f"Idioma no soportado por XTTS-v2 (según docs): {language}")

        if voice_id is None:
            voice_id = self.create_voice_id()

        voice_folder = self.voices_dir / voice_id
        voice_folder.mkdir(parents=True, exist_ok=True)

        # Guardamos el audio tal cual lo subes (ideal: WAV). Si subes MP3 y tu entorno no tiene decoder,
        # puede fallar al leerlo.
        ref_path = voice_folder / f"ref_{Path(ref_filename).name}"
        ref_path.write_bytes(ref_audio_bytes)

        preview_path = voice_folder / "preview.wav"

        # El modelo no suele ser thread-safe: serializamos por lock.
        with self._lock:
            # Warmup + caché por speaker ID (clave para “ya está listo”). :contentReference[oaicite:7]{index=7}
            self.tts.tts_to_file(
                text=warmup_text,
                file_path=str(preview_path),
                speaker_wav=[str(ref_path)],
                speaker=voice_id,
                language=language,
                split_sentences=split_sentences,
            )

        vp = VoiceProfile(
            voice_id=voice_id,
            ref_audio_path=str(ref_path),
            language=language,
            preview_wav_path=str(preview_path),
        )
        self._voices[voice_id] = vp
        self._save_index()
        return vp

    def synthesize(
        self,
        voice_id: str,
        text: str,
        language: Optional[str] = None,
        split_sentences: bool = True,
    ) -> bytes:
        """
        Genera WAV (bytes) usando el speaker cacheado.
        """
        vp = self._voices.get(voice_id)
        if vp is None:
            raise KeyError("voice_id no registrado")

        if not text.strip():
            raise ValueError("Texto vacío")

        lang = (language or vp.language).strip().lower()

        out_path = (self.voices_dir / voice_id / "last_output.wav")

        with self._lock:
            # Reutilización del speaker cacheado: NO volvemos a pasar speaker_wav. :contentReference[oaicite:8]{index=8}
            self.tts.tts_to_file(
                text=text,
                file_path=str(out_path),
                speaker=voice_id,
                language=lang,
                split_sentences=split_sentences,
            )

        return out_path.read_bytes()
