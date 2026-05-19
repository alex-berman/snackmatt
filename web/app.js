const statusEl = document.getElementById("status");
const transcriptEl = document.getElementById("transcript");
const recordBtn = document.getElementById("recordBtn");
const ttsBtn = document.getElementById("ttsBtn");
const player = document.getElementById("player");

let mediaRecorder = null;
let chunks = [];
let stream = null;

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

function setStatus(text, kind = "") {
  statusEl.textContent = text;
  statusEl.className = "status" + (kind ? ` ${kind}` : "");
}

/** Browsers only expose mediaDevices in a secure context (HTTPS or localhost). */
function getMicBlockReason() {
  const { protocol, hostname } = window.location;

  if (protocol === "file:") {
    return "Öppna sidan via servern (t.ex. https://localhost:8000), inte som en lokal fil.";
  }

  const onLocalhost = LOCAL_HOSTS.has(hostname);
  if (!window.isSecureContext && !onLocalhost) {
    if (hostname === "0.0.0.0") {
      return "Använd https://localhost:8000 eller https://127.0.0.1:8000 — inte 0.0.0.0.";
    }
    return (
      `Mikrofon kräver HTTPS eller localhost. Du är på ${protocol}//${hostname}. ` +
      "På datorn: https://localhost:8000. På telefonen: HTTPS mot datorns IP (se README)."
    );
  }

  if (!navigator.mediaDevices?.getUserMedia) {
    return "Webbläsaren stödjer inte mikrofon här. Prova Chrome eller Firefox.";
  }

  return null;
}

function requestMicrophone() {
  const block = getMicBlockReason();
  if (block) {
    return Promise.reject(new Error(block));
  }
  return navigator.mediaDevices.getUserMedia({ audio: true });
}

async function ensureMic() {
  if (stream) return stream;
  stream = await requestMicrophone();
  return stream;
}

function initMicUi() {
  const block = getMicBlockReason();
  if (block) {
    recordBtn.disabled = true;
    setStatus(block, "error");
    return;
  }
  recordBtn.disabled = false;
}

function pickMimeType() {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
  ];
  return candidates.find((t) => MediaRecorder.isTypeSupported(t)) || "";
}

async function startRecording() {
  const mic = await ensureMic();
  const mimeType = pickMimeType();
  chunks = [];
  mediaRecorder = new MediaRecorder(mic, mimeType ? { mimeType } : undefined);
  mediaRecorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };
  mediaRecorder.start();
  recordBtn.classList.add("recording");
  setStatus("Lyssnar…", "busy");
}

async function stopRecordingAndEcho() {
  if (!mediaRecorder || mediaRecorder.state === "inactive") return;

  await new Promise((resolve) => {
    mediaRecorder.onstop = resolve;
    mediaRecorder.stop();
  });

  recordBtn.classList.remove("recording");
  setStatus("Tänker…", "busy");

  const blob = new Blob(chunks, { type: mediaRecorder.mimeType || "audio/webm" });
  const ext = blob.type.includes("mp4") ? "m4a" : "webm";
  const form = new FormData();
  form.append("file", blob, `recording.${ext}`);

  try {
    const res = await fetch("/api/echo", { method: "POST", body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || res.statusText);
    }
    const transcript = res.headers.get("X-Transcript") || "";
    transcriptEl.hidden = false;
    transcriptEl.textContent = transcript ? `Du sa: ${transcript}` : "";
    const audioBlob = await res.blob();
    playBlob(audioBlob);
    setStatus("Klart! Lyssna på svaret.");
  } catch (err) {
    console.error(err);
    setStatus(err.message || "Något gick fel.", "error");
  } finally {
    recordBtn.disabled = false;
  }
}

function playBlob(blob) {
  const url = URL.createObjectURL(blob);
  player.hidden = false;
  player.src = url;
  player.play().catch(() => {});
}

recordBtn.addEventListener("pointerdown", async (e) => {
  e.preventDefault();
  recordBtn.disabled = true;
  try {
    await startRecording();
    recordBtn.disabled = false;
  } catch (err) {
    console.error(err);
    setStatus(err.message || "Mikrofonen fungerar inte. Tillåt mikrofon i webbläsaren.", "error");
    recordBtn.disabled = false;
  }
});

recordBtn.addEventListener("pointerup", () => stopRecordingAndEcho());
recordBtn.addEventListener("pointerleave", () => {
  if (mediaRecorder?.state === "recording") stopRecordingAndEcho();
});

ttsBtn.addEventListener("click", async () => {
  ttsBtn.disabled = true;
  setStatus("Spelar testfras…", "busy");
  try {
    const res = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: "Hej! Jag är din schackkompis." }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || res.statusText);
    }
    playBlob(await res.blob());
    setStatus("TTS-test klart.");
  } catch (err) {
    console.error(err);
    setStatus(err.message || "TTS misslyckades.", "error");
  } finally {
    ttsBtn.disabled = false;
  }
});

initMicUi();

fetch("/api/health")
  .then((r) => r.json())
  .then((data) => {
    if (getMicBlockReason()) return;
    if (!data.elevenlabs_configured) {
      setStatus("Server saknar API-nyckel — lägg till ELEVENLABS_API_KEY.", "error");
    }
  })
  .catch(() => {
    if (!getMicBlockReason()) setStatus("Kan inte nå servern.", "error");
  });
