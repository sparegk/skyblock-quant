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

type NpcFilterKey =
  | 'minSellVolume'
  | 'minSellOrders'
  | 'maxProfitMargin'
  | 'historySnapshots'
  | 'minProfitableSnapshots'

type NpcFilters = Record<NpcFilterKey, number>

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
  if (item.profit_consistency < 0.75) {
    return 'not steady'
  }

  if (item.profit_margin >= 0.2) {
    return 'wide margin'
  }

  if (item.sell_volume < 20_000 || item.sell_orders < 50) {
    return 'low supply'
  }

  return 'stable'
}

function getNpcQualityClass(item: NpcArbitrageItem) {
  const label = getNpcQualityLabel(item)

  if (label === 'stable') {
    return 'quality-badge stable'
  }

  if (label === 'wide margin') {
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

function clampNumber(value: number, min: number, max: number) {
  if (!Number.isFinite(value)) {
    return min
  }

  return Math.min(Math.max(value, min), max)
}

const defaultNpcFilters: NpcFilters = {
  minSellVolume: 10_000,
  minSellOrders: 25,
  maxProfitMargin: 25,
  historySnapshots: 5,
  minProfitableSnapshots: 2,
}

const npcFilterPresets: Record<'strict' | 'balanced' | 'loose', NpcFilters> = {
  strict: {
    minSellVolume: 50_000,
    minSellOrders: 75,
    maxProfitMargin: 15,
    historySnapshots: 5,
    minProfitableSnapshots: 4,
  },
  balanced: defaultNpcFilters,
  loose: {
    minSellVolume: 2_500,
    minSellOrders: 10,
    maxProfitMargin: 40,
    historySnapshots: 3,
    minProfitableSnapshots: 1,
  },
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
  const [selectedNpcItemId, setSelectedNpcItemId] = useState<string | null>(null)
  const [selectedNpcDetail, setSelectedNpcDetail] = useState<NpcArbitrageDetail | null>(null)
  const [npcFilters, setNpcFilters] = useState<NpcFilters>(defaultNpcFilters)
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

        const [summaryResponse, itemsResponse, investmentResponse] = await Promise.all([
          fetch(`${API_BASE_URL}/api/bazaar/summary`),
          fetch(`${API_BASE_URL}/api/bazaar/latest?limit=40`),
          fetch(`${API_BASE_URL}/api/investments/momentum?limit=5`),
        ])

        if (!summaryResponse.ok || !itemsResponse.ok || !investmentResponse.ok) {
          throw new Error('Backend API request failed.')
        }

        const summaryData = (await summaryResponse.json()) as MarketSummary
        const itemsData = (await itemsResponse.json()) as { items: BazaarItem[] }
        const investmentData = (await investmentResponse.json()) as {
          items: InvestmentMomentumItem[]
        }

        setSummary(summaryData)
        setItems(itemsData.items)
        setInvestmentItems(investmentData.items)
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
          limit: '8',
          min_sell_volume: String(npcFilters.minSellVolume),
          min_sell_orders: String(npcFilters.minSellOrders),
          max_profit_margin: String(npcFilters.maxProfitMargin / 100),
          history_snapshots: String(npcFilters.historySnapshots),
          min_profitable_snapshots: String(npcFilters.minProfitableSnapshots),
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

          return data.items[0]?.item_id ?? null
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
  }, [npcFilters])

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
          history_snapshots: String(npcFilters.historySnapshots),
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
  }, [npcFilters.historySnapshots, selectedNpcItemId])

  function updateNpcFilter(filter: NpcFilterKey, value: number) {
    setNpcFilters((current) => {
      const limits: Record<NpcFilterKey, [number, number]> = {
        minSellVolume: [0, 10_000_000],
        minSellOrders: [0, 10_000],
        maxProfitMargin: [1, 1000],
        historySnapshots: [1, 100],
        minProfitableSnapshots: [1, current.historySnapshots],
      }
      const [min, max] = limits[filter]
      const nextValue = clampNumber(value, min, max)

      return {
        ...current,
        [filter]: nextValue,
        ...(filter === 'historySnapshots' && current.minProfitableSnapshots > nextValue
          ? { minProfitableSnapshots: nextValue }
          : {}),
      }
    })
  }

  function applyNpcFilters(filters: NpcFilters) {
    setNpcFilters(filters)
  }

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
  const alertItems = rankedItems.slice(0, 3)
  const averageSpread =
    rankedItems.length > 0
      ? rankedItems.reduce((sum, item) => sum + Math.max(spreadPercent(item), 0), 0) /
        rankedItems.length
      : 0
  const stableNpcFlips = npcArbitrageItems.filter(
    (item) => item.profit_consistency >= 0.75 && item.sell_volume >= 20_000,
  ).length
  const forecastChartValues =
    investmentItems.length > 0
      ? investmentItems.map((item) => item.momentum_score)
      : rankedItems.slice(0, 8).map((item) => scoreItem(item))
  const selectedNpcProfitChart =
    selectedNpcDetail?.history
      .slice()
      .reverse()
      .map((row) => row.profit_per_item) ?? []

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
              <span>stable npc flips</span>
              <strong>{stableNpcFlips}</strong>
              <p>
                {npcArbitrageItems.length > 0
                  ? `${npcArbitrageItems.length} filtered flips`
                  : 'waiting for arbitrage data'}
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

              <div className="filter-actions" aria-label="npc arbitrage presets">
                <button type="button" onClick={() => applyNpcFilters(npcFilterPresets.strict)}>
                  strict
                </button>
                <button type="button" onClick={() => applyNpcFilters(npcFilterPresets.balanced)}>
                  balanced
                </button>
                <button type="button" onClick={() => applyNpcFilters(npcFilterPresets.loose)}>
                  loose
                </button>
                <button type="button" onClick={() => applyNpcFilters(defaultNpcFilters)}>
                  reset
                </button>
              </div>

              <div className="filter-grid" aria-label="npc arbitrage filters">
                <label>
                  <span>min volume</span>
                  <input
                    min="0"
                    step="1000"
                    type="number"
                    value={npcFilters.minSellVolume}
                    onChange={(event) =>
                      updateNpcFilter('minSellVolume', Number(event.target.value))
                    }
                  />
                </label>
                <label>
                  <span>min orders</span>
                  <input
                    min="0"
                    step="5"
                    type="number"
                    value={npcFilters.minSellOrders}
                    onChange={(event) =>
                      updateNpcFilter('minSellOrders', Number(event.target.value))
                    }
                  />
                </label>
                <label>
                  <span>max margin</span>
                  <input
                    min="1"
                    max="1000"
                    step="1"
                    type="number"
                    value={npcFilters.maxProfitMargin}
                    onChange={(event) =>
                      updateNpcFilter('maxProfitMargin', Number(event.target.value))
                    }
                  />
                </label>
                <label>
                  <span>history</span>
                  <input
                    min="1"
                    max="100"
                    step="1"
                    type="number"
                    value={npcFilters.historySnapshots}
                    onChange={(event) =>
                      updateNpcFilter('historySnapshots', Number(event.target.value))
                    }
                  />
                </label>
                <label>
                  <span>profitable</span>
                  <input
                    min="1"
                    max={npcFilters.historySnapshots}
                    step="1"
                    type="number"
                    value={npcFilters.minProfitableSnapshots}
                    onChange={(event) =>
                      updateNpcFilter('minProfitableSnapshots', Number(event.target.value))
                    }
                  />
                </label>
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
                    <span>profit</span>
                    <span>hist. profit</span>
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
                      <span>{formatCompact(item.history_adjusted_profit)}</span>
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
                      {getNpcQualityLabel(selectedNpcItem)}
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
                <h2>active alerts</h2>
                <span>view all -&gt;</span>
              </div>
              {alertItems.map((item) => (
                <div className="alert-row" key={item.item_id}>
                  <span className="alert-dot" />
                  <div>
                    <b>{formatItemName(item.item_id)}</b>
                    <small>
                      {spreadPercent(item).toFixed(2)}% spread ·{' '}
                      {formatCompact(item.buy_volume + item.sell_volume)} volume
                    </small>
                  </div>
                </div>
              ))}
            </article>
          </aside>
        </section>
      </main>
    </div>
  )
}

export default App
