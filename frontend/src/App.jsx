import { useEffect, useRef, useState } from 'react'
import { fetchJobs, fetchFacets, fetchDashboard, getLastUpdated, invalidateDataCache } from './api.js'
import TopAppBar from './components/TopAppBar.jsx'
import BottomNav from './components/BottomNav.jsx'
import FilterSheet from './components/FilterSheet.jsx'
import JobGrid from './components/JobGrid.jsx'
import Pagination from './components/Pagination.jsx'
import SkeletonList from './components/SkeletonList.jsx'
import { EmptyState, ErrorState } from './components/StateBlocks.jsx'
import SavedView from './components/SavedView.jsx'
import SearchView from './components/SearchView.jsx'
import SettingsView from './components/SettingsView.jsx'
import { useDarkMode } from './useDarkMode.js'

const BOOKMARKS_KEY = 'ai-job-hunter:bookmarks'
const PULL_THRESHOLD_PX = 70

function loadBookmarkSet() {
  try {
    const raw = localStorage.getItem(BOOKMARKS_KEY)
    return raw ? new Set(JSON.parse(raw)) : new Set()
  } catch {
    return new Set()
  }
}

// Single fixed-user app: no profile selector, no resume, no per-job
// match fetching -- SAP Manufacturing jobs and Telegram notifications
// are the whole feature set. This is a mobile-first PWA shell: a Top
// App Bar + Bottom Navigation switching between four tabs (Jobs /
// Saved / Search / Settings), reading the same static jobs.json
// snapshot as before via api.js -- no filtering/search/sort logic
// changed, just how it's presented.
export default function App() {
  const [isDark, themePreference, setThemePreference] = useDarkMode()

  const [activeTab, setActiveTab] = useState('jobs')
  const [filterSheetOpen, setFilterSheetOpen] = useState(false)

  const [jobs, setJobs] = useState([])
  const [total, setTotal] = useState(0)
  const [facets, setFacets] = useState(null)
  const [dashboard, setDashboard] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)

  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)

  const [sort, setSort] = useState('newest')
  const [category, setCategory] = useState('')
  const [locationBucket, setLocationBucket] = useState('')
  const [company, setCompany] = useState('')
  const [salary, setSalary] = useState('')
  const [postedWithin, setPostedWithin] = useState('')
  const [pageSize] = useState(25)
  const [page, setPage] = useState(1)

  const [bookmarkVersion, setBookmarkVersion] = useState(0)
  const savedCount = loadBookmarkSet().size

  const filterParams = { category, locationBucket, company, salary, postedWithin }
  const hasFilters = Boolean(category || locationBucket || company || salary || postedWithin)

  useEffect(() => {
    setPage(1)
  }, [sort, category, locationBucket, company, salary, postedWithin])

  async function load({ isRefresh = false } = {}) {
    isRefresh ? setRefreshing(true) : setLoading(true)
    setError(null)
    try {
      if (isRefresh) invalidateDataCache()
      const [jobsData, facetsData, dashboardData, updated] = await Promise.all([
        fetchJobs({ ...filterParams, sort, page, pageSize }),
        fetchFacets(filterParams),
        fetchDashboard(),
        getLastUpdated(),
      ])
      setJobs(jobsData.results || [])
      setTotal(jobsData.total || 0)
      setFacets(facetsData)
      setDashboard(dashboardData)
      setLastUpdated(updated)
    } catch (err) {
      setError(err.message || 'Unknown error')
    } finally {
      isRefresh ? setRefreshing(false) : setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category, locationBucket, company, salary, postedWithin, sort, page, pageSize])

  useEffect(() => {
    function onBookmarkChange() { setBookmarkVersion((v) => v + 1) }
    window.addEventListener('ai-job-hunter:bookmark-change', onBookmarkChange)
    window.addEventListener('storage', onBookmarkChange)
    return () => {
      window.removeEventListener('ai-job-hunter:bookmark-change', onBookmarkChange)
      window.removeEventListener('storage', onBookmarkChange)
    }
  }, [])

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  function clearFilters() {
    setCategory('')
    setLocationBucket('')
    setCompany('')
    setSalary('')
    setPostedWithin('')
  }

  // --- Pull-to-refresh (Jobs tab only) ---------------------------------
  const scrollRef = useRef(null)
  const touchStartY = useRef(null)
  const [pullDistance, setPullDistance] = useState(0)

  function onTouchStart(e) {
    if (activeTab !== 'jobs') return
    if (scrollRef.current && scrollRef.current.scrollTop > 0) return
    touchStartY.current = e.touches[0].clientY
  }
  function onTouchMove(e) {
    if (touchStartY.current == null) return
    const delta = e.touches[0].clientY - touchStartY.current
    if (delta > 0) setPullDistance(Math.min(delta, PULL_THRESHOLD_PX * 1.5))
  }
  function onTouchEnd() {
    if (pullDistance >= PULL_THRESHOLD_PX) load({ isRefresh: true })
    setPullDistance(0)
    touchStartY.current = null
  }

  return (
    <div className={`app-shell${filterSheetOpen ? ' app-shell--sheet-open' : ''}`}>
      <TopAppBar
        title="SAP Job Hunter"
        onSearchClick={() => setActiveTab('search')}
        onFilterClick={() => setFilterSheetOpen(true)}
        filterActive={hasFilters}
      />

      <main
        className="app-main"
        ref={scrollRef}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
      >
        {activeTab === 'jobs' && (
          <div className="jobs-view">
            {pullDistance > 0 && (
              <div className="pull-indicator" style={{ height: pullDistance }}>
                {pullDistance >= PULL_THRESHOLD_PX ? '↻ Release to refresh' : '↓ Pull to refresh'}
              </div>
            )}

            {dashboard && (
              <div className="mini-dashboard">
                <div className="mini-dashboard__stat">
                  <strong>{dashboard.total_jobs?.toLocaleString() ?? 0}</strong>
                  <span>Total Jobs</span>
                </div>
                <div className="mini-dashboard__stat">
                  <strong>{dashboard.jobs_today?.toLocaleString() ?? 0}</strong>
                  <span>New Today</span>
                </div>
              </div>
            )}

            {!loading && !error && (
              <p className="results-meta">
                <strong>{total.toLocaleString()}</strong> job{total === 1 ? '' : 's'} found
              </p>
            )}

            {loading && <SkeletonList />}

            {!loading && error && <ErrorState message={error} onRetry={() => load()} />}

            {!loading && !error && jobs.length === 0 && (
              <EmptyState hasFilters={hasFilters} onClearFilters={clearFilters} />
            )}

            {!loading && !error && jobs.length > 0 && (
              <>
                <JobGrid jobs={jobs} />
                <Pagination page={page} totalPages={totalPages} totalJobs={total} onPageChange={setPage} />
              </>
            )}
          </div>
        )}

        {activeTab === 'saved' && <SavedView refreshKey={bookmarkVersion} />}

        {activeTab === 'search' && <SearchView />}

        {activeTab === 'settings' && (
          <SettingsView
            themePreference={themePreference}
            onThemeChange={setThemePreference}
            lastUpdated={lastUpdated}
            onRefresh={() => load({ isRefresh: true })}
            refreshing={refreshing}
            totalJobs={dashboard?.total_jobs}
          />
        )}
      </main>

      <BottomNav active={activeTab} onChange={setActiveTab} savedCount={savedCount} />

      <FilterSheet
        open={filterSheetOpen}
        onClose={() => setFilterSheetOpen(false)}
        category={category} onCategoryChange={setCategory}
        locationBucket={locationBucket} onLocationBucketChange={setLocationBucket}
        company={company} onCompanyChange={setCompany}
        salary={salary} onSalaryChange={setSalary}
        postedWithin={postedWithin} onPostedWithinChange={setPostedWithin}
        facets={facets}
      />
    </div>
  )
}
