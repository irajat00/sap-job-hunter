const SALARY_OPTIONS = [
  { value: '', label: 'Any Salary' },
  { value: 'available', label: 'Salary Available' },
  { value: 'not_listed', label: 'Salary Not Listed' },
]

const POSTED_OPTIONS = [
  { value: '', label: 'Any time' },
  { value: 'today', label: 'Posted Today' },
  { value: '3', label: 'Last 3 Days' },
  { value: '7', label: 'Last Week' },
]

function RadioGroup({ name, options, value, onChange }) {
  return (
    <div className="filter-sheet__options">
      {options.map((opt) => (
        <button
          type="button"
          key={opt.value ?? opt.key ?? opt.label}
          className={`filter-chip${(opt.value ?? '') === (value || '') ? ' filter-chip--active' : ''}`}
          onClick={() => onChange(opt.value ?? '')}
        >
          {opt.label}
          {typeof opt.count === 'number' && <span className="filter-chip__count">{opt.count}</span>}
        </button>
      ))}
    </div>
  )
}

export default function FilterSheet({
  open, onClose,
  category, onCategoryChange,
  locationBucket, onLocationBucketChange,
  company, onCompanyChange,
  salary, onSalaryChange,
  postedWithin, onPostedWithinChange,
  facets,
}) {
  if (!open) return null

  const hasFilters = Boolean(category || locationBucket || company || salary || postedWithin)

  function clearAll() {
    onCategoryChange('')
    onLocationBucketChange('')
    onCompanyChange('')
    onSalaryChange('')
    onPostedWithinChange('')
  }

  const categoryOptions = (facets?.categories || [])
    .filter((c) => c.key !== 'All Jobs')
    .map((c) => ({ value: c.key, label: c.key, count: c.count }))
  const locationOptions = (facets?.locations || [])
    .filter((l) => l.key !== 'All')
    .map((l) => ({ value: l.key, label: l.key, count: l.count }))
  const companyOptions = (facets?.companies || []).slice(0, 20).map((c) => ({ value: c.name, label: c.name, count: c.count }))

  return (
    <div className="sheet-overlay" role="dialog" aria-modal="true" aria-label="Filters" onClick={onClose}>
      <div className="filter-sheet" onClick={(e) => e.stopPropagation()}>
        <div className="filter-sheet__handle" aria-hidden="true" />
        <div className="filter-sheet__header">
          <h2>Filters</h2>
          <button type="button" className="filter-sheet__close" onClick={onClose} aria-label="Close filters">✕</button>
        </div>

        <div className="filter-sheet__body">
          <section className="filter-sheet__group">
            <h3>Country / Location</h3>
            <RadioGroup name="location" options={[{ value: '', label: 'All' }, ...locationOptions]} value={locationBucket} onChange={onLocationBucketChange} />
          </section>

          <section className="filter-sheet__group">
            <h3>Category</h3>
            <RadioGroup name="category" options={[{ value: '', label: 'All Jobs' }, ...categoryOptions]} value={category} onChange={onCategoryChange} />
          </section>

          <section className="filter-sheet__group">
            <h3>Source / Company</h3>
            <RadioGroup name="company" options={[{ value: '', label: 'All Companies' }, ...companyOptions]} value={company} onChange={onCompanyChange} />
            {companyOptions.length === 0 && <p className="filter-sheet__empty-note">No companies to show yet.</p>}
          </section>

          <section className="filter-sheet__group">
            <h3>Salary</h3>
            <RadioGroup name="salary" options={SALARY_OPTIONS} value={salary} onChange={onSalaryChange} />
          </section>

          <section className="filter-sheet__group">
            <h3>Posted</h3>
            <RadioGroup name="posted" options={POSTED_OPTIONS} value={postedWithin} onChange={onPostedWithinChange} />
          </section>
        </div>

        <div className="filter-sheet__footer">
          {hasFilters && (
            <button type="button" className="filter-sheet__clear" onClick={clearAll}>Clear all</button>
          )}
          <button type="button" className="filter-sheet__apply" onClick={onClose}>Show results</button>
        </div>
      </div>
    </div>
  )
}
