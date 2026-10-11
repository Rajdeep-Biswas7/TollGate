// Incremental parser for Server-Sent Events frames ("data: {...}\n\n").
export function createSseParser(onEvent) {
  const decoder = new TextDecoder();
  let buffer = '';
  return {
    push(chunk) {
      buffer += typeof chunk === 'string' ? chunk : decoder.decode(chunk, { stream: true });
      let idx;
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const data = frame
          .split('\n')
          .filter((l) => l.startsWith('data:'))
          .map((l) => l.slice(5).trimStart())
          .join('\n');
        if (!data) continue; // comment / heartbeat frame
        try {
          onEvent(JSON.parse(data));
        } catch {
          /* ignore malformed frame */
        }
      }
    },
  };
}

export function sseFrame(event) {
  return `data: ${JSON.stringify(event)}\n\n`;
}
