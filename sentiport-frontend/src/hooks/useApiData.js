import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Hook do pobierania danych z API z obsługą loading/error.
 *
 * Chroni przed race condition: jeśli deps zmienią się szybko (np.
 * klikanie między portami w Nadbrzeżach, zanim poprzedni fetch się
 * zakończy), wynik "starszego" zapytania jest ignorowany, nawet jeśli
 * dotrze później niż nowsze - inaczej dane z poprzedniego wyboru
 * mogłyby nadpisać te z aktualnego (to było źródło "migania" nabrzeży).
 *
 * fetcher musi być stabilną referencją (useCallback) albo funkcją
 * zdefiniowaną poza renderem, inaczej wpadnie w nieskończoną pętlę.
 */
export function useApiData(fetcher, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const requestIdRef = useRef(0);

  const reload = useCallback(() => {
    const thisRequestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);
    fetcher()
      .then((result) => {
        if (thisRequestId === requestIdRef.current) {
          setData(result);
        }
        // jeśli to nie jest już najnowsze zapytanie, ignorujemy wynik -
        // nowsze zapytanie (lub jego wynik) ma priorytet
      })
      .catch((err) => {
        if (thisRequestId === requestIdRef.current) {
          setError(err);
        }
      })
      .finally(() => {
        if (thisRequestId === requestIdRef.current) {
          setLoading(false);
        }
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    reload();
  }, [reload]);

  return { data, loading, error, reload };
}