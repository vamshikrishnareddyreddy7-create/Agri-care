(function () {
  "use strict";
  var log = document.getElementById("chatLog");
  var input = document.getElementById("chatInput");
  var sendBtn = document.getElementById("sendBtn");
  var equipSel = document.getElementById("chatEquip");
  var micBtn = document.getElementById("micBtn");
  var langSel = document.getElementById("chatLang");
  var convList = document.getElementById("convList");
  var convSearch = document.getElementById("convSearch");
  var newChatBtn = document.getElementById("newChat");
  var clearBtn = document.getElementById("clearChat");
  var quickRow = document.getElementById("quickRow");

  var conversationId = window.CHAT_CONVERSATION_ID || null;
  var messages = (window.CHAT_MESSAGES || []).slice().reverse(); // oldest first
  var busy = false;

  var BOT_AV = '<span class="m-av"><svg viewBox="0 0 24 24" style="width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:2"><path d="M12 8a4 4 0 1 0 0-8 4 4 0 0 0 0 8z"/><path d="M4 21c0-4 4-7 8-7s8 3 8 7"/></svg></span>';

  function scrollDown() { log.scrollTop = log.scrollHeight; }

  function msgHtml(role, text, smallNote) {
    var div = document.createElement("div");
    div.className = "msg " + role;
    var avatar = role === "user" ? '<span class="m-av">YOU</span>' : BOT_AV;
    div.innerHTML = avatar + '<div class="bubble"></div>';
    div.querySelector(".bubble").textContent = text;
    if (smallNote) {
      var note = document.createElement("small");
      note.textContent = smallNote;
      div.querySelector(".bubble").appendChild(note);
    }
    log.appendChild(div);
    scrollDown();
    return div;
  }

  function addTyping() {
    var div = document.createElement("div");
    div.className = "msg bot typing";
    div.innerHTML = BOT_AV + '<div class="bubble"><span class="typing-dots"><i></i><i></i><i></i></span></div>';
    log.appendChild(div);
    scrollDown();
    return div;
  }

  function greet() {
    if (log.querySelector(".msg")) return;
    var div = document.createElement("div");
    div.className = "msg bot";
    div.innerHTML = BOT_AV + '<div class="bubble">Namaste! I am your AgriCare AI assistant. Tell me what is happening with a machine — for example "my tractor is making a strange sound" — or ask about maintenance, service schedules or AI predictions. You can write in English, Telugu or a mix of both.</div>';
    log.appendChild(div);
  }

  function renderMessages() {
    log.innerHTML = "";
    if (!messages.length) { greet(); return; }
    messages.forEach(function (m) {
      msgHtml(m.role === "assistant" ? "bot" : "user", m.content);
    });
  }

  function renderConversations(items, activeId) {
    convList.innerHTML = "";
    if (!items.length) {
      var empty = document.createElement("div");
      empty.className = "conv-empty";
      empty.textContent = "No chats yet";
      convList.appendChild(empty);
      return;
    }
    items.forEach(function (c) {
      var div = document.createElement("div");
      div.className = "conv-item" + (c.conversation_id === activeId ? " active" : "");
      div.dataset.id = c.conversation_id;
      var title = document.createElement("span");
      title.className = "conv-title";
      title.textContent = c.title || "New chat";
      var del = document.createElement("button");
      del.className = "conv-del";
      del.title = "Delete chat";
      del.setAttribute("aria-label", "Delete chat");
      del.innerHTML = '<svg viewBox="0 0 24 24"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>';
      div.appendChild(title);
      div.appendChild(del);
      convList.appendChild(div);
    });
  }

  function loadConversation(id) {
    API.getConversationMessages(id)
      .then(function (r) {
        conversationId = id;
        messages = (r.messages || []).slice();
        renderMessages();
        renderConversations(currentConvs, id);
        document.querySelectorAll(".conv-item").forEach(function (el) {
          el.classList.toggle("active", Number(el.dataset.id) === Number(id));
        });
        if (window.matchMedia("(max-width: 900px)").matches) toggleSide(false);
      })
      .catch(handleApiError);
  }

  function refreshConversations(selectId) {
    API.getConversations(convSearch ? convSearch.value.trim() : "")
      .then(function (r) {
        currentConvs = r.conversations || [];
        renderConversations(currentConvs, selectId !== undefined ? selectId : conversationId);
      })
      .catch(function () { /* sidebar is non-critical */ });
  }
  var currentConvs = [];

  function send(message) {
    if (busy) return;
    if (!message || !message.trim()) return;
    if (recording) stopRecognition();
    msgHtml("user", message.trim());
    input.value = "";
    input.style.height = "auto";
    var typing = addTyping();
    busy = true;
    sendBtn.disabled = true;
    API.chat(message.trim(), equipSel.value || null, langSel.value, conversationId)
      .then(function (r) {
        typing.remove();
        msgHtml("bot", r.answer || "");
        if (r.conversation_id) conversationId = r.conversation_id;
        messages.push({ role: "user", content: message.trim() });
        messages.push({ role: "assistant", content: r.answer || "" });
        refreshConversations(conversationId);
      })
      .catch(function (err) {
        typing.remove();
        msgHtml("bot", (err && err.status === 503)
          ? "I'm having trouble connecting to the AI assistant right now. Please try again in a moment."
          : "Sorry, I could not answer right now. " + ((err && err.message) || ""));
      })
      .finally(function () {
        busy = false;
        sendBtn.disabled = false;
        input.focus();
      });
  }

  sendBtn.addEventListener("click", function () { send(input.value); });
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input.value); }
  });
  input.addEventListener("input", function () {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 110) + "px";
  });

  document.querySelectorAll("[data-quick]").forEach(function (chip) {
    chip.addEventListener("click", function () { send(chip.dataset.quick); });
  });

  // ------------------------------------------------------------------
  //  Conversation sidebar
  // ------------------------------------------------------------------
  if (newChatBtn) {
    newChatBtn.addEventListener("click", function () {
      conversationId = null;
      messages = [];
      renderMessages();
      document.querySelectorAll(".conv-item").forEach(function (el) { el.classList.remove("active"); });
      if (window.matchMedia("(max-width: 900px)").matches) toggleSide(false);
      input.focus();
    });
  }

  if (convList) {
    convList.addEventListener("click", function (e) {
      var del = e.target.closest(".conv-del");
      var item = e.target.closest(".conv-item");
      if (!item) return;
      var id = Number(item.dataset.id);
      if (del) {
        confirmDialog({
          title: "Delete this chat?",
          message: "The conversation and all its messages will be permanently removed.",
          confirmText: "Delete",
          onConfirm: function () {
            API.deleteConversation(id).then(function () {
              if (id === conversationId) {
                conversationId = null;
                messages = [];
                renderMessages();
              }
              refreshConversations(id === conversationId ? null : conversationId);
              toast("Chat deleted.");
            }).catch(handleApiError);
          },
        });
        return;
      }
      if (id !== conversationId) loadConversation(id);
    });
  }

  var searchTimer = null;
  if (convSearch) {
    convSearch.addEventListener("input", function () {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(function () { refreshConversations(); }, 250);
    });
  }

  function toggleSide(force) {
    document.getElementById("convSide").classList.toggle("open", force);
  }
  var toggleBtn = document.getElementById("convToggle");
  if (toggleBtn) toggleBtn.addEventListener("click", function () { toggleSide(); });

  if (clearBtn) {
    clearBtn.addEventListener("click", function () {
      if (!conversationId) {
        toast("Nothing to clear — this chat is empty.", "info");
        return;
      }
      confirmDialog({
        title: "Clear this chat?",
        message: "All messages in this conversation will be removed.",
        confirmText: "Clear",
        onConfirm: function () {
          API.deleteConversation(conversationId).then(function () {
            conversationId = null;
            messages = [];
            renderMessages();
            refreshConversations(null);
            toast("Chat cleared.");
          }).catch(handleApiError);
        },
      });
    });
  }

  // ------------------------------------------------------------------
  //  Language selector (persisted per browser)
  // ------------------------------------------------------------------
  var LANG_KEY = "chatLang";
  var LANG_CODES = { en: "en-IN", hi: "hi-IN", kn: "kn-IN", te: "te-IN" };
  var PLACEHOLDERS = {
    en: "Ask about overheating, oil, engine problems, service schedules\u2026 (Enter to send)",
    hi: "\u0905\u0927\u093F\u0915 \u0917\u0930\u094D\u092E\u0940, \u0924\u0947\u0932, \u0907\u0902\u091C\u0928 \u0915\u0940 \u0938\u092E\u0938\u094D\u092F\u093E\u090F\u0901, \u0938\u0930\u094D\u0935\u093F\u0938 \u0938\u092E\u092F \u092A\u0942\u091B\u0947\u0902\u2026 (\u092D\u0947\u091C\u0928\u0947 \u0915\u0947 \u0932\u093F\u090F Enter)",
    kn: "\u0CA4\u0CC6\u0CB3\u0CBF\u0CAE\u0CA8, \u0CA4\u0CC8\u0CB2, \u0C8E\u0C82\u0C9C\u0CBF\u0CA8\u0CCD \u0CB8\u0CAE\u0CB8\u0CCD\u0CAF\u0CBE\u0C97\u0CB3\u0CC1, \u0CB8\u0CB0\u0CCD\u0CB5\u0CBF\u0CB8\u0CCD \u0CB5\u0CC7\u0CB3\u0CC6\u0C97\u0CB3\u0CA8\u0CCD\u0CA8\u0CC1 \u0C95\u0CC7\u0CB3\u0CBF\u0CB0\u0CBF\u2026 (\u0C95\u0CB3\u0CBF\u0CB8\u0CB2\u0CC1 Enter)",
    te: "\u0C05\u0C24\u0C3F \u0C35\u0CC7\u0C21\u0C3F, \u0C28\u0C40\u0C32, \u0C07\u0C02\u0C1C\u0C28\u0C4D \u0C38\u0C2E\u0C38\u0C4D\u0C2F\u0C32\u0C41, \u0C38\u0C30\u0C4D\u0C35\u0C40\u0C38\u0C4D \u0C38\u0C2E\u0C2F\u0C02 \u0C05\u0C21\u0C17\u0C02\u0C21\u0C3F\u2026 (\u0C2A\u0C02\u0C2A\u0C21\u0C3E\u0C32\u0C3F \u0C05\u0C28\u0C15\u0C41 Enter)",
  };
  try { langSel.value = localStorage.getItem(LANG_KEY) || "en"; } catch (e) { /* private mode */ }
  if (!langSel.value) langSel.value = "en";
  input.placeholder = PLACEHOLDERS[langSel.value] || PLACEHOLDERS.en;
  langSel.addEventListener("change", function () {
    try { localStorage.setItem(LANG_KEY, langSel.value); } catch (e) { /* ignore */ }
    if (recording) stopRecognition();
    input.placeholder = PLACEHOLDERS[langSel.value] || PLACEHOLDERS.en;
    input.focus();
  });

  // ------------------------------------------------------------------
  //  Voice input (Web Speech API)
  // ------------------------------------------------------------------
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  var recognition = null;
  var recording = false;
  var baseText = "";

  function stopRecognition() {
    if (recognition) { try { recognition.stop(); } catch (e) { /* ignore */ } }
    recording = false;
    micBtn.classList.remove("recording");
    micBtn.setAttribute("aria-pressed", "false");
    micBtn.title = "Voice input";
  }

  function handleResult(event) {
    var transcript = "";
    for (var i = event.resultIndex; i < event.results.length; i++) {
      if (event.results[i].isFinal) transcript += event.results[i][0].transcript;
    }
    if (!transcript) return;
    baseText = baseText ? baseText + " " + transcript : transcript;
    input.value = baseText;
    input.dispatchEvent(new Event("input"));
  }

  function startRecognition() {
    if (!SR) {
      toast("Voice input needs Chrome or Edge \u2014 this browser does not support the Web Speech API.", "info");
      return;
    }
    if (busy) { toast("Please wait for the current answer.", "info"); return; }
    if (!recognition) {
      recognition = new SR();
      recognition.continuous = true;
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.onresult = handleResult;
      recognition.onerror = function (e) {
        var messages = {
          "not-allowed": "Microphone access was blocked. Allow it in your browser settings.",
          "service-not-allowed": "Microphone access was blocked. Allow it in your browser settings.",
          "no-speech": "No speech detected \u2014 try again.",
          "audio-capture": "No microphone found.",
          "network": "Speech service network error \u2014 check your connection.",
        };
        toast(messages[e.error] || "Voice input error: " + e.error, "error");
        stopRecognition();
      };
      recognition.onend = function () {
        // Chrome fires onend after brief pauses even in continuous mode.
        if (recording) { try { recognition.start(); } catch (e) { /* already started */ } }
        else stopRecognition();
      };
    }
    baseText = input.value.trim();
    recognition.lang = LANG_CODES[langSel.value] || "en-IN";
    recognition.start();
    recording = true;
    micBtn.classList.add("recording");
    micBtn.setAttribute("aria-pressed", "true");
    micBtn.title = "Stop voice input";
  }

  micBtn.addEventListener("click", function () {
    if (recording) stopRecognition();
    else startRecognition();
  });

  // Preselect equipment from query param
  if (window.CHAT_EQUIPMENT_ID) equipSel.value = String(window.CHAT_EQUIPMENT_ID);

  renderMessages();
  refreshConversations();
})();
