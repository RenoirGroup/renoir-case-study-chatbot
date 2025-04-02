async function sendMessage() {
  const input = document.getElementById("user-input");
  const chatBox = document.getElementById("chat-box");
  const message = input.value.trim();
  if (!message) return;

  // Add user message to chat
  chatBox.innerHTML += `<div class="chat-message user"><strong>You:</strong> ${message}</div>`;
  input.value = "";
  chatBox.scrollTop = chatBox.scrollHeight;

  // Send to backend
  const response = await fetch("/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ message })
  });

  const data = await response.json();
  const reply = data.reply;

  // Add bot reply
  chatBox.innerHTML += `<div class="chat-message bot"><strong>Bot:</strong> ${reply}</div>`;
  chatBox.scrollTop = chatBox.scrollHeight;
}

// ✅ Add Enter key support
document.getElementById("user-input").addEventListener("keydown", function (e) {
  if (e.key === "Enter") {
    e.preventDefault(); // avoid newline
    sendMessage();
  }
});
