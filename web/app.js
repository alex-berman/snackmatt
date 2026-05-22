const btn = document.getElementById("recordBtn");
const player = document.getElementById("player");

const IDLE = "idle", LISTENING = "listening", THINKING = "thinking", SPEAKING = "speaking";
const RECORD_DURATION = 7000;

let state = IDLE;
let mediaRecorder = null;
let chunks = [];
let stream = null;
let recordTimeout = null;

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

function setState(s) {
  state = s;
  btn.className = "btn " + s;
}

function micBlockReason() {
  const { protocol, hostname } = window.location;
  if (protocol === "file:") return "Öppna sidan via servern, inte som lokal fil.";
  if (!window.isSecureContext && !LOCAL_HOSTS.has(hostname)) {
    if (hostname === "0.0.0.0")
      return "Använd https://localhost:8000 eller https://127.0.0.1:8000.";
    return "Mikrofon kräver HTTPS eller localhost.";
  }
  if (!navigator.mediaDevices?.getUserMedia)
    return "Webbläsaren stödjer inte mikrofon här.";
  return null;
}

async function requestMic() {
  const reason = micBlockReason();
  if (reason) throw new Error(reason);
  return navigator.mediaDevices.getUserMedia({ audio: true });
}

async function ensureMic() {
  if (stream) return stream;
  stream = await requestMic();
  return stream;
}

function mimeType() {
  return ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"]
    .find((t) => MediaRecorder.isTypeSupported(t)) || "";
}

async function startListening() {
  const mic = await ensureMic();
  chunks = [];
  mediaRecorder = new MediaRecorder(mic, mimeType() ? { mimeType: mimeType() } : undefined);
  mediaRecorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };
  mediaRecorder.start();
  setState(LISTENING);
  recordTimeout = setTimeout(stopAndSend, RECORD_DURATION);
}

async function stopAndSend() {
  if (!mediaRecorder || mediaRecorder.state === "inactive") return;
  clearTimeout(recordTimeout);
  await new Promise((r) => { mediaRecorder.onstop = r; mediaRecorder.stop(); });
  sendAudio();
}

async function sendAudio() {
  setState(THINKING);
  const blob = new Blob(chunks, { type: mediaRecorder.mimeType || "audio/webm" });
  const ext = blob.type.includes("mp4") ? "m4a" : "webm";
  const form = new FormData();
  form.append("file", blob, "recording." + ext);
  try {
    const res = await fetch("/api/command", { method: "POST", body: form });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
    const audioBlob = await res.blob();
    if (audioBlob.size > 0) playAudio(audioBlob);
    else setState(IDLE);
  } catch (err) {
    console.error(err);
    setState(IDLE);
  }
}

function playAudio(blob) {
  setState(SPEAKING);
  const url = URL.createObjectURL(blob);
  player.src = url;
  player.onended = () => { URL.revokeObjectURL(url); setState(IDLE); };
  player.play().catch(() => setState(IDLE));
}

btn.addEventListener("click", async () => {
  if (state === IDLE) {
    btn.disabled = true;
    try {
      await startListening();
    } catch (err) {
      console.error(err);
    }
    btn.disabled = false;
  }
});

if (micBlockReason()) btn.disabled = true;
