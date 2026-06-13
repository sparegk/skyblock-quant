import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  Bell,
  Boxes,
  CalendarDays,
  ChevronDown,
  FileText,
  Gauge,
  Home,
  LineChart,
  Search,
  Settings,
  SlidersHorizontal,
  Sparkles,
  TrendingUp,
} from 'lucide-react'
import './App.css'

const API_BASE_URL = 'http://127.0.0.1:8000'

type MarketSummary = {
  database_ready: boolean
  latest_snapshot: string | null
  tracked_products: number
  total_rows: number
}

type BazaarItem = {
  item_id: string
  buy_price: number
  sell_price: number
  buy_volume: number
  sell_volume: number
  buy_orders: number
  sell_orders: number
  spread: number
  collected_at: string
}

type NpcArbitrageItem = {
  item_id: string
  item_name: string
  category: string | null
  tier: string | null
  bazaar_buy_price: number
  bazaar_sell_price: number
  npc_sell_price: number
  profit_per_item: number
  profit_margin: number
  estimated_profit: number
  history_adjusted_profit: number
  liquidity_score: number
  observed_snapshots: number
  profitable_snapshots: number
  average_profit_per_item: number
  profit_consistency: number
  max_recent_price_jump: number
  spread_percent: number
  risk_score: number
  risk_label: string
  risk_reasons: string[]
  buy_volume: number
  sell_volume: number
  buy_orders: number
  sell_orders: number
  collected_at: string
}

type NpcArbitrageHistoryRow = {
  collected_at: string
  bazaar_buy_price: number
  bazaar_sell_price: number
  npc_sell_price: number
  profit_per_item: number
  profit_margin: number | null
  buy_volume: number
  sell_volume: number
  buy_orders: number
  sell_orders: number
  is_profitable: number
}

type NpcArbitrageDetail = {
  item_id: string
  item_name: string
  category: string | null
  tier: string | null
  npc_sell_price: number
  latest: NpcArbitrageHistoryRow
  history: NpcArbitrageHistoryRow[]
  observed_snapshots: number
  profitable_snapshots: number
  profit_consistency: number
  profit_margin: number
  sell_volume: number
  sell_orders: number
  max_recent_price_jump: number
  spread_percent: number
  risk_score: number
  risk_label: string
  risk_reasons: string[]
}

type InvestmentMomentumItem = {
  item_id: string
  item_name: string
  category: string | null
  tier: string | null
  buy_price: number
  sell_price: number
  midpoint_price: number
  buy_volume: number
  sell_volume: number
  buy_orders: number
  sell_orders: number
  spread: number
  collected_at: string
  observed_snapshots: number
  oldest_midpoint_price: number
  latest_midpoint_price: number
  gain_percent: number
  rising_steps: number
  max_single_jump: number
  average_volume: number
  average_orders: number
  momentum_score: number
}

type MarketSignal = {
  id: number
  created_at: string
  source_snapshot: string | null
  item_id: string
  item_name: string
  signal_type: string
  title: string
  message: string
  confidence: number
  expected_return: number | null
  risk_score: number
  severity: 'positive' | 'watch' | 'risk' | string
  explanation: Record<string, unknown>
}

type BacktestSummary = {
  total_results: number
  successful_results: number
  win_rate: number
  average_return: number
  median_return: number
  best_return: number
  worst_return: number
  average_drawdown: number
  latest_evaluated_at: string | null
}

type BacktestResult = {
  id: number
  signal_id: number
  item_id: string
  item_name: string
  signal_type: string
  title: string
  horizon: string
  entry_time: string
  exit_time: string
  entry_price: number
  exit_price: number
  return_percent: number
  max_drawdown_percent: number
  max_gain_percent: number
  was_successful: number
  evaluated_at: string
  notes: string | null
}

type JobRun = {
  id: number
  job_type: string
  started_at: string
  finished_at: string | null
  status: 'running' | 'success' | 'partial' | 'failed' | string
  message: string | null
  products_collected: number | null
  signals_generated: number | null
  backtests_evaluated: Record<string, number>
}

type DetailMetricProps = {
  label: string
  value: ReactNode
  hint: string
  positive?: boolean
}

type MiniLineChartProps = {
  values: number[]
  label: string
  compact?: boolean
}

const navItems = [
  { label: 'home', icon: Home, active: true },
  { label: 'markets', icon: Boxes },
  { label: 'opportunities', icon: Sparkles },
  { label: 'forecasts', icon: LineChart },
  { label: 'rankings', icon: Gauge },
  { label: 'research', icon: FileText },
  { label: 'alerts', icon: Bell, badge: '12' },
  { label: 'settings', icon: Settings },
]

function formatNumber(value: number) {
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: value >= 100 ? 0 : 2,
  }).format(value)
}

