export default function TopAppBar({ title, onSearchClick, onFilterClick, filterActive }) {
  return (
    <header className="top-app-bar">
      <h1 className="top-app-bar__title">{title}</h1>
      <div className="top-app-bar__actions">
        <button
          type="button"
          className="top-app-bar__icon-btn"
          onClick={onSearchClick}
          aria-label="Search"
          title="Search"
        >
          🔍
        </button>
        <button
          type="button"
          className={`top-app-bar__icon-btn${filterActive ? ' top-app-bar__icon-btn--active' : ''}`}
          onClick={onFilterClick}
          aria-label="Filters"
          title="Filters"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M4 6h16M7 12h10M10 18h4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          {filterActive && <span className="top-app-bar__dot" aria-hidden="true" />}
        </button>
      </div>
    </header>
  )
}
