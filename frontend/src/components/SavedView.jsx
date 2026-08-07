import { useEffect, useMemo, useState } from 'react'
import { fetchJobs } from '../api.js'
import JobGrid from './JobGrid.jsx'
import SkeletonList from './SkeletonList.jsx'
import { ErrorState } from './StateBlocks.jsx'

const BOOKMARKS_KEY = 'ai-job-hunter:bookmarks'

function loadBookmarkSet() {
  try {
    const raw = localStorage.getItem(BOOKMARKS_KEY)
    return raw ? new Set(JSON.parse(raw)) : new Set()
  } catch {
    return new Set()
  }
}

// Saved Jobs intentionally loads the FULL job list (not just whatever
// page the Jobs tab happens to have fetched) so a job you bookmarked
// on any page/filter still shows up here -- bookmarks themselves are
// unchanged (same localStorage key JobCard already uses).
export default function SavedView({ refreshKey }) {
  const [allJobs, setAllJobs] = useState(null)
  const [error, setError] = useState(null)
  const [bookmarkVersion, setBookmarkVersion] = useState(0)

  useEffect(() => {
    let cancelled = false
    setError(null)
    fetchJobs({ page: 1, pageSize: 1000, sort: 'newest' })
      .then((res) => { if (!cancelled) setAllJobs(res.results || []) })
      .catch((err) => { if (!cancelled) setError(err.message || 'Could not load jobs') })
    return () => { cancelled = true }
  }, [refreshKey])

  useEffect(() => {
    function onChange() { setBookmarkVersion((v) => v + 1) }
    window.addEventListener('ai-job-hunter:bookmark-change', onChange)
    window.addEventListener('storage', onChange)
    return () => {
      window.removeEventListener('ai-job-hunter:bookmark-change', onChange)
      window.removeEventListener('storage', onChange)
    }
  }, [])

  const savedJobs = useMemo(() => {
    if (!allJobs) return []
    const bookmarks = loadBookmarkSet()
    return allJobs.filter((j) => bookmarks.has(j.job_url))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allJobs, bookmarkVersion])

  if (error) return <ErrorState message={error} onRetry={() => window.location.reload()} />
  if (allJobs === null) return <SkeletonList count={4} />
  if (savedJobs.length === 0) {
    return (
      <div className="state-block">
        <p className="state-block__title">No saved jobs yet.</p>
        <p className="state-block__body">Tap the ☆ on any job card to save it for later — it'll show up here.</p>
      </div>
    )
  }

  return (
    <>
      <p className="results-meta">
        <strong>{savedJobs.length}</strong> saved job{savedJobs.length === 1 ? '' : 's'}
      </p>
      <JobGrid jobs={savedJobs} />
    </>
  )
}
