function NoJobsIllustration() {
  return (
    <svg width="120" height="120" viewBox="0 0 120 120" fill="none" aria-hidden="true" className="state-block__illustration">
      <circle cx="60" cy="60" r="56" fill="var(--accent-soft)" />
      <rect x="34" y="46" width="52" height="36" rx="6" fill="var(--panel)" stroke="var(--border-strong)" strokeWidth="2" />
      <rect x="48" y="36" width="24" height="14" rx="4" fill="var(--panel)" stroke="var(--border-strong)" strokeWidth="2" />
      <line x1="34" y1="60" x2="86" y2="60" stroke="var(--border-strong)" strokeWidth="2" />
      <circle cx="78" cy="78" r="12" fill="var(--panel)" stroke="var(--muted-light)" strokeWidth="3" />
      <line x1="86.5" y1="86.5" x2="94" y2="94" stroke="var(--muted-light)" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

export function EmptyState({ hasFilters, onClearFilters }) {
  return (
    <div className="state-block">
      <NoJobsIllustration />
      <p className="state-block__title">No matching SAP jobs found.</p>
      <p className="state-block__body">
        {hasFilters
          ? 'Try widening the search, or clearing a filter.'
          : 'The collector hasn\u2019t saved any postings yet. Check back soon.'}
      </p>
      {hasFilters && (
        <button type="button" onClick={onClearFilters}>Clear filters</button>
      )}
    </div>
  )
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="state-block state-block--error">
      <p className="state-block__title">Couldn't load job data.</p>
      <p className="state-block__body">{message}</p>
      <button type="button" onClick={onRetry}>Try again</button>
    </div>
  )
}