function formatCompact(value: number) {
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 2,
    notation: 'compact',
  }).format(value)
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(2)}%`
}

function formatSnapshotTime(value: string | null) {
  if (!value) {
    return 'no snapshot'
  }

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value))
}

function formatItemName(itemId: string) {
  return itemId
    .toLowerCase()
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

function spreadPercent(item: BazaarItem) {
  if (item.sell_price <= 0) {
    return 0
  }

  return (item.spread / item.sell_price) * 100
}

function scoreItem(item: BazaarItem) {
  const liquidity = Math.min((item.buy_volume + item.sell_volume) / 1_000_000, 40)
  const spreadScore = Math.min(Math.max(spreadPercent(item), 0), 35)
  const orderScore = Math.min((item.buy_orders + item.sell_orders) / 40, 25)
  return Math.round(liquidity + spreadScore + orderScore)
}

function getNpcQualityLabel(item: NpcArbitrageItem) {
  return item.risk_label
}

function getNpcQualityClass(item: NpcArbitrageItem) {
  const label = getNpcQualityLabel(item)

  if (label === 'stable') {
    return 'quality-badge stable'
  }

  if (label === 'possible manipulation' || label === 'volatile') {
    return 'quality-badge risk'
  }

  if (label === 'thin liquidity') {
    return 'quality-badge warning'
  }

  return 'quality-badge'
}

function getMomentumLabel(item: InvestmentMomentumItem) {
  if (item.max_single_jump >= 0.2) {
    return 'quick jump'
  }

  if (item.rising_steps >= item.observed_snapshots - 1) {
    return 'steady climb'
  }

  return 'heating up'
}

function getMomentumLabelClass(item: InvestmentMomentumItem) {
  const label = getMomentumLabel(item)

  if (label === 'steady climb') {
    return 'quality-badge stable'
  }

  if (label === 'quick jump') {
    return 'quality-badge warning'
  }

  return 'quality-badge'
}

function getSignalDotClass(signal: MarketSignal) {
  if (signal.severity === 'positive') {
    return 'alert-dot positive-dot'
  }

  if (signal.severity === 'risk') {
    return 'alert-dot risk-dot'
  }

  return 'alert-dot watch-dot'
}

function getSignalShortText(signal: MarketSignal) {
  if (signal.expected_return !== null) {
    return `${formatPercent(signal.expected_return)} expected move`
  }

  return `${Math.round(signal.confidence * 100)}% confidence`
}

function getJobStatusClass(status: string) {
  if (status === 'success') {
    return 'quality-badge stable'
  }

  if (status === 'failed') {
    return 'quality-badge risk'
  }

  return 'quality-badge warning'
}

function formatBacktestCounts(values: Record<string, number>) {
  const entries = Object.entries(values)
  if (!entries.length) {
    return 'none'
  }

  return entries.map(([horizon, count]) => `${horizon}: ${count}`).join(' / ')
}

function getMinecraftIconName(itemId: string) {
  const customIcons: Record<string, string> = {
    BROWN_MUSHROOM: 'brown_mushroom',
    CARROT_ITEM: 'carrot',
    COAL: 'coal',
    COBBLESTONE: 'cobblestone',
    DIAMOND: 'diamond',
    DIAMOND_BLOCK: 'diamond_block',
    EMERALD: 'emerald',
    EMERALD_BLOCK: 'emerald_block',
    ENDER_PEARL: 'ender_pearl',
    FEATHER: 'feather',
    GOLD_INGOT: 'gold_ingot',
    GOLD_BLOCK: 'gold_block',
    IRON_INGOT: 'iron_ingot',
    IRON_BLOCK: 'iron_block',
    MELON: 'melon_slice',
    NETHERRACK: 'netherrack',
    OBSIDIAN: 'obsidian',
    POTATO_ITEM: 'potato',
    RABBIT_FOOT: 'rabbit_foot',
    REDSTONE: 'redstone',
    REDSTONE_BLOCK: 'redstone_block',
    SLIME_BALL: 'slime_ball',
    SNOW_BALL: 'snowball',
    SUGAR_CANE: 'sugar_cane',
    TARANTULA_WEB: 'cobweb',
    WHEAT: 'wheat',
  }

  if (customIcons[itemId]) {
    return customIcons[itemId]
  }

  const normalized = itemId
    .replace(/^ENCHANTED_/, '')
    .replace(/_ITEM$/, '')
    .toLowerCase()

  return normalized
}

function ItemIcon({ item }: { item: BazaarItem }) {
  const [failed, setFailed] = useState(false)
  const iconName = getMinecraftIconName(item.item_id)
  const initials = formatItemName(item.item_id)
    .split(' ')
    .slice(0, 2)
    .map((word) => word[0])
    .join('')

  return (
    <span className="item-icon">
      {!failed ? (
        <img
          alt=""
          src={`https://raw.githubusercontent.com/InventivetalentDev/minecraft-assets/1.20.4/assets/minecraft/textures/item/${iconName}.png`}
          onError={() => setFailed(true)}
        />
      ) : (
        <span>{initials}</span>
      )}
    </span>
  )
}

