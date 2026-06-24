import { useState, useEffect, useCallback } from 'react';

/**
 * Prosty hook do pobierania danych z API z obsługą loading/error.
 * fetcher musi być stabilną referencją (useCallback) albo funkcją
 * zdefiniowaną poza renderem, inaczej wpadnie w nieskończoną pętlę.
 */
export function useApiData(fetcher, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    fetcher()
      .then((result) => setData(result))
      .catch((err) => setError(err))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    reload();
  }, [reload]);

  return { data, loading, error, reload };
}
