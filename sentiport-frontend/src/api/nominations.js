import { api, API_BASE_URL } from './client';

export const nominationsApi = {
  /** Lista nominacji ("Skrzynka") - opcjonalny filtr statusu, paginacja. */
  list: ({ status, limit = 50, offset = 0 } = {}) => {
    const params = new URLSearchParams({ limit, offset });
    if (status) params.set('status', status);
    return api.get(`/nominations/?${params.toString()}`);
  },

  /** Pełny widok jednej nominacji (Panel główny - "Sugestie AI" + dane statku). */
  getDetail: (nominationId) => api.get(`/nominations/${nominationId}`),

  /** Wywołuje Agenta #1 (ekstrakcja danych z maila). */
  extract: (nominationId) => api.post(`/nominations/${nominationId}/extract`),

  /** Wywołuje Agenta #2 (wzbogacenie historią statku). */
  enrichWithHistory: (nominationId) => api.post(`/nominations/${nominationId}/enrich-with-history`),

  /** TOP-3 rekomendowane nabrzeża dla tej nominacji. */
  recommendedBerths: (nominationId, topN = 3) =>
    api.get(`/nominations/${nominationId}/recommended-berths?top_n=${topN}`),

  /** Agent portowy zatwierdza konkretne nabrzeże ("Zaakceptuj zgłoszenie"). */
  assignBerth: (nominationId, berthId) =>
    api.post(`/nominations/${nominationId}/assign-berth`, { berth_id: berthId }),

  /** Zmiana statusu nominacji (np. "rejected" - "Przekieruj do innego portu"). */
  changeStatus: (nominationId, status) =>
    api.post(`/nominations/${nominationId}/status`, { status }),

  /** Częściowa edycja pól ("Poproś o uzupełnienie danych" loguje się tu, gdy agent poprawia dane). */
  updateFields: (nominationId, fields) =>
    api.patch(`/nominations/${nominationId}`, fields),

  /** Import maili z mailservera ("Skrzynka" - przycisk odświeżenia). */
  syncInbox: () => api.post('/mailbox/sync-inbox'),

  /** Link do pobrania załącznika PDF z maila (otwierany w nowej karcie, nie przez fetch). */
  attachmentDownloadUrl: (nominationId, attachmentId) =>
    `${API_BASE_URL}/nominations/${nominationId}/attachments/${attachmentId}/download`,
};