function DetailMetric({ label, value, hint, positive = false }: DetailMetricProps) {
  return (
    <div className="detail-metric">
      <span>{label}</span>
      <strong className={positive ? 'metric-value positive' : 'metric-value'}>{value}</strong>
      <small>{hint}</small>
    </div>
  )
}

function MiniLineChart({ values, label, compact = false }: MiniLineChartProps) {
  const cleanValues = values.filter((value) => Number.isFinite(value))
  const points = cleanValues.length >= 2 ? cleanValues : [0, 0]
  const min = Math.min(...points)
  const max = Math.max(...points)
  const range = max - min || 1
  const width = compact ? 96 : 260
  const height = compact ? 34 : 78
  const padding = compact ? 4 : 8
  const usableWidth = width - padding * 2
  const usableHeight = height - padding * 2
  const coordinates = points.map((value, index) => {
    const x = padding + (index / Math.max(points.length - 1, 1)) * usableWidth
    const y = padding + (1 - (value - min) / range) * usableHeight
    return `${x.toFixed(2)},${y.toFixed(2)}`
  })
  const areaCoordinates = [
    `${padding},${height - padding}`,
    ...coordinates,
    `${width - padding},${height - padding}`,
  ]

  return (
    <svg
      className={compact ? 'mini-chart compact' : 'mini-chart'}
      role="img"
      aria-label={label}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
    >
      <polyline className="mini-chart-grid" points={`${padding},${height - padding} ${width - padding},${height - padding}`} />
      <polygon className="mini-chart-area" points={areaCoordinates.join(' ')} />
      <polyline className="mini-chart-line" points={coordinates.join(' ')} />
      {!compact
        ? coordinates.map((point) => {
            const [cx, cy] = point.split(',')
            return <circle className="mini-chart-point" cx={cx} cy={cy} key={point} r="2.8" />
          })
        : null}
    </svg>
  )
}

function getNpcTrend(detail: NpcArbitrageDetail | null) {
  if (!detail || detail.history.length < 2) {
    return 'steady'
  }

  const latest = detail.history[0].profit_per_item
  const oldest = detail.history[detail.history.length - 1].profit_per_item
  const movement = latest - oldest
  const movementRatio = oldest > 0 ? movement / oldest : 0

  if (movementRatio > 0.05) {
    return 'improving'
  }

  if (movementRatio < -0.05) {
    return 'fading'
  }

  return 'steady'
}

function getSnapshotAgeMinutes(value: string | null) {
  if (!value) {
    return null
  }

  const timestamp = new Date(value).getTime()
  if (Number.isNaN(timestamp)) {
    return null
  }

  return Math.max(0, Math.floor((Date.now() - timestamp) / 60_000))
}

