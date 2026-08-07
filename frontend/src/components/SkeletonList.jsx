function SkeletonCard() {
  return (
    <div className="job-card job-card--skeleton" aria-hidden="true">
      <div className="job-card__top">
        <div className="skeleton skeleton--circle" />
        <div className="job-card__title-block">
          <div className="skeleton skeleton--line" style={{ width: '70%' }} />
          <div className="skeleton skeleton--line" style={{ width: '45%', marginTop: 6 }} />
        </div>
      </div>
      <div className="job-card__meta-row">
        <div className="skeleton skeleton--pill" />
        <div className="skeleton skeleton--pill" />
      </div>
      <div className="skeleton skeleton--line" style={{ width: '90%', marginTop: 10 }} />
      <div className="skeleton skeleton--line" style={{ width: '60%', marginTop: 6 }} />
    </div>
  )
}

export default function SkeletonList({ count = 6 }) {
  return (
    <div className="job-grid" role="status" aria-label="Loading jobs">
      {Array.from({ length: count }).map((_, i) => <SkeletonCard key={i} />)}
    </div>
  )
}
