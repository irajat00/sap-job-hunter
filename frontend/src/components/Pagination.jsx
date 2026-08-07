export default function Pagination({ page, totalPages, totalJobs, onPageChange }) {
  if (totalPages <= 1) return null

  return (
    <nav className="pagination" aria-label="Job results pages">
      <button
        type="button"
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
      >
        ← Prev
      </button>

      <span className="pagination__count">
        Page {page} of {totalPages} · {totalJobs.toLocaleString()} jobs total
      </span>

      <button
        type="button"
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages}
      >
        Next →
      </button>
    </nav>
  )
}