function App() {
  const [summary, setSummary] = useState<MarketSummary | null>(null)
  const [items, setItems] = useState<BazaarItem[]>([])
  const [npcArbitrageItems, setNpcArbitrageItems] = useState<NpcArbitrageItem[]>([])
  const [investmentItems, setInvestmentItems] = useState<InvestmentMomentumItem[]>([])
  const [signals, setSignals] = useState<MarketSignal[]>([])
  const [backtestSummary, setBacktestSummary] = useState<BacktestSummary | null>(null)
  const [backtestResults, setBacktestResults] = useState<BacktestResult[]>([])
  const [jobRuns, setJobRuns] = useState<JobRun[]>([])
  const [selectedNpcItemId, setSelectedNpcItemId] = useState<string | null>(null)
  const [selectedNpcDetail, setSelectedNpcDetail] = useState<NpcArbitrageDetail | null>(null)
  const [query, setQuery] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isArbitrageLoading, setIsArbitrageLoading] = useState(true)
  const [isNpcDetailLoading, setIsNpcDetailLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadDashboardData() {
      try {
        setIsLoading(true)
        setError(null)

        const [
          summaryResponse,
          itemsResponse,
          investmentResponse,
          signalsResponse,
          backtestSummaryResponse,
          backtestResultsResponse,
          jobsResponse,
        ] =
          await Promise.all([
          fetch(`${API_BASE_URL}/api/bazaar/summary`),
          fetch(`${API_BASE_URL}/api/bazaar/latest?limit=40`),
          fetch(`${API_BASE_URL}/api/investments/momentum?limit=5`),
          fetch(`${API_BASE_URL}/api/signals/latest?limit=8`),
          fetch(`${API_BASE_URL}/api/backtests/summary`),
          fetch(`${API_BASE_URL}/api/backtests/results?limit=5`),
          fetch(`${API_BASE_URL}/api/jobs/latest?limit=5`),
        ])

        if (
          !summaryResponse.ok ||
          !itemsResponse.ok ||
          !investmentResponse.ok ||
          !signalsResponse.ok ||
          !backtestSummaryResponse.ok ||
          !backtestResultsResponse.ok ||
          !jobsResponse.ok
        ) {
          throw new Error('Backend API request failed.')
        }

        const summaryData = (await summaryResponse.json()) as MarketSummary
        const itemsData = (await itemsResponse.json()) as { items: BazaarItem[] }
        const investmentData = (await investmentResponse.json()) as {
          items: InvestmentMomentumItem[]
        }
        const signalsData = (await signalsResponse.json()) as { signals: MarketSignal[] }
        const backtestSummaryData = (await backtestSummaryResponse.json()) as BacktestSummary
        const backtestResultsData = (await backtestResultsResponse.json()) as {
          results: BacktestResult[]
        }
        const jobsData = (await jobsResponse.json()) as { jobs: JobRun[] }

        setSummary(summaryData)
        setItems(itemsData.items)
        setInvestmentItems(investmentData.items)
        setSignals(signalsData.signals)
        setBacktestSummary(backtestSummaryData)
        setBacktestResults(backtestResultsData.results)
        setJobRuns(jobsData.jobs)
      } catch {
        setError('start the backend api to load live bazaar data')
      } finally {
        setIsLoading(false)
      }
    }

    loadDashboardData()
  }, [])

  useEffect(() => {
    const request = new AbortController()

    async function loadNpcArbitrage() {
      try {
        setIsArbitrageLoading(true)
        setError(null)

        const params = new URLSearchParams({ limit: '8' })
        const response = await fetch(`${API_BASE_URL}/api/arbitrage/npc?${params}`, {
          signal: request.signal,
        })

        if (!response.ok) {
          throw new Error('Backend API request failed.')
        }

        const data = (await response.json()) as { items: NpcArbitrageItem[] }
        setNpcArbitrageItems(data.items)
        setSelectedNpcItemId((current) => {
          if (current && data.items.some((item) => item.item_id === current)) {
            return current
          }

          return null
        })
      } catch (loadError) {
        if (loadError instanceof DOMException && loadError.name === 'AbortError') {
          return
        }

        setNpcArbitrageItems([])
        setError('start the backend api to load live bazaar data')
      } finally {
        if (!request.signal.aborted) {
          setIsArbitrageLoading(false)
        }
      }
    }

    loadNpcArbitrage()

    return () => request.abort()
  }, [])

  useEffect(() => {
    if (!selectedNpcItemId) {
      setSelectedNpcDetail(null)
      return
    }

    const request = new AbortController()

    async function loadNpcDetail() {
      try {
        setIsNpcDetailLoading(true)
        const params = new URLSearchParams({
          history_snapshots: '5',
        })
        const response = await fetch(
          `${API_BASE_URL}/api/arbitrage/npc/${selectedNpcItemId}?${params}`,
          { signal: request.signal },
        )

        if (!response.ok) {
          throw new Error('NPC arbitrage detail request failed.')
        }

        const data = (await response.json()) as { item: NpcArbitrageDetail }
        setSelectedNpcDetail(data.item)
      } catch (loadError) {
        if (loadError instanceof DOMException && loadError.name === 'AbortError') {
          return
        }

        setSelectedNpcDetail(null)
      } finally {
        if (!request.signal.aborted) {
          setIsNpcDetailLoading(false)
        }
      }
    }

    loadNpcDetail()

    return () => request.abort()
  }, [selectedNpcItemId])

  const rankedItems = useMemo(
    () => [...items].sort((a, b) => scoreItem(b) - scoreItem(a)),
    [items],
  )

  const featuredItem = rankedItems[0]

  const filteredItems = useMemo(() => {
    const cleanQuery = query.trim().toLowerCase()

    if (!cleanQuery) {
      return rankedItems.slice(0, 8)
    }

    return rankedItems
      .filter((item) => formatItemName(item.item_id).toLowerCase().includes(cleanQuery))
      .slice(0, 8)
  }, [query, rankedItems])

  const marketScore = featuredItem ? Math.min(scoreItem(featuredItem), 99) : 0
  const totalOpportunities = rankedItems.filter((item) => spreadPercent(item) > 1).length
  const bestNpcProfit = npcArbitrageItems[0]?.profit_per_item ?? 0
  const selectedNpcItem =
    npcArbitrageItems.find((item) => item.item_id === selectedNpcItemId) ?? null
  const snapshotAgeMinutes = getSnapshotAgeMinutes(summary?.latest_snapshot ?? null)
  const isSnapshotStale = snapshotAgeMinutes !== null && snapshotAgeMinutes > 20
  const topRankings = rankedItems.slice(0, 3)
  const averageSpread =
    rankedItems.length > 0
      ? rankedItems.reduce((sum, item) => sum + Math.max(spreadPercent(item), 0), 0) /
        rankedItems.length
      : 0
  const forecastChartValues =
    investmentItems.length > 0
      ? investmentItems.map((item) => item.momentum_score)
      : rankedItems.slice(0, 8).map((item) => scoreItem(item))
  const selectedNpcProfitChart =
    selectedNpcDetail?.history
      .slice()
      .reverse()
      .map((row) => row.profit_per_item) ?? []
  const backtestWinRate = backtestSummary ? Math.round(backtestSummary.win_rate * 100) : 0
  const latestJob = jobRuns[0]

  return (
    <div className="dashboard">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">sq</div>
          <strong>skyblock quant</strong>
        </div>

        <nav className="nav-list" aria-label="main navigation">
          {navItems.map((item) => {
            const Icon = item.icon

            return (
              <button className={item.active ? 'nav-item active' : 'nav-item'} key={item.label}>
                <Icon size={18} />
                <span>{item.label}</span>
                {item.badge ? <em>{item.badge}</em> : null}
              </button>
            )
          })}
        </nav>

        <button className="collapse-button">
          <ChevronDown size={16} />
          collapse
        </button>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <label className="search-box">
            <Search size={18} />
            <input
              aria-label="search items"
              placeholder="search items, metrics, or markets..."
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <kbd>ctrl k</kbd>
          </label>

          <div className="toolbar">
            <button>
              <CalendarDays size={17} />
              {formatSnapshotTime(summary?.latest_snapshot ?? null)}
              <ChevronDown size={15} />
            </button>
            <button>
              <Boxes size={17} />
              all bazaar
              <ChevronDown size={15} />
            </button>
            <button>
              <SlidersHorizontal size={17} />
              filters
            </button>
            <button className="icon-button" aria-label="notifications">
              <Bell size={18} />
            </button>
          </div>
        </header>

        <section className="title-row">
          <div>
            <h1>home dashboard</h1>
            <p>a unified view of the hypixel skyblock economy.</p>
          </div>
          <span className={error ? 'connection offline' : 'connection'}>
            {error ? error : 'backend connected'}
          </span>
        </section>

        <section className="metric-grid">
          <article className="metric-card outlook">
            <div className="metric-icon">
              <TrendingUp size={32} />
            </div>
            <div>
              <span>market outlook</span>
              <strong>{marketScore >= 55 ? 'active' : 'stable'}</strong>
              <p>
                score <b>{marketScore}</b> / 100
              </p>
            </div>
          </article>
          <article className="metric-card">
            <div className="metric-icon blue">
              <Sparkles size={30} />
            </div>
            <div>
              <span>bazaar flips</span>
              <strong>{npcArbitrageItems.length || totalOpportunities}</strong>
              <p>
                {bestNpcProfit > 0
                  ? `${formatCompact(bestNpcProfit)} best npc profit`
                  : 'waiting for metadata'}
              </p>
            </div>
          </article>
          <article className="metric-card">
            <div className="metric-icon purple">
              <Gauge size={30} />
            </div>
            <div>
              <span>spread index</span>
              <strong>{averageSpread.toFixed(2)}%</strong>
              <p>latest snapshot average</p>
            </div>
          </article>
          <article className="metric-card">
            <div className="metric-icon orange">
              <LineChart size={30} />
            </div>
            <div>
              <span>backtest win rate</span>
              <strong>{backtestSummary?.total_results ? `${backtestWinRate}%` : 'n/a'}</strong>
              <p>
                {backtestSummary?.total_results
                  ? `${backtestSummary.successful_results} of ${backtestSummary.total_results} signals`
                  : 'evaluate signals to start'}
              </p>
            </div>
          </article>
        </section>

        <section className="dashboard-grid">
          <div className="left-column">
            <article className="panel featured-panel">
              <div className="panel-heading">
                <h2>featured opportunity</h2>
                {featuredItem ? <span className="buy-pill">strong watch</span> : null}
              </div>

              {isLoading ? (
                <p className="empty-state">loading bazaar snapshot...</p>
              ) : featuredItem ? (
                <>
                  <div className="featured-head">
                    <ItemIcon item={featuredItem} />
                    <div>
                      <h3>{formatItemName(featuredItem.item_id)}</h3>
                      <p>{featuredItem.item_id}</p>
                    </div>
                  </div>

                  <div className="detail-grid">
                    <DetailMetric
                      label="buy price"
                      value={formatCompact(featuredItem.buy_price)}
                      hint="highest instant sell order"
                    />
                    <DetailMetric
                      label="sell price"
                      value={formatCompact(featuredItem.sell_price)}
                      hint="lowest instant buy order"
                    />
                    <DetailMetric
                      label="spread"
                      value={`${spreadPercent(featuredItem).toFixed(2)}%`}
                      hint={`${formatCompact(featuredItem.spread)} coins gap`}
                      positive
                    />
                    <DetailMetric
                      label="total volume"
                      value={formatCompact(featuredItem.buy_volume + featuredItem.sell_volume)}
                      hint="buy and sell volume"
                    />
                    <DetailMetric
                      label="orders"
                      value={featuredItem.buy_orders + featuredItem.sell_orders}
                      hint="active order count"
                    />
                    <DetailMetric
                      label="confidence"
                      value={<span className="score-badge">{scoreItem(featuredItem)}</span>}
                      hint="baseline score"
                    />
                  </div>

                  <p className="panel-note">
                    high liquidity and a visible spread make this item useful for the first
                    opportunity ranking pass.
                  </p>
                </>
              ) : (
                <p className="empty-state">run the collector to create your first snapshot.</p>
              )}
            </article>

            <article className="panel">
              <div className="panel-heading">
                <h2>top opportunities</h2>
                <span>{formatSnapshotTime(summary?.latest_snapshot ?? null)}</span>
              </div>

              <div className="opportunity-table">
                <div className="opportunity-row table-head">
                  <span>#</span>
                  <span>item</span>
                  <span>buy price</span>
                  <span>sell price</span>
                <span>spread</span>
                <span>confidence</span>
              </div>
                {filteredItems.map((item, index) => (
                  <div className="opportunity-row" key={item.item_id}>
                    <span>{index + 1}</span>
                    <span className="item-cell">
                      <ItemIcon item={item} />
                      <span>
                        <b>{formatItemName(item.item_id)}</b>
                        <small>{item.item_id}</small>
                      </span>
                    </span>
                    <span>{formatCompact(item.buy_price)}</span>
                    <span>{formatCompact(item.sell_price)}</span>
                    <span className="positive">{spreadPercent(item).toFixed(2)}%</span>
                    <span className="table-score">
                      <span>{scoreItem(item)}</span>
                    </span>
                  </div>
                ))}
              </div>
            </article>

            <article className="panel">
              <div className="panel-heading">
                <h2>npc arbitrage</h2>
                <span>{isArbitrageLoading ? 'updating' : 'liquidity filtered'}</span>
              </div>

              {isArbitrageLoading ? (
                <p className="empty-state">loading npc arbitrage...</p>
              ) : npcArbitrageItems.length > 0 ? (
                <div className="arbitrage-table">
                  <div className="arbitrage-row table-head">
                    <span>#</span>
                    <span>item</span>
                    <span>bazaar buy</span>
                    <span>npc sell</span>
                    <span>profit per item</span>
                    <span>risk</span>
                  </div>
                  {npcArbitrageItems.slice(0, 5).map((item, index) => (
                    <button
                      className={
                        selectedNpcItemId === item.item_id
                          ? 'arbitrage-row selected'
                          : 'arbitrage-row'
                      }
                      key={item.item_id}
                      type="button"
                      onClick={() => setSelectedNpcItemId(item.item_id)}
                    >
                      <span>{index + 1}</span>
                      <span className="arbitrage-item-cell">
                        <b>{item.item_name}</b>
                        <small>
                          {item.item_id}
                          <span className={getNpcQualityClass(item)}>
                            {getNpcQualityLabel(item)}
                          </span>
                        </small>
                      </span>
                      <span>{formatCompact(item.bazaar_buy_price)}</span>
                      <span>{formatCompact(item.npc_sell_price)}</span>
                      <span className="positive">{formatCompact(item.profit_per_item)}</span>
                      <span className={getNpcQualityClass(item)}>{item.risk_label}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="empty-state">
                  run the item metadata collector to calculate npc arbitrage.
                </p>
              )}

              {selectedNpcItem ? (
                <div className="npc-detail-panel">
                  <div className="panel-heading compact-heading">
                    <div>
                      <h3>{selectedNpcItem.item_name}</h3>
                      <span>{selectedNpcItem.item_id}</span>
                    </div>
                    <span className={getNpcQualityClass(selectedNpcItem)}>
                      {selectedNpcItem.risk_label}
                    </span>
                  </div>

                  {isNpcDetailLoading ? (
                    <p className="empty-state">loading item history...</p>
                  ) : selectedNpcDetail ? (
                    <>
                      <div className="npc-detail-grid">
                        <DetailMetric
                          label="trend"
                          value={getNpcTrend(selectedNpcDetail)}
                          hint="recent profit direction"
                          positive={getNpcTrend(selectedNpcDetail) === 'improving'}
                        />
                        <DetailMetric
                          label="consistency"
                          value={`${selectedNpcDetail.profitable_snapshots} / ${selectedNpcDetail.observed_snapshots}`}
                          hint="profitable snapshots"
                          positive={selectedNpcDetail.profit_consistency >= 0.75}
                        />
                        <DetailMetric
                          label="latest profit"
                          value={formatCompact(selectedNpcDetail.latest.profit_per_item)}
                          hint="coins per item"
                          positive={selectedNpcDetail.latest.profit_per_item > 0}
                        />
                        <DetailMetric
                          label="risk score"
                          value={`${Math.round(selectedNpcDetail.risk_score * 100)} / 100`}
                          hint={selectedNpcDetail.risk_label}
                          positive={selectedNpcDetail.risk_score < 0.3}
                        />
                        <DetailMetric
                          label="price jump"
                          value={formatPercent(selectedNpcDetail.max_recent_price_jump)}
                          hint="largest recent move"
                          positive={selectedNpcDetail.max_recent_price_jump < 0.25}
                        />
                        <DetailMetric
                          label="spread"
                          value={formatPercent(selectedNpcDetail.spread_percent)}
                          hint={selectedNpcDetail.risk_reasons[0] ?? 'risk check'}
                          positive={selectedNpcDetail.spread_percent < 0.2}
                        />
                      </div>

                      <div className="history-table">
                        <MiniLineChart
                          label={`${selectedNpcItem.item_name} npc profit history`}
                          values={selectedNpcProfitChart}
                        />
                        {selectedNpcDetail.history.slice(0, 5).map((row) => (
                          <div className="history-row" key={row.collected_at}>
                            <span>{formatSnapshotTime(row.collected_at)}</span>
                            <b className={row.is_profitable ? 'positive' : ''}>
                              {formatCompact(row.profit_per_item)}
                            </b>
                            <span>{formatCompact(row.sell_volume)} volume</span>
                            <span>{formatNumber(row.sell_orders)} orders</span>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <p className="empty-state">no recent history for this item.</p>
                  )}
                </div>
              ) : null}
            </article>
          </div>

          <aside className="right-column">
            <article className="panel forecast-panel">
              <h2>forecast snapshot</h2>
              <div className="forecast-chart-layout">
                <div className="sparkline">
                  <MiniLineChart label="investment momentum forecast" values={forecastChartValues} />
                </div>
                <div className="forecast-copy">
                  <strong>
                    {investmentItems[0] ? `${formatPercent(investmentItems[0].gain_percent)} top climb` : 'building signal'}
                  </strong>
                  <span>
                    {investmentItems[0]
                      ? `${investmentItems[0].item_name} leads recent bazaar momentum.`
                      : 'collect more snapshots for stronger price trends.'}
                  </span>
                </div>
              </div>
              <p>
                {isSnapshotStale && snapshotAgeMinutes !== null
                  ? `latest snapshot is ${formatCompact(snapshotAgeMinutes)} minutes old.`
                  : 'prices with high liquidity and positive spreads are prioritized for review.'}
              </p>
              <div className="confidence-line">
                <span className="score-badge">{marketScore}</span>
                <strong>baseline confidence</strong>
              </div>
            </article>

            <article className="panel compact-panel">
              <div className="panel-heading">
                <h2>items heating up</h2>
                <span>price momentum</span>
              </div>
              {investmentItems.length > 0 ? (
                investmentItems.map((item, index) => (
                  <div className="ranking-card" key={item.item_id}>
                    <span className="rank-number">{index + 1}</span>
                    <div>
                      <b>{item.item_name}</b>
                      <small>
                        {formatPercent(item.gain_percent)} gain ·{' '}
                        {formatCompact(item.average_volume)} volume
                      </small>
                    </div>
                    <MiniLineChart
                      compact
                      label={`${item.item_name} price climb`}
                      values={[
                        item.oldest_midpoint_price,
                        (item.oldest_midpoint_price + item.latest_midpoint_price) / 2,
                        item.latest_midpoint_price,
                      ]}
                    />
                    <span className={getMomentumLabelClass(item)}>
                      {getMomentumLabel(item)}
                    </span>
                  </div>
                ))
              ) : (
                <p className="empty-state">waiting for more price history.</p>
              )}
            </article>

            <article className="panel compact-panel">
              <div className="panel-heading">
                <h2>rankings preview</h2>
                <span>top scored</span>
              </div>
              {topRankings.map((item, index) => (
                <div className="ranking-card" key={item.item_id}>
                  <span className="rank-number">{index + 1}</span>
                  <div>
                    <b>{formatItemName(item.item_id)}</b>
                    <small>
                      {formatCompact(item.buy_volume + item.sell_volume)} volume ·{' '}
                      {spreadPercent(item).toFixed(2)}% spread
                    </small>
                  </div>
                  <span className="table-score">
                    <span>{scoreItem(item)}</span>
                  </span>
                </div>
              ))}
            </article>

            <article className="panel compact-panel">
              <div className="panel-heading">
                <h2>recent research</h2>
                <span>view all -&gt;</span>
              </div>
              <div className="insight-row">
                <FileText size={16} />
                <div>
                  <b>npc arbitrage baseline</b>
                  <small>metadata joined with latest bazaar snapshot</small>
                </div>
              </div>
              <div className="insight-row">
                <FileText size={16} />
                <div>
                  <b>liquidity review</b>
                  <small>npc flips must hold across recent snapshots</small>
                </div>
              </div>
              <div className="insight-row">
                <FileText size={16} />
                <div>
                  <b>spread behavior snapshot</b>
                  <small>wide spreads need manipulation checks</small>
                </div>
              </div>
            </article>

            <article className="panel compact-panel">
              <div className="panel-heading">
                <h2>system status</h2>
                {latestJob ? (
                  <span className={getJobStatusClass(latestJob.status)}>{latestJob.status}</span>
                ) : (
                  <span>no runs</span>
                )}
              </div>

              {latestJob ? (
                <>
                  <div className="job-run-grid">
                    <DetailMetric
                      label="last run"
                      value={formatSnapshotTime(latestJob.started_at)}
                      hint={latestJob.job_type}
                      positive={latestJob.status === 'success'}
                    />
                    <DetailMetric
                      label="products"
                      value={
                        latestJob.products_collected !== null
                          ? formatCompact(latestJob.products_collected)
                          : 'n/a'
                      }
                      hint="collected"
                    />
                    <DetailMetric
                      label="signals"
                      value={latestJob.signals_generated ?? 'n/a'}
                      hint="generated"
                    />
                    <DetailMetric
                      label="backtests"
                      value={Object.values(latestJob.backtests_evaluated).reduce(
                        (sum, count) => sum + count,
                        0,
                      )}
                      hint={formatBacktestCounts(latestJob.backtests_evaluated)}
                    />
                  </div>

                  <div className="job-run-list">
                    {jobRuns.slice(0, 3).map((job) => (
                      <div className="job-run-row" key={job.id}>
                        <span className={getJobStatusClass(job.status)}>{job.status}</span>
                        <div>
                          <b>{formatSnapshotTime(job.started_at)}</b>
                          <small>{job.message ?? job.job_type}</small>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <p className="empty-state">scheduler runs will appear after the next cycle.</p>
              )}
            </article>

            <article className="panel compact-panel">
              <div className="panel-heading">
                <h2>backtest results</h2>
                <span>
                  {backtestSummary?.latest_evaluated_at
                    ? formatSnapshotTime(backtestSummary.latest_evaluated_at)
                    : 'not evaluated'}
                </span>
              </div>

              {backtestSummary && backtestSummary.total_results > 0 ? (
                <>
                  <div className="backtest-summary-grid">
                    <DetailMetric
                      label="win rate"
                      value={`${backtestWinRate}%`}
                      hint={`${backtestSummary.successful_results} successful`}
                      positive={backtestSummary.win_rate >= 0.5}
                    />
                    <DetailMetric
                      label="avg return"
                      value={formatPercent(backtestSummary.average_return)}
                      hint="evaluated signals"
                      positive={backtestSummary.average_return >= 0}
                    />
                    <DetailMetric
                      label="median"
                      value={formatPercent(backtestSummary.median_return)}
                      hint="middle result"
                      positive={backtestSummary.median_return >= 0}
                    />
                    <DetailMetric
                      label="drawdown"
                      value={formatPercent(backtestSummary.average_drawdown)}
                      hint="average path low"
                    />
                  </div>

                  <div className="backtest-result-list">
                    {backtestResults.map((result) => (
                      <div className="backtest-result-row" key={result.id}>
                        <span
                          className={
                            result.was_successful ? 'alert-dot positive-dot' : 'alert-dot risk-dot'
                          }
                        />
                        <div>
                          <b>{result.item_name}</b>
                          <small>
                            {result.signal_type} - {result.horizon}
                          </small>
                        </div>
                        <strong className={result.return_percent >= 0 ? 'positive' : ''}>
                          {formatPercent(result.return_percent)}
                        </strong>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <p className="empty-state">
                  run backtest evaluation after signals have a future snapshot.
                </p>
              )}
            </article>

            <article className="panel compact-panel">
              <div className="panel-heading">
                <h2>active alerts</h2>
                <span>view all -&gt;</span>
              </div>
              {signals.length > 0 ? (
                signals.slice(0, 4).map((signal) => (
                  <div className="alert-row" key={`${signal.signal_type}-${signal.item_id}`}>
                    <span className={getSignalDotClass(signal)} />
                    <div>
                      <b>{signal.title}</b>
                      <small>
                        {signal.item_name} · {getSignalShortText(signal)}
                      </small>
                    </div>
                  </div>
                ))
              ) : (
                <p className="empty-state">waiting for live signals.</p>
              )}
            </article>
          </aside>
        </section>
      </main>
    </div>
  )
}

export default App
