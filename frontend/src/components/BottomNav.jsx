const TABS = [
  { key: 'jobs', label: 'Jobs', icon: '💼' },
  { key: 'saved', label: 'Saved', icon: '★' },
  { key: 'search', label: 'Search', icon: '🔍' },
  { key: 'settings', label: 'Settings', icon: '⚙' },
]

export default function BottomNav({ active, onChange, savedCount }) {
  return (
    <nav className="bottom-nav" aria-label="Primary">
      {TABS.map((tab) => (
        <button
          key={tab.key}
          type="button"
          className={`bottom-nav__item${active === tab.key ? ' bottom-nav__item--active' : ''}`}
          onClick={() => onChange(tab.key)}
          aria-current={active === tab.key ? 'page' : undefined}
        >
          <span className="bottom-nav__icon" aria-hidden="true">
            {tab.icon}
            {tab.key === 'saved' && savedCount > 0 && (
              <span className="bottom-nav__badge">{savedCount > 99 ? '99+' : savedCount}</span>
            )}
          </span>
          <span className="bottom-nav__label">{tab.label}</span>
        </button>
      ))}
    </nav>
  )
}
