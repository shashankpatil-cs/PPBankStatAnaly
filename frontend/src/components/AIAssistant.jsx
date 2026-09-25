import React, { useState, useRef, useEffect } from "react";
import { chatWithAssistant } from "../api.js";

export default function AIAssistant() {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Hi! Ask me things like \"How much did I spend last month?\" or \"Who did I pay the most?\"" },
  ]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  const send = async () => {
    if (!input.trim() || sending) return;
    const userMsg = { role: "user", content: input };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setSending(true);
    setError("");
    try {
      const res = await chatWithAssistant(userMsg.content, conversationId);
      setConversationId(res.data.conversation_id);
      setMessages((m) => [...m, { role: "assistant", content: res.data.reply }]);
    } catch (err) {
      setError(err.response?.data?.detail || "The assistant couldn't respond.");
    } finally {
      setSending(false);
    }
  };

  return (
    <div>
      <h2>AI Financial Assistant</h2>
      <p className="muted">Answers are grounded in your actual stored transactions via function calling.</p>

      <div className="card">
        <div className="chat-window" ref={scrollRef}>
          {messages.map((m, i) => (
            <div key={i} className={`chat-msg ${m.role}`}>
              <div className="bubble">{m.content}</div>
            </div>
          ))}
          {sending && (
            <div className="chat-msg assistant">
              <div className="bubble muted">Thinking...</div>
            </div>
          )}
        </div>
        {error && <div className="error-text" style={{ marginBottom: 8 }}>{error}</div>}
        <div className="chat-input-row">
          <input
            placeholder="Ask about your spending..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
          />
          <button onClick={send} disabled={sending}>Send</button>
        </div>
      </div>
    </div>
  );
}
