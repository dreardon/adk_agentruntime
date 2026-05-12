const chat = document.getElementById("chat");
const wrapper = document.getElementById("chat-wrapper");
const input = document.getElementById("userInput");
const btn = document.getElementById("sendBtn");
let thinkingDiv = null;
let pendingAuthCall = null;
let currentUserId = "";
let currentSessionId = "";

function login() {
  const idInput = document.getElementById("loginUserId").value.trim();
  if (!idInput) return;
  currentUserId = idInput;
  document.cookie = "user_id=" + currentUserId + "; path=/";

  // Generate session ID
  currentSessionId = "session-" + Math.random().toString(36).substring(2, 15);

  document.getElementById("login-container").style.display = "none";
  document.getElementById("chat-wrapper").style.display = "block";
  document.getElementById("input-container").style.display = "block";

  document.getElementById("user-badge").innerText = currentUserId;
  document.getElementById("session-badge").innerText = currentSessionId;
  document.getElementById("user-info-container").style.display = "flex";

  input.focus();
  scroll();
}

const scroll = () => (wrapper.scrollTop = wrapper.scrollHeight);

async function resumeSession() {
  if (!pendingAuthCall) {
    return;
  }

  const authConfig = pendingAuthCall.args.authConfig || pendingAuthCall.args.auth_config;
  const payload = {
    user_id: currentUserId,
    session_id: currentSessionId,
    function_response: {
      name: "adk_request_credential",
      id: pendingAuthCall.id,
      response: authConfig,
    },
  };

  const cardId = "auth-card-" + pendingAuthCall.id;
  const authCard = document.getElementById(cardId);
  if (authCard) {
    authCard.remove();
  } else {
    const cards = document.querySelectorAll('.auth-card');
    cards.forEach((card) => card.remove());
  }

  pendingAuthCall = null;

  addThought("Authenticating with Gmail...");
  setThinking(true);

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    // Remove the thought message once the stream response starts
    const thoughts = document.querySelectorAll('.thought-container');
    if (thoughts.length > 0) thoughts[thoughts.length - 1].remove();

    await processStream(response);
  } catch (err) {
    setThinking(false);
    add("Error resuming mailbox session.", "agent");
  } finally {
    setThinking(false);
    input.disabled = false;
    btn.disabled = false;
    input.focus();
  }
}

function add(text, sender) {
  const container = document.createElement("div");
  container.className = `msg-container ${sender}`;

  const msgDiv = document.createElement("div");
  msgDiv.className = "msg";
  msgDiv.innerText = text;

  const metaDiv = document.createElement("div");
  metaDiv.className = "meta-info";
  metaDiv.innerText = sender === "user" ? "You • Just now" : "Agent • Just now";

  container.appendChild(msgDiv);
  container.appendChild(metaDiv);
  chat.appendChild(container);
  scroll();
  return container;
}

function addThought(text) {
  const container = document.createElement("div");
  container.className = "thought-container";
  container.innerHTML = `
    <span class="thought-icon">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
      </svg>
    </span>
    <span>${text}</span>
  `;
  chat.appendChild(container);
  scroll();
  return container;
}

function setThinking(active) {
  if (active) {
    if (thinkingDiv) return;
    thinkingDiv = document.createElement("div");
    thinkingDiv.className = "thinking-bubble";
    thinkingDiv.innerHTML = `
      <div class="dot-pulse">
        <div class="dot"></div>
        <div class="dot"></div>
        <div class="dot"></div>
      </div>
    `;
    chat.appendChild(thinkingDiv);
  } else if (thinkingDiv) {
    thinkingDiv.remove();
    thinkingDiv = null;
  }
  scroll();
}

