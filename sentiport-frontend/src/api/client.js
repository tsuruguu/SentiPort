// Bazowy adres backendu FastAPI. Na hakatonie backend działa lokalnie
// przez docker-compose na porcie 8000 (patrz docker-compose.yml).
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.status = status;
    this.payload = payload;
  }
}

/**
 * Wrapper na fetch ze wspólną obsługą błędów - backend zwraca błędy
 * biznesowe jako { error: "...", details: {...} } (patrz
 * register_exception_handlers w backendzie), więc wyciągamy z tego
 * czytelny komunikat zamiast gołego "Failed to fetch".
 */
async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    let payload = null;
    try {
      payload = await response.json();
    } catch {
      // odpowiedź nie była JSON-em (np. 502 z gołym tekstem)
    }
    const message = payload?.error || payload?.detail || `Błąd ${response.status}`;
    throw new ApiError(message, response.status, payload);
  }

  // Niektóre endpointy (download PDF) zwracają binarkę, nie JSON
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return response.json();
  }
  return response;
}

export const api = {
  get: (path) => request(path, { method: 'GET' }),
  post: (path, body) => request(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  patch: (path, body) => request(path, { method: 'PATCH', body: JSON.stringify(body) }),
};

export { ApiError };
