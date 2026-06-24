import { api, API_BASE_URL } from './client';

export const documentsApi = {
  generate: (nominationId) => api.post(`/documents/nominations/${nominationId}/generate`),
  list: (nominationId) => api.get(`/documents/nominations/${nominationId}/documents`),
  downloadUrl: (documentId) => `${API_BASE_URL}/documents/${documentId}/download`,
};