async function processStream(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let currentAgentDiv = null;
  let currentAgentMeta = null;
  let fullText = "";
  let isAuthRequested = false;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop();

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const json = JSON.parse(line.slice(6).trim());
          if (json.content?.parts) {
            for (const p of json.content.parts) {
              const fc = p.functionCall || p.function_call;
              if (fc) {
                if (fc.name === "adk_request_credential") {
                  setThinking(false);
                  pendingAuthCall = fc;
                  isAuthRequested = true;

                  // Clean up and delete premature text apology bubble in this turn
                  if (currentAgentDiv) {
                    currentAgentDiv.parentElement.remove();
                    currentAgentDiv = null;
                    currentAgentMeta = null;
                    fullText = "";
                  }
                  const args = fc.args || {};
                  const authConfig = args.authConfig || args.auth_config;

                  if (!authConfig) {
                    console.error("Missing auth config:", args);
                    add("Error: OAuth credentials requested but missing configuration.", "agent");
                    continue;
                  }

                  const authUri = authConfig.exchangedAuthCredential?.oauth2?.authUri || authConfig.exchanged_auth_credential?.oauth2?.auth_uri;
                  const nonce = authConfig.exchangedAuthCredential?.oauth2?.nonce || authConfig.exchanged_auth_credential?.oauth2?.nonce;

                  if (nonce) {
                    document.cookie = "consent_nonce=" + nonce + "; path=/";
                  }

                  // Disable typing fields
                  input.disabled = true;
                  btn.disabled = true;

                  // Generate Cyber Auth Card
                  const authDiv = document.createElement("div");
                  authDiv.id = "auth-card-" + pendingAuthCall.id;
                  authDiv.className = "auth-card";

                  window.cancelAuth = function () {
                    if (pendingAuthCall) {
                      resumeSession();
                    }
                  };

                  window.openAuthPopup = function (url, buttonElement) {
                    if (buttonElement) {
                      buttonElement.innerText = "Authorizing...";
                      buttonElement.disabled = true;
                      const cancelBtn = buttonElement.nextElementSibling;
                      if (cancelBtn) cancelBtn.disabled = true;
                    }

                    const popup = window.open(url, "_blank");

                    if (!popup) {
                      alert("Popup Blocked! Please allowlist popups to link your Gmail.");
                      if (buttonElement) {
                        buttonElement.innerText = "Authorize";
                        buttonElement.disabled = false;
                        const cancelBtn = buttonElement.nextElementSibling;
                        if (cancelBtn) cancelBtn.disabled = false;
                      }
                    } else {
                      const timer = setInterval(() => {
                        if (popup.closed) {
                          clearInterval(timer);
                          if (pendingAuthCall) {
                            resumeSession();
                          }
                        }
                      }, 500);
                    }
                  };

                  authDiv.innerHTML = `
                    <div class="auth-header">
                      <div class="auth-warn-icon">🔐</div>
                      <h3>Mail Permission Required</h3>
                    </div>
                    <p>The agent needs security access to your email mailbox. Click below to link your Google Account securely via 3-Legged OAuth.</p>
                    <div class="auth-actions">
                      <button class="btn-auth-confirm" onclick="window.openAuthPopup('${authUri}', this)">Authorize</button>
                      <button class="btn-auth-cancel" onclick="window.cancelAuth()">Decline</button>
                    </div>
                  `;

                  chat.appendChild(authDiv);
                  scroll();
                  currentAgentDiv = null;
                } else {
                  if (json.partial === false) {
                    continue;
                  }
                  addThought(`Running tool: ${fc.name}`);
                  currentAgentDiv = null;
                }
              }

              if (p.text) {
                if (isAuthRequested) {
                  continue; // Ignore text generated during an auth block request
                }
                if (json.partial === false && fullText.length > 0) {
                  continue;
                }

                setThinking(false);
                if (!currentAgentDiv) {
                  const container = document.createElement("div");
                  container.className = "msg-container agent";

                  currentAgentDiv = document.createElement("div");
                  currentAgentDiv.className = "msg";

                  currentAgentMeta = document.createElement("div");
                  currentAgentMeta.className = "meta-info";
                  currentAgentMeta.innerText = "Agent • Just now";

                  container.appendChild(currentAgentDiv);
                  container.appendChild(currentAgentMeta);
                  chat.appendChild(container);
                  fullText = "";
                }

                fullText += p.text;
                currentAgentDiv.innerText = fullText;
              }
            }
          }
        } catch (e) {
          console.error("Error on SSE line:", line, e);
        }
      }
    }
    scroll();
  }
}

async function send() {
  const val = input.value.trim();
  if (!val) return;

  add(val, "user");
  input.value = "";
  input.disabled = true;
  btn.disabled = true;
  setThinking(true);

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: val,
        user_id: currentUserId,
        session_id: currentSessionId,
      }),
    });
    await processStream(response);
  } catch (err) {
    setThinking(false);
    add("Error linking with service backend.", "agent");
  } finally {
    setThinking(false);
    input.disabled = false;
    btn.disabled = false;
    input.focus();
  }
}

input.onkeypress = (e) => {
  if (e.key === "Enter") send();
};
