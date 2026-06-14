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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

type NpcFilterSettings = {
  minSellVolume: number
  minSellOrders: number
  maxProfitMargin: number
  historySnapshots: number
  minProfitableSnapshots: number
}

const NPC_FILTER_STORAGE_KEY = 'skyblock-quant:npc-filters'

const DEFAULT_NPC_FILTERS: NpcFilterSettings = {
  minSellVolume: 10000,
  minSellOrders: 25,
  maxProfitMargin: 0.25,
  historySnapshots: 5,
  minProfitableSnapshots: 2,
}

const NPC_FILTER_PRESETS: Array<{
  label: string
  value: NpcFilterSettings
}> = [
  {
    label: 'balanced',
    value: DEFAULT_NPC_FILTERS,
  },
  {
    label: 'strict',
    value: {
      minSellVolume: 25000,
      minSellOrders: 50,
      maxProfitMargin: 0.18,
      historySnapshots: 8,
      minProfitableSnapshots: 5,
    },
  },
  {
    label: 'loose',
    value: {
      minSellVolume: 2500,
      minSellOrders: 10,
      maxProfitMargin: 0.4,
      historySnapshots: 3,
      minProfitableSnapshots: 1,
    },
  },
]

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
  estimated_stack_size: number
  profit_per_sell_action: number
  interaction_efficiency_score: number
  action_adjusted_profit: number
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
  estimated_stack_size: number
  profit_per_sell_action: number
  interaction_efficiency_score: number
  action_adjusted_profit: number
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
  projected_rise_percent: number
  projected_target_price: number
  projection_confidence: number
  estimated_stack_size: number
  storage_slot_value: number
  storage_efficiency_score: number
  investment_score: number
  projected_profit_per_unit: number
  projected_profit_per_slot: number
  profit_efficiency_score: number
}

type OccurrenceInvestmentItem = {
  item_id: string
  item_name: string
  category: string | null
  tier: string | null
  latest_midpoint_price: number
  catalyst_type: string
  catalyst_summary: string
  thesis: string
  source_label: string
  source_url: string | null
  source_date: string | null
  confidence: number
  expected_impact: number
  urgency: string
  estimated_stack_size: number
  storage_slot_value: number
  storage_efficiency_score: number
  occurrence_score: number
  buy_volume: number
  sell_volume: number
  buy_orders: number
  sell_orders: number
  collected_at: string | null
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
  projection_results: number
  projection_hit_rate: number
  average_projection_error: number
  average_absolute_projection_error: number
  average_projected_return: number
  average_realized_projection_return: number
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
  expected_return: number | null
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

function sanitizeNpcFilters(filters: Partial<NpcFilterSettings>): NpcFilterSettings {
  return {
    minSellVolume: Math.max(0, Number(filters.minSellVolume) || 0),
    minSellOrders: Math.max(0, Number(filters.minSellOrders) || 0),
    maxProfitMargin: Math.max(0.01, Number(filters.maxProfitMargin) || 0.01),
    historySnapshots: Math.max(1, Number(filters.historySnapshots) || 1),
    minProfitableSnapshots: Math.max(1, Number(filters.minProfitableSnapshots) || 1),
  }
}

function npcFiltersMatch(left: NpcFilterSettings, right: NpcFilterSettings) {
  return (
    left.minSellVolume === right.minSellVolume &&
    left.minSellOrders === right.minSellOrders &&
    left.maxProfitMargin === right.maxProfitMargin &&
    left.historySnapshots === right.historySnapshots &&
    left.minProfitableSnapshots === right.minProfitableSnapshots
  )
}

function loadNpcFilters() {
  if (typeof window === 'undefined') {
    return DEFAULT_NPC_FILTERS
  }

  try {
    const savedFilters = window.localStorage.getItem(NPC_FILTER_STORAGE_KEY)

    if (!savedFilters) {
      return DEFAULT_NPC_FILTERS
    }

    return sanitizeNpcFilters({
      ...DEFAULT_NPC_FILTERS,
      ...(JSON.parse(savedFilters) as Partial<NpcFilterSettings>),
    })
  } catch {
    return DEFAULT_NPC_FILTERS
  }
}

function useDebouncedValue<T>(value: T, delayMs: number) {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedValue(value), delayMs)

    return () => window.clearTimeout(timeout)
  }, [delayMs, value])

  return debouncedValue
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

