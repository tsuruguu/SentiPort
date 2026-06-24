import { api } from './client';

export const portsApi = {
  list: () => api.get('/ports/'),
  berths: (portId) => api.get(`/ports/${portId}/berths`),
};
