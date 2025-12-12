const API_BASE = "http://localhost:9999";

const el = (id) => document.getElementById(id);

const btnRegister = el("btnRegister");
const btnSpeak = el("btnSpeak");

const refAudio = el("refAudio");
const warmupText = el("warmupText");
const langRegister = el("langRegister");

const registerStatus = el("registerStatus");
const previewAudio = el("previewAudio");

const voiceId = el("voiceId");
const langTTS = el("langTTS");
const ttsText = el("ttsText");

const ttsStatus = el("ttsStatus");
const outAudio = el("outAudio");

function setBusy(targetEl, isBusy, text) {
  targetEl.textContent = text;
  targetEl.classList.toggle("busy", isBusy);
}

btnRegister.addEventListener("click", async () => {
  try {
    if (!refAudio.files || refAudio.files.length === 0) {
      alert("Selecciona un audio de referencia.");
      return;
    }

    btnRegister.disabled = true;
    setBusy(registerStatus, true, "Clonando/caching... (puede tardar)");

    const fd = new FormData();
    fd.append("audio", refAudio.files[0]);
    fd.append("warmup_text", warmupText.value || "");
    fd.append("language", langRegister.value || "es");

    const res = await fetch(`${API_BASE}/voice/register`, {
      method: "POST",
      body: fd
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Error HTTP ${res.status}`);
    }

    const data = await res.json();

    voiceId.value = data.voice_id;
    btnSpeak.disabled = false;

    setBusy(registerStatus, false, `✅ Listo. voice_id=${data.voice_id}`);

    // Cargamos preview
    previewAudio.src = `${API_BASE}${data.preview_url}`;
    previewAudio.load();
  } catch (e) {
    console.error(e);
    setBusy(registerStatus, false, `❌ ${e.message}`);
    alert(e.message);
  } finally {
    btnRegister.disabled = false;
  }
});

btnSpeak.addEventListener("click", async () => {
  try {
    const vid = voiceId.value.trim();
    if (!vid) {
      alert("Primero registra una voz.");
      return;
    }
    const text = ttsText.value.trim();
    if (!text) {
      alert("Escribe un texto.");
      return;
    }

    btnSpeak.disabled = true;
    setBusy(ttsStatus, true, "Generando audio...");

    const fd = new FormData();
    fd.append("voice_id", vid);
    fd.append("text", text);
    fd.append("language", langTTS.value || "");

    const res = await fetch(`${API_BASE}/tts`, {
      method: "POST",
      body: fd
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Error HTTP ${res.status}`);
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    outAudio.src = url;
    outAudio.load();
    await outAudio.play();

    setBusy(ttsStatus, false, "✅ Audio listo.");
  } catch (e) {
    console.error(e);
    setBusy(ttsStatus, false, `❌ ${e.message}`);
    alert(e.message);
  } finally {
    btnSpeak.disabled = false;
  }
});
