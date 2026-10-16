// ---------- Voice: speech to text (microphone) and text to speech (listen) ----------
// Uses the browser's built-in speech features. Speaking to type works in Chrome and Edge.

const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
const VOICE_LANG = navigator.language || "en-US";

const MIC_ICON = `<svg viewBox="0 0 24 24" width="23" height="23"
     fill="none" stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round">
     <rect x="9" y="2" width="6" height="12" rx="3"></rect>
     <path d="M5 10a7 7 0 0 0 14 0"></path>
     <path d="M12 17v5M8 22h8"></path>
   </svg>`;

let recognition = null;
let recognizing = false;
let voiceError = false;
let startTimer = null;
let textBeforeSpeaking = "";

let speaking = false;
let speechToken = 0;

function setVoiceStatus(message) {
  $("voice-status").textContent = message;
}

function describeVoiceError(code) {
  if (code === "not-allowed" || code === "service-not-allowed") {
    return "Microphone access is blocked. Click the lock icon in the address bar, set Microphone to Allow, then reload the page.";
  }
  if (code === "no-speech") return "I didn't hear anything. Click the microphone and try again.";
  if (code === "audio-capture") return "No microphone was found. Check it is plugged in and selected in Windows sound settings.";
  if (code === "network") {
    return "Voice input could not reach the speech service. Check your internet, or open CYNA in Chrome or Edge.";
  }
  return "Voice input error: " + code;
}

// ---------- Microphone (speech to text) ----------
function updateMic() {
  const mic = $("mic-btn");
  mic.innerHTML = recognizing ? "■" : MIC_ICON;
  mic.classList.toggle("active", recognizing);
  mic.title = recognizing ? "Stop recording" : "Start speaking";
}

function setupRecognition() {
  if (!SpeechRecognitionAPI) {
    $("mic-btn").disabled = true;
    $("mic-btn").title = "Speaking to type needs Chrome or Edge";
    return;
  }

  recognition = new SpeechRecognitionAPI();
  recognition.lang = VOICE_LANG;
  recognition.interimResults = true;
  recognition.continuous = true;

  recognition.onstart = () => {
    clearTimeout(startTimer);
    recognizing = true;
    updateMic();
    setVoiceStatus("Listening... click the microphone again when you're done, then press Enter to send.");
  };

  recognition.onresult = (event) => {
    let spoken = "";
    for (let i = 0; i < event.results.length; i++) {
      spoken += event.results[i][0].transcript;
    }
    const input = $("message-input");
    input.value = (textBeforeSpeaking + " " + spoken).trim();
    input.dispatchEvent(new Event("input", { bubbles: true })); // refreshes the Send / waveform buttons
  };

  recognition.onerror = (event) => {
    console.log("Voice error:", event.error);
    if (event.error === "aborted") return;
    clearTimeout(startTimer);
    voiceError = true;
    setVoiceStatus(describeVoiceError(event.error));
  };

  recognition.onend = () => {
    clearTimeout(startTimer);
    recognizing = false;
    updateMic();
    if (!voiceError) setVoiceStatus("");
  };
}

function toggleVoice() {
  if (!recognition) {
    setVoiceStatus("Speaking to type needs Chrome or Edge. Open CYNA in one of them.");
    return;
  }

  if (recognizing) {
    recognition.stop();
    return;
  }

  stopSpeaking(); // so the microphone does not hear CYNA
  textBeforeSpeaking = $("message-input").value.trim();
  voiceError = false;
  setVoiceStatus("Starting the microphone... if a box asks, click Allow.");

  // If nothing starts within a few seconds, say so
  clearTimeout(startTimer);
  startTimer = setTimeout(() => {
    if (!recognizing && !voiceError) {
      setVoiceStatus(
        "The microphone did not start. Click the lock icon in the address bar and allow the microphone, or open CYNA in Chrome or Edge."
      );
    }
  }, 4000);

  try {
    recognition.start();
  } catch (err) {
    console.log("Voice start failed:", err);
    setVoiceStatus("Could not start the microphone: " + err.message);
  }
}

// When you send a message, stop listening and drop anything still being processed
function stopListening() {
  if (recognizing && recognition) recognition.abort();
}

// ---------- Listen (text to speech) ----------
function updateListen() {
  const button = $("voice-mode-btn");
  if (!button) return;

  button.classList.toggle("active", speaking);
  button.title = speaking ? "Stop speaking" : "Listen to CYNA's last answer";
}

// Removes Markdown marks so they are not read out loud
function speakable(text) {
  return text
    .replace(/```[\s\S]*?```/g, " code block ")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^\s*[-*\u2022]\s+/gm, "")
    .replace(/[*_`>]/g, "")
    .replace(/\n+/g, ". ");
}

function stopSpeaking() {
  speechToken += 1; // ignore events from the speech we are cancelling
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  speaking = false;
  updateListen();
}

function speak(text) {
  stopSpeaking();

  // Short pieces keep the browser from cutting long answers off
  const pieces = (speakable(text).match(/[^.!?\n]+[.!?]*/g) || [])
    .map((p) => p.trim())
    .filter(Boolean);
  if (pieces.length === 0) return;

  const token = speechToken;
  let remaining = pieces.length;
  const finished = () => {
    if (token !== speechToken) return;
    remaining -= 1;
    if (remaining <= 0) {
      speaking = false;
      updateListen();
    }
  };

  speaking = true;
  updateListen();

  pieces.forEach((piece) => {
    const utterance = new SpeechSynthesisUtterance(piece);
    utterance.lang = VOICE_LANG;
    utterance.onend = finished;
    utterance.onerror = finished;
    window.speechSynthesis.speak(utterance);
  });
}

function listenToLastAnswer() {
  if (!("speechSynthesis" in window)) {
    setVoiceStatus("Your browser cannot read text aloud.");
    return;
  }
  if (speaking) {
    stopSpeaking();
    return;
  }

  const answers = [...document.querySelectorAll("#messages .msg.assistant")].filter((b) => {
    const text = b.textContent.trim();
    return text && text !== "...";
  });
  if (answers.length === 0) return;

  if (recognizing) recognition.abort();
  setVoiceStatus("");
  speak(answers[answers.length - 1].textContent);
}

// ---------- Wiring ----------
setupRecognition();

$("mic-btn").onclick = toggleVoice;
$("voice-mode-btn").onclick = listenToLastAnswer;

const messageInput = $("message-input");
const sendButton = $("send-btn");
const voiceButton = $("voice-mode-btn");

// Send shows when there is text, the waveform (listen) button shows when the box is empty
function updateComposerButtons() {
  const hasText = messageInput.value.trim().length > 0;
  sendButton.classList.toggle("hidden", !hasText);
  voiceButton.classList.toggle("hidden", hasText);
}

messageInput.addEventListener("input", updateComposerButtons);
updateComposerButtons();

// The box is emptied by code after sending, which does not count as typing,
// so refresh the buttons right after a message is sent.
function afterSend() {
  stopListening();
  setTimeout(updateComposerButtons, 0);
}

sendButton.addEventListener("click", afterSend);
messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) afterSend();
});

// Stop talking and listening when you log out
new MutationObserver(() => {
  if ($("app-screen").classList.contains("hidden")) {
    stopSpeaking();
    stopListening();
  }
}).observe($("app-screen"), { attributes: true, attributeFilter: ["class"] });