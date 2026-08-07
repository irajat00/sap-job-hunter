const THEME_OPTIONS = [
  { value: 'system', label: 'Match device' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
]

function formatLastUpdated(iso) {
  if (!iso) return 'Unknown'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return 'Unknown'
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export default function SettingsView({ themePreference, onThemeChange, lastUpdated, onRefresh, refreshing, totalJobs }) {
  return (
    <div className="settings-view">
      <section className="settings-view__section">
        <h2>Appearance</h2>
        <div className="settings-view__theme-options">
          {THEME_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`filter-chip${themePreference === opt.value ? ' filter-chip--active' : ''}`}
              onClick={() => onThemeChange(opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </section>

      <section className="settings-view__section">
        <h2>Data</h2>
        <div className="settings-view__row">
          <span>Last updated</span>
          <strong>{formatLastUpdated(lastUpdated)}</strong>
        </div>
        <div className="settings-view__row">
          <span>Total jobs tracked</span>
          <strong>{(totalJobs ?? 0).toLocaleString()}</strong>
        </div>
        <button type="button" className="settings-view__refresh-btn" onClick={onRefresh} disabled={refreshing}>
          {refreshing ? 'Refreshing…' : '↻ Refresh now'}
        </button>
      </section>

      <section className="settings-view__section">
        <h2>About</h2>
        <p className="settings-view__about">
          SAP Job Hunter collects SAP PP/QM Manufacturing job postings automatically and
          sends instant Telegram alerts for new matches, plus a daily summary. This app
          works offline once loaded and can be installed to your home screen.
        </p>
      </section>
    </div>
  )
}
