import { useState, memo } from 'react'

function cleanDescription(raw, maxLength = 140) {
  if (!raw) return ''
  const stripped = raw.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim()
  if (stripped.length <= maxLength) return stripped
  return stripped.slice(0, maxLength).trim() + '…'
}

// Relative "posting age" (e.g. "2d ago"), falling back to created_at
// when posted_date is missing/unparseable, and to the raw string as a
// last resort so nothing is ever silently hidden.
function postingAge(job) {
  const raw = job.posted_date || job.created_at
  if (!raw) return null
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return typeof raw === 'string' ? raw : null
  const diffMs = Date.now() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'Just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  if (diffDay < 7) return `${diffDay}d ago`
  const diffWeek = Math.floor(diffDay / 7)
  if (diffWeek < 5) return `${diffWeek}w ago`
  const diffMonth = Math.floor(diffDay / 30)
  return `${diffMonth}mo ago`
}

// Remote/Hybrid badge: derived from the location_bucket the backend
// already precomputes (app/locations.py, unchanged), plus a simple
// text check for "hybrid" -- no new backend field needed.
function workModeBadge(job) {
  const haystack = `${job.title || ''} ${job.location || ''} ${job.description || ''}`.toLowerCase()
  if (job.location_bucket === 'Remote' || haystack.includes('remote')) return 'Remote'
  if (haystack.includes('hybrid')) return 'Hybrid'
  return null
}

// "Easy Apply" is a UI-only heuristic (the data has no explicit
// signal for this): postings from a company's own ATS board
// (Greenhouse/Lever/Ashby/SmartRecruiters) are typically a direct,
// streamlined application, unlike aggregator redirects (Adzuna/Jooble/
// RSS). Shown as a soft hint, not a guarantee.
const EASY_APPLY_SOURCES = new Set(['greenhouse', 'lever', 'ashby', 'smartrecruiters'])
function isEasyApply(job) {
  return EASY_APPLY_SOURCES.has((job.source || '').toLowerCase())
}

const BOOKMARKS_KEY = 'ai-job-hunter:bookmarks'

function loadBookmarks() {
  try {
    const raw = localStorage.getItem(BOOKMARKS_KEY)
    return raw ? new Set(JSON.parse(raw)) : new Set()
  } catch {
    return new Set()
  }
}

function saveBookmarks(set) {
  try {
    localStorage.setItem(BOOKMARKS_KEY, JSON.stringify([...set]))
  } catch {
    // localStorage unavailable (private browsing, etc.) -- bookmarking
    // just won't persist across reloads; not worth surfacing an error for.
  }
}

function JobCard({ job }) {
  const description = cleanDescription(job.description)
  const age = postingAge(job)
  const workMode = workModeBadge(job)
  const easyApply = isEasyApply(job)

  const [bookmarked, setBookmarked] = useState(() => loadBookmarks().has(job.job_url))
  const [shareFeedback, setShareFeedback] = useState(false)

  function toggleBookmark(e) {
    e.preventDefault()
    e.stopPropagation()
    const bookmarks = loadBookmarks()
    if (bookmarks.has(job.job_url)) {
      bookmarks.delete(job.job_url)
      setBookmarked(false)
    } else {
      bookmarks.add(job.job_url)
      setBookmarked(true)
    }
    saveBookmarks(bookmarks)
    window.dispatchEvent(new Event('ai-job-hunter:bookmark-change'))
  }

  async function handleShare(e) {
    e.preventDefault()
    e.stopPropagation()
    const shareData = {
      title: job.title || 'SAP job',
      text: `${job.title || 'SAP job'} at ${job.company || 'a company'}`,
      url: job.job_url,
    }
    if (navigator.share) {
      try {
        await navigator.share(shareData)
      } catch {
        // user cancelled the native share sheet -- not an error
      }
      return
    }
    try {
      await navigator.clipboard.writeText(job.job_url)
      setShareFeedback(true)
      window.setTimeout(() => setShareFeedback(false), 1500)
    } catch {
      // clipboard unavailable -- silently do nothing rather than error
    }
  }

  return (
    <div className="job-card">
      <div className="job-card__top">
        <div className="job-card__logo" aria-hidden="true">
          {(job.company || '?').trim().charAt(0).toUpperCase()}
        </div>
        <div className="job-card__title-block">
          <h3 className="job-card__title">{job.title || 'Untitled role'}</h3>
          <div className="job-card__company">{job.company || 'Company not listed'}</div>
        </div>
        <button
          type="button"
          className={`bookmark-btn${bookmarked ? ' bookmark-btn--active' : ''}`}
          onClick={toggleBookmark}
          aria-label={bookmarked ? 'Remove from saved jobs' : 'Save this job'}
          aria-pressed={bookmarked}
        >
          {bookmarked ? '★' : '☆'}
        </button>
      </div>

      <div className="job-card__badges">
        {workMode && (
          <span className={`badge badge--${workMode.toLowerCase()}`}>{workMode}</span>
        )}
        {easyApply && <span className="badge badge--easy-apply">Easy Apply</span>}
      </div>

      <div className="job-card__meta-row">
        {job.location && <span className="job-card__meta-tag">📍 {job.location}</span>}
        {job.salary && <span className="job-card__meta-tag job-card__meta-tag--salary">{job.salary}</span>}
        <span className="job-card__meta-tag job-card__meta-tag--source">{job.source}</span>
      </div>

      {description && <p className="job-card__desc">{description}</p>}

      <div className="job-card__footer">
        {age ? <span className="job-card__posted">{age}</span> : <span />}
        <div className="job-card__footer-actions">
          <button
            type="button"
            className="job-card__share-btn"
            onClick={handleShare}
            aria-label="Share this job"
          >
            {shareFeedback ? 'Copied!' : '↗ Share'}
          </button>
          <a
            className="job-card__open-btn"
            href={job.job_url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Open posting: ${job.title} at ${job.company || 'unknown company'}`}
          >
            Open Job ↗
          </a>
        </div>
      </div>
    </div>
  )
}

export default memo(JobCard)
