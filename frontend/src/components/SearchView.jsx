import { useEffect, useRef, useState } from 'react'
import { fetchJobs } from '../api.js'
import JobGrid from './JobGrid.jsx'
import SkeletonList from './SkeletonList.jsx'
import { ErrorState } from './StateBlocks.jsx'

const DEBOUNCE_MS = 300

// Instant search across title, company, and location (api.js's
// matchesSearch() already checks all three fields, plus the ported
// synonym groups -- unchanged).
export default function SearchView() {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const inputRef = useRef(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    const handle = setTimeout(() => setDebouncedQuery(query), DEBOUNCE_MS)
    return () => clearTimeout(handle)
  }, [query])

  useEffect(() => {
    if (!debouncedQuery.trim()) {
      setResults(null)
      return
    }
    let cancelled = false
    setError(null)
    fetchJobs({ search: debouncedQuery, page: 1, pageSize: 100, sort: 'newest' })
      .then((res) => { if (!cancelled) setResults(res.results || []) })
      .catch((err) => { if (!cancelled) setError(err.message || 'Search failed') })
    return () => { cancelled = true }
  }, [debouncedQuery])

  return (
    <div className="search-view">
      <div className="search-view__input-wrap">
        <span className="search-view__icon" aria-hidden="true">🔍</span>
        <input
          ref={inputRef}
          type="text"
          className="search-view__input"
          placeholder="Search title, company, or location…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search jobs"
        />
        {query && (
          <button type="button" className="search-view__clear" onClick={() => setQuery('')} aria-label="Clear search">✕</button>
        )}
      </div>

      {!debouncedQuery.trim() && (
        <p className="state-block__body search-view__hint">Start typing to search across all tracked jobs.</p>
      )}

      {error && <ErrorState message={error} onRetry={() => setDebouncedQuery((q) => `${q}`)} />}

      {debouncedQuery.trim() && !error && results === null && <SkeletonList count={3} />}

      {debouncedQuery.trim() && !error && results !== null && results.length === 0 && (
        <div className="state-block">
          <p className="state-block__title">No matches for "{debouncedQuery}".</p>
          <p className="state-block__body">Try a different keyword, company, or location.</p>
        </div>
      )}

      {results && results.length > 0 && (
        <>
          <p className="results-meta"><strong>{results.length}</strong> result{results.length === 1 ? '' : 's'}</p>
          <JobGrid jobs={results} />
        </>
      )}
    </div>
  )
}