function scoreInvestmentItem(item: InvestmentMomentumItem) {
  const gainScore = Math.min(item.projected_rise_percent * 220, 45)
  const confidenceScore = Math.min(item.projection_confidence * 26, 26)
  const profitScore = Math.min(item.profit_efficiency_score * 0.2, 20)
  const steadyScore = Math.min(item.rising_steps * 7, 18)
  const jumpPenalty = item.max_single_jump >= 0.25 ? 12 : 0
  return Math.max(1, Math.round(gainScore + confidenceScore + profitScore + steadyScore - jumpPenalty))
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

function getNpcRiskReasonSummary(item: NpcArbitrageItem | NpcArbitrageDetail) {
  return item.risk_reasons[0] ?? 'risk checks are still building'
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

function ItemIcon({ item }: { item: { item_id: string } }) {
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
  const [occurrenceItems, setOccurrenceItems] = useState<OccurrenceInvestmentItem[]>([])
  const [signals, setSignals] = useState<MarketSignal[]>([])
  const [backtestSummary, setBacktestSummary] = useState<BacktestSummary | null>(null)
  const [backtestResults, setBacktestResults] = useState<BacktestResult[]>([])
  const [jobRuns, setJobRuns] = useState<JobRun[]>([])
  const [selectedNpcItemId, setSelectedNpcItemId] = useState<string | null>(null)
  const [selectedNpcDetail, setSelectedNpcDetail] = useState<NpcArbitrageDetail | null>(null)
  const [query, setQuery] = useState('')
  const [showNpcFilters, setShowNpcFilters] = useState(false)
  const [npcFilters, setNpcFilters] = useState<NpcFilterSettings>(() => loadNpcFilters())
  const debouncedNpcFilters = useDebouncedValue(npcFilters, 350)
  const [isLoading, setIsLoading] = useState(true)
  const [isArbitrageLoading, setIsArbitrageLoading] = useState(true)
  const [isNpcDetailLoading, setIsNpcDetailLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    window.localStorage.setItem(NPC_FILTER_STORAGE_KEY, JSON.stringify(npcFilters))
  }, [npcFilters])

  useEffect(() => {
    async function loadDashboardData() {
      try {
        setIsLoading(true)
        setError(null)

        const [
          summaryResponse,
          itemsResponse,
          investmentResponse,
          occurrenceResponse,
          signalsResponse,
          backtestSummaryResponse,
          backtestResultsResponse,
          jobsResponse,
        ] =
          await Promise.all([
          fetch(`${API_BASE_URL}/api/bazaar/summary`),
          fetch(`${API_BASE_URL}/api/bazaar/latest?limit=40`),
          fetch(`${API_BASE_URL}/api/investments/momentum?limit=10`),
          fetch(`${API_BASE_URL}/api/investments/occurrences?limit=5`),
          fetch(`${API_BASE_URL}/api/signals/latest?limit=8`),
          fetch(`${API_BASE_URL}/api/backtests/summary`),
          fetch(`${API_BASE_URL}/api/backtests/results?limit=5`),
          fetch(`${API_BASE_URL}/api/jobs/latest?limit=5`),
        ])

        if (
          !summaryResponse.ok ||
          !itemsResponse.ok ||
          !investmentResponse.ok ||
          !occurrenceResponse.ok ||
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
        const occurrenceData = (await occurrenceResponse.json()) as {
          items: OccurrenceInvestmentItem[]
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
        setOccurrenceItems(occurrenceData.items)
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

        const params = new URLSearchParams({
          limit: '10',
          min_sell_volume: String(debouncedNpcFilters.minSellVolume),
          min_sell_orders: String(debouncedNpcFilters.minSellOrders),
          max_profit_margin: String(debouncedNpcFilters.maxProfitMargin),
          history_snapshots: String(debouncedNpcFilters.historySnapshots),
          min_profitable_snapshots: String(debouncedNpcFilters.minProfitableSnapshots),
        })
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
  }, [debouncedNpcFilters])

  useEffect(() => {
    if (!selectedNpcItemId) {
      return
    }

    const request = new AbortController()

    async function loadNpcDetail() {
      try {
        setIsNpcDetailLoading(true)
        const params = new URLSearchParams({
          history_snapshots: String(debouncedNpcFilters.historySnapshots),
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
  }, [debouncedNpcFilters.historySnapshots, selectedNpcItemId])

  const rankedItems = useMemo(
    () => [...items].sort((a, b) => scoreItem(b) - scoreItem(a)),
    [items],
  )

  const featuredInvestment = investmentItems[0]
  const featuredOccurrenceInvestment = occurrenceItems[0]

  const filteredInvestments = useMemo(() => {
    const cleanQuery = query.trim().toLowerCase()
    const watchItems = featuredInvestment
      ? investmentItems.filter((item) => item.item_id !== featuredInvestment.item_id)
      : investmentItems

    if (!cleanQuery) {
      return watchItems.slice(0, 10)
    }

    return watchItems
      .filter((item) => item.item_name.toLowerCase().includes(cleanQuery))
      .slice(0, 10)
  }, [featuredInvestment, query, investmentItems])

  const marketScore = featuredInvestment ? Math.min(scoreInvestmentItem(featuredInvestment), 99) : 0
  const bestNpcProfit = npcArbitrageItems[0]?.profit_per_item ?? 0
  const selectedNpcItem =
    npcArbitrageItems.find((item) => item.item_id === selectedNpcItemId) ?? null
  const snapshotAgeMinutes = getSnapshotAgeMinutes(summary?.latest_snapshot ?? null)
  const isSnapshotStale = snapshotAgeMinutes !== null && snapshotAgeMinutes > 20
  const bestInvestmentGain = featuredInvestment?.gain_percent ?? 0
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
  const investmentFitItems = investmentItems.slice(1, 4)

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
            <button
              className={showNpcFilters ? 'active-filter-button' : ''}
              type="button"
              aria-expanded={showNpcFilters}
              onClick={() => setShowNpcFilters((current) => !current)}
            >
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

        {showNpcFilters ? (
          <section className="filter-panel" aria-label="Bazaar to NPC flip risk filters">
            <div className="filter-presets" aria-label="Bazaar to NPC flip filter presets">
              {NPC_FILTER_PRESETS.map((preset) => (
                <button
                  className={npcFiltersMatch(npcFilters, preset.value) ? 'active-preset' : ''}
                  type="button"
                  key={preset.label}
                  onClick={() => setNpcFilters(preset.value)}
                >
                  {preset.label}
                </button>
              ))}
            </div>
            <label>
              <span>min volume</span>
              <input
                type="number"
                min="0"
                step="1000"
                value={npcFilters.minSellVolume}
                onChange={(event) =>
                  setNpcFilters((current) =>
                    sanitizeNpcFilters({
                      ...current,
                      minSellVolume: Number(event.target.value),
                    }),
                  )
                }
              />
            </label>
            <label>
              <span>min orders</span>
              <input
                type="number"
                min="0"
                step="5"
                value={npcFilters.minSellOrders}
                onChange={(event) =>
                  setNpcFilters((current) =>
                    sanitizeNpcFilters({
                      ...current,
                      minSellOrders: Number(event.target.value),
                    }),
                  )
                }
              />
            </label>
            <label>
              <span>max margin</span>
              <input
                type="number"
                min="0.01"
                max="10"
                step="0.01"
                value={npcFilters.maxProfitMargin}
                onChange={(event) =>
                  setNpcFilters((current) =>
                    sanitizeNpcFilters({
                      ...current,
                      maxProfitMargin: Number(event.target.value),
                    }),
                  )
                }
              />
            </label>
            <label>
              <span>history</span>
              <input
                type="number"
                min="1"
                max="100"
                step="1"
                value={npcFilters.historySnapshots}
                onChange={(event) =>
                  setNpcFilters((current) =>
                    sanitizeNpcFilters({
                      ...current,
                      historySnapshots: Number(event.target.value),
                    }),
                  )
                }
              />
            </label>
            <label>
              <span>profitable</span>
              <input
                type="number"
                min="1"
                max="100"
                step="1"
                value={npcFilters.minProfitableSnapshots}
                onChange={(event) =>
                  setNpcFilters((current) =>
                    sanitizeNpcFilters({
                      ...current,
                      minProfitableSnapshots: Number(event.target.value),
                    }),
                  )
                }
              />
            </label>
            <button type="button" onClick={() => setNpcFilters(DEFAULT_NPC_FILTERS)}>
              reset
            </button>
          </section>
        ) : null}

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
              <span>Bazaar to NPC</span>
              <strong>{npcArbitrageItems.length}</strong>
              <p>
                {bestNpcProfit > 0
                  ? `${formatCompact(bestNpcProfit)} best flip profit`
                  : 'waiting for metadata'}
              </p>
            </div>
          </article>
          <article className="metric-card">
            <div className="metric-icon purple">
              <Gauge size={30} />
            </div>
            <div>
              <span>rising items</span>
              <strong>{investmentItems.length}</strong>
              <p>
                {bestInvestmentGain > 0
                  ? `${formatPercent(bestInvestmentGain)} strongest move`
                  : 'collecting price history'}
              </p>
            </div>
          </article>
          <article className="metric-card">
            <div className="metric-icon orange">
              <LineChart size={30} />
            </div>
            <div>
              <span>signal hit rate</span>
              <strong>{backtestSummary?.total_results ? `${backtestWinRate}%` : 'n/a'}</strong>
              <p>
                {backtestSummary?.total_results
                  ? `${backtestSummary.successful_results} of ${backtestSummary.total_results} tested picks worked`
                  : 'waiting for tested picks'}
              </p>
            </div>
          </article>
        </section>

        <section className="dashboard-grid">
          <div className="left-column">
            <article className="panel market-watch-panel">
              <div className="panel-heading">
                <h2>featured investment watch</h2>
                <span>{formatSnapshotTime(summary?.latest_snapshot ?? null)}</span>
              </div>

              {isLoading ? (
                <p className="empty-state">loading bazaar snapshot...</p>
              ) : featuredInvestment ? (
                <>
                  <div className="featured-strip">
                    <div className="featured-head compact-featured-head">
                      <ItemIcon item={featuredInvestment} />
                      <div>
                        <h3>{featuredInvestment.item_name}</h3>
                        <p>{featuredInvestment.item_id}</p>
                      </div>
                    </div>

                    <div className="featured-stat-row">
                      <DetailMetric
                        label="price"
                        value={formatCompact(featuredInvestment.midpoint_price)}
                        hint="bazaar midpoint"
                      />
                      <DetailMetric
                        label="recent move"
                        value={formatPercent(featuredInvestment.gain_percent)}
                        hint={`${featuredInvestment.observed_snapshots} snapshots`}
                        positive
                      />
                      <DetailMetric
                        label="potential rise"
                        value={formatPercent(featuredInvestment.projected_rise_percent)}
                        hint={`${formatCompact(featuredInvestment.projected_target_price)} target`}
                        positive
                      />
                      <DetailMetric
                        label="slot profit"
                        value={formatCompact(featuredInvestment.projected_profit_per_slot)}
                        hint={`${featuredInvestment.estimated_stack_size} stack - ${formatCompact(featuredInvestment.storage_slot_value)} slot`}
                        positive={featuredInvestment.projected_profit_per_slot > 0}
                      />
                      <DetailMetric
                        label="confidence"
                        value={<span className="score-badge">{scoreInvestmentItem(featuredInvestment)}</span>}
                        hint="momentum score"
                        positive
                      />
                    </div>
                  </div>

                  <div className="table-section-heading">
                    <h3>items to watch</h3>
                    <span>next 10</span>
                  </div>

                  <div className="opportunity-table">
                    <div className="opportunity-row table-head">
                      <span>#</span>
                      <span>item</span>
                      <span>price</span>
                      <span>recent move</span>
                      <span>potential rise</span>
                      <span>slot profit</span>
                      <span>confidence</span>
                    </div>
                    {filteredInvestments.length > 0 ? filteredInvestments.map((item, index) => (
                      <div className="opportunity-row" key={item.item_id}>
                        <span>{index + 1}</span>
                        <span className="item-cell">
                          <ItemIcon item={item} />
                          <span>
                            <b>{item.item_name}</b>
                            <small>{item.item_id}</small>
                          </span>
                        </span>
                        <span>{formatCompact(item.midpoint_price)}</span>
                        <span className="positive">{formatPercent(item.gain_percent)}</span>
                        <span className="projection-cell">
                          <b>{formatPercent(item.projected_rise_percent)}</b>
                          <small>{formatCompact(item.projected_target_price)} target</small>
                        </span>
                        <span className="projection-cell">
                          <b>{formatCompact(item.projected_profit_per_slot)}</b>
                          <small>
                            {item.estimated_stack_size} stack - {formatCompact(item.storage_slot_value)} slot
                          </small>
                        </span>
                        <span className="table-score">
                          <span>{scoreInvestmentItem(item)}</span>
                        </span>
                      </div>
                    )) : (
                      <p className="empty-state">collect more snapshots to rank investment candidates.</p>
                    )}
                  </div>
                </>
              ) : (
                <p className="empty-state">collect more snapshots to find investment candidates.</p>
                )}
            </article>

            <article className="panel">
              <div className="panel-heading">
                <h2>Bazaar to NPC flips</h2>
                <span>
                  {isArbitrageLoading
                    ? 'updating'
                    : `${formatCompact(npcFilters.minSellVolume)} volume floor`}
                </span>
              </div>

              {isArbitrageLoading ? (
                <p className="empty-state">loading Bazaar to NPC flips...</p>
              ) : npcArbitrageItems.length > 0 ? (
                <div className="arbitrage-table">
                  <div className="arbitrage-row table-head">
                    <span>#</span>
                    <span>item</span>
                    <span>bazaar buy</span>
                    <span>npc sell</span>
                    <span>sell action</span>
                    <span>risk</span>
                  </div>
                  {npcArbitrageItems.slice(0, 10).map((item, index) => (
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
                      <span className="projection-cell">
                        <b className="positive">{formatCompact(item.profit_per_sell_action)}</b>
                        <small>{formatCompact(item.profit_per_item)} each</small>
                      </span>
                      <span className="risk-cell">
                        <span className={getNpcQualityClass(item)}>{item.risk_label}</span>
                        <small>{getNpcRiskReasonSummary(item)}</small>
                      </span>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="empty-state">
                  run the item metadata collector to calculate Bazaar to NPC flips.
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
                          label="sell action"
                          value={formatCompact(selectedNpcDetail.profit_per_sell_action)}
                          hint={`${formatCompact(selectedNpcDetail.latest.profit_per_item)} each - ${selectedNpcDetail.estimated_stack_size} stack`}
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

                      {selectedNpcDetail.risk_reasons.length > 0 ? (
                        <div className="risk-reason-list" aria-label="risk reasons">
                          {selectedNpcDetail.risk_reasons.map((reason) => (
                            <span key={reason}>{reason}</span>
                          ))}
                        </div>
                      ) : null}

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
                  : 'items with recent price strength and usable volume are prioritized for review.'}
              </p>
              <div className="confidence-line">
                <span className="score-badge">{marketScore}</span>
                <strong>baseline confidence</strong>
              </div>
            </article>

            <article className="panel occurrence-panel">
              <div className="panel-heading">
                <h2>occurrence investment</h2>
                <span>event catalyst</span>
              </div>
              {featuredOccurrenceInvestment ? (
                <>
                  <div className="occurrence-feature">
                    <span className="quality-badge stable">
                      {featuredOccurrenceInvestment.catalyst_type}
                    </span>
                    <h3>{featuredOccurrenceInvestment.item_name}</h3>
                    <p>{featuredOccurrenceInvestment.catalyst_summary}</p>
                  </div>
                  <div className="occurrence-metrics">
                    <DetailMetric
                      label="expected impact"
                      value={formatPercent(featuredOccurrenceInvestment.expected_impact)}
                      hint={featuredOccurrenceInvestment.urgency}
                      positive={featuredOccurrenceInvestment.expected_impact > 0}
                    />
                    <DetailMetric
                      label="confidence"
                      value={`${Math.round(featuredOccurrenceInvestment.confidence * 100)}%`}
                      hint={featuredOccurrenceInvestment.source_label}
                      positive={featuredOccurrenceInvestment.confidence >= 0.6}
                    />
                    <DetailMetric
                      label="slot value"
                      value={formatCompact(featuredOccurrenceInvestment.storage_slot_value)}
                      hint={`${featuredOccurrenceInvestment.estimated_stack_size} stack`}
                      positive={featuredOccurrenceInvestment.storage_slot_value >= 5_000}
                    />
                  </div>
                  <p className="panel-note">{featuredOccurrenceInvestment.thesis}</p>
                  {featuredOccurrenceInvestment.source_url ? (
                    <a className="source-link" href={featuredOccurrenceInvestment.source_url}>
                      source
                    </a>
                  ) : null}
                </>
              ) : (
                <p className="empty-state">
                  add trusted update, alpha, rumor, or video catalysts to the curated occurrence list.
                </p>
              )}
            </article>

            <article className="panel compact-panel">
              <div className="panel-heading">
                <h2>investment fit</h2>
                <span>slot profit</span>
              </div>
              {investmentFitItems.length > 0 ? (
                investmentFitItems.map((item, index) => (
                  <div className="ranking-card" key={item.item_id}>
                    <span className="rank-number">{index + 1}</span>
                    <div>
                      <b>{item.item_name}</b>
                      <small>
                        {formatCompact(item.projected_profit_per_slot)} slot profit -{' '}
                        {formatPercent(item.projected_rise_percent)} projected
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
                    <span className="table-score">
                      <span>{scoreInvestmentItem(item)}</span>
                    </span>
                  </div>
                ))
              ) : (
                <p className="empty-state">waiting for more practical investment candidates.</p>
              )}
            </article>

            <article className="panel compact-panel">
              <div className="panel-heading">
                <h2>recent research</h2>
                <span>view all -&gt;</span>
              </div>
              <div className="insight-row">
                <FileText size={16} />
                <div>
                  <b>Bazaar to NPC baseline</b>
                  <small>metadata joined with latest bazaar snapshot</small>
                </div>
              </div>
              <div className="insight-row">
                <FileText size={16} />
                <div>
                  <b>liquidity review</b>
                  <small>flips must hold across recent snapshots</small>
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

          </aside>
        </section>

        <section className="lower-dashboard-grid">
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
                  <DetailMetric
                    label="projection hit"
                    value={
                      backtestSummary.projection_results
                        ? `${Math.round(backtestSummary.projection_hit_rate * 100)}%`
                        : 'n/a'
                    }
                    hint={`${backtestSummary.projection_results} projected picks`}
                    positive={backtestSummary.projection_hit_rate >= 0.5}
                  />
                  <DetailMetric
                    label="projected"
                    value={formatPercent(backtestSummary.average_projected_return)}
                    hint="average expected rise"
                    positive={backtestSummary.average_projected_return > 0}
                  />
                  <DetailMetric
                    label="realized"
                    value={formatPercent(backtestSummary.average_realized_projection_return)}
                    hint="average actual return"
                    positive={backtestSummary.average_realized_projection_return >= 0}
                  />
                  <DetailMetric
                    label="avg error"
                    value={formatPercent(backtestSummary.average_absolute_projection_error)}
                    hint="absolute forecast miss"
                    positive={backtestSummary.average_absolute_projection_error <= 0.05}
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
              signals.slice(0, 6).map((signal) => (
                <div className="alert-row" key={`${signal.signal_type}-${signal.item_id}`}>
                  <span className={getSignalDotClass(signal)} />
                  <div>
                    <b>{signal.title}</b>
                    <small>
                      {signal.item_name} - {getSignalShortText(signal)}
                    </small>
                  </div>
                </div>
              ))
            ) : (
              <p className="empty-state">waiting for live signals.</p>
            )}
          </article>
        </section>
      </main>
    </div>
  )
}

export default App
