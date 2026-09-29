"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "@/lib/api";

interface QueryState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
  setData: (updater: T | ((prev: T | null) => T | null)) => void;
}

interface Result<T> {
  key: string;
  data: T | null;
  error: string | null;
}

export function useQuery<T>(fetcher: () => Promise<T>, deps: unknown[]): QueryState<T> {
  const [tick, setTick] = useState(0);
  const key = `${JSON.stringify(deps)}#${tick}`;
  const [result, setResult] = useState<Result<T>>({ key: "", data: null, error: null });
  const fetcherRef = useRef(fetcher);

  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  useEffect(() => {
    let cancelled = false;
    fetcherRef
      .current()
      .then((data) => {
        if (!cancelled) setResult({ key, data, error: null });
      })
      .catch((err: unknown) => {
        if (!cancelled) setResult((prev) => ({ key, data: prev.data, error: errorMessage(err) }));
      });
    return () => {
      cancelled = true;
    };
  }, [key]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  const setData = useCallback((updater: T | ((prev: T | null) => T | null)) => {
    setResult((prev) => ({
      ...prev,
      data: typeof updater === "function" ? (updater as (p: T | null) => T | null)(prev.data) : updater,
    }));
  }, []);

  return { data: result.data, error: result.error, loading: result.key !== key, reload, setData };
}
