export class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

const MODEL_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$/;

export function validateChat(body) {
  if (!body || typeof body !== 'object') throw new HttpError(400, 'Body must be a JSON object.');
  const { messages, model } = body;
  if (!Array.isArray(messages) || messages.length < 1 || messages.length > 30) {
    throw new HttpError(400, 'messages must be an array of 1-30 items.');
  }
  let total = 0;
  const clean = messages.map((m, i) => {
    if (!m || (m.role !== 'user' && m.role !== 'assistant') || typeof m.content !== 'string') {
      throw new HttpError(400, `messages[${i}] needs a role (user|assistant) and string content.`);
    }
    const content = m.content.trim();
    if (!content) throw new HttpError(400, `messages[${i}] is empty.`);
    if (content.length > 8000) throw new HttpError(400, `messages[${i}] is too long (max 8000 characters).`);
    total += content.length;
    return { role: m.role, content };
  });
  if (total > 60000) throw new HttpError(400, 'Conversation is too long. Start a new chat.');
  if (clean[clean.length - 1].role !== 'user') throw new HttpError(400, 'The last message must be from the user.');
  if (model != null && (typeof model !== 'string' || !MODEL_RE.test(model))) throw new HttpError(400, 'Invalid model id.');
  return { messages: clean, model: model || null };
}
