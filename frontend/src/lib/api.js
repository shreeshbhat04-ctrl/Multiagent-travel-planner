const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

export { API_BASE_URL };

export async function fetchHealth() {
  const response = await fetch(`${API_BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }
  return response.json();
}

export async function streamPlanTrip({ message, threadId, signal, onThreadId, onEvent }) {
  const response = await fetch(`${API_BASE_URL}/plan/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      message,
      thread_id: threadId || null
    }),
    signal
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Planning request failed with status ${response.status}`);
  }

  const nextThreadId = response.headers.get("X-Thread-Id");
  if (nextThreadId && onThreadId) {
    onThreadId(nextThreadId);
  }

  if (!response.body) {
    throw new Error("Streaming is not available in this browser.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";

    for (const frame of frames) {
      const trimmed = frame.trim();
      if (!trimmed.startsWith("data:")) {
        continue;
      }

      const payload = trimmed.slice(5).trim();
      if (!payload) {
        continue;
      }

      try {
        const event = JSON.parse(payload);
        onEvent(event);
      } catch {
        onEvent({
          node: "error",
          sender: "System",
          content: `Malformed stream payload: ${payload}`,
          tool_calls: []
        });
      }
    }
  }

  if (buffer.trim().startsWith("data:")) {
    try {
      onEvent(JSON.parse(buffer.trim().slice(5).trim()));
    } catch {
      onEvent({
        node: "error",
        sender: "System",
        content: "Malformed trailing stream payload.",
        tool_calls: []
      });
    }
  }
}
