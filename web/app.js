const recordBtn = document.getElementById("recordBtn");
const player = document.getElementById("player");

let mediaRecorder = null;
let chunks = [];
let stream = null;

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

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
      "På datorn: https://localhost:8000. På telefonen: HTTPS mot datorns IP."
    );
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    return "Webbläsaren stödjer inte mikrofon här. Prova Chrome eller Firefox.";
  }
  return null;
}

function requestMicrophone() {
  const block = getMicBlockReason();
  if (block) return Promise.reject(new Error(block));
  return navigator.mediaDevices.getUserMedia({ audio: true });
}

async function ensureMic() {
  if (stream) return stream;
  stream = await requestMicrophone();
  return stream;
}

function initMicUi() {
  recordBtn.disabled = !!getMicBlockReason();
}

function pickMimeType() {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
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
}

async function stopRecordingAndSend() {
  if (!mediaRecorder || mediaRecorder.state === "inactive") return;

  await new Promise((resolve) => {
    mediaRecorder.onstop = resolve;
    mediaRecorder.stop();
  });

  recordBtn.classList.remove("recording");

  const blob = new Blob(chunks, { type: mediaRecorder.mimeType || "audio/webm" });
  const ext = blob.type.includes("mp4") ? "m4a" : "webm";
  const form = new FormData();
  form.append("file", blob, `recording.${ext}`);

  try {
    const res = await fetch("/api/command", { method: "POST", body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || res.statusText);
    }
    const audioBlob = await res.blob();
    if (audioBlob.size > 0) playBlob(audioBlob);
  } catch (err) {
    console.error(err);
  } finally {
    recordBtn.disabled = false;
  }
}

function playBlob(blob) {
  const url = URL.createObjectURL(blob);
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
    recordBtn.disabled = false;
  }
});

recordBtn.addEventListener("pointerup", () => stopRecordingAndSend());
recordBtn.addEventListener("pointerleave", () => {
  if (mediaRecorder?.state === "recording") stopRecordingAndSend();
});

initMicUi();
