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
  buy_volume: number
  sell_volume: number
  buy_orders: number
  sell_orders: number
  collected_at: string
}

type DetailMetricProps = {
  label: string
  value: ReactNode
  hint: string
  positive?: boolean
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

function App() {
  const [summary, setSummary] = useState<MarketSummary | null>(null)
  const [items, setItems] = useState<BazaarItem[]>([])
  const [npcArbitrageItems, setNpcArbitrageItems] = useState<NpcArbitrageItem[]>([])
  const [query, setQuery] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadDashboardData() {
      try {
        setIsLoading(true)
        setError(null)

        const [summaryResponse, itemsResponse, arbitrageResponse] = await Promise.all([
          fetch(`${API_BASE_URL}/api/bazaar/summary`),
          fetch(`${API_BASE_URL}/api/bazaar/latest?limit=40`),
          fetch(`${API_BASE_URL}/api/arbitrage/npc?limit=8`),
        ])

        if (!summaryResponse.ok || !itemsResponse.ok || !arbitrageResponse.ok) {
          throw new Error('Backend API request failed.')
        }

        const summaryData = (await summaryResponse.json()) as MarketSummary
        const itemsData = (await itemsResponse.json()) as { items: BazaarItem[] }
        const arbitrageData = (await arbitrageResponse.json()) as {
          items: NpcArbitrageItem[]
        }

        setSummary(summaryData)
        setItems(itemsData.items)
        setNpcArbitrageItems(arbitrageData.items)
      } catch {
        setError('start the backend api to load live bazaar data')
      } finally {
        setIsLoading(false)
      }
    }

    loadDashboardData()
  }, [])

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
  const topRankings = rankedItems.slice(0, 3)
  const alertItems = rankedItems.slice(0, 3)
  const averageSpread =
    rankedItems.length > 0
      ? rankedItems.reduce((sum, item) => sum + Math.max(spreadPercent(item), 0), 0) /
        rankedItems.length
      : 0
  const totalVolume = rankedItems.reduce(
    (sum, item) => sum + item.buy_volume + item.sell_volume,
    0,
  )

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
              <span>arbitrage candidates</span>
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
              <span>market volume</span>
              <strong>{formatCompact(totalVolume)}</strong>
              <p>{summary ? `${formatNumber(summary.total_rows)} saved rows` : 'loading'}</p>
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
                <span>bazaar to npc</span>
              </div>

              {npcArbitrageItems.length > 0 ? (
                <div className="arbitrage-table">
                  <div className="arbitrage-row table-head">
                    <span>#</span>
                    <span>item</span>
                    <span>bazaar buy</span>
                    <span>npc sell</span>
                    <span>profit</span>
                    <span>volume</span>
                  </div>
                  {npcArbitrageItems.slice(0, 5).map((item, index) => (
                    <div className="arbitrage-row" key={item.item_id}>
                      <span>{index + 1}</span>
                      <span className="arbitrage-item-cell">
                        <b>{item.item_name}</b>
                        <small>{item.item_id}</small>
                      </span>
                      <span>{formatCompact(item.bazaar_buy_price)}</span>
                      <span>{formatCompact(item.npc_sell_price)}</span>
                      <span className="positive">{formatCompact(item.profit_per_item)}</span>
                      <span>{formatCompact(item.buy_volume + item.sell_volume)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="empty-state">
                  run the item metadata collector to calculate npc arbitrage.
                </p>
              )}
            </article>
          </div>

          <aside className="right-column">
            <article className="panel forecast-panel">
              <h2>forecast snapshot</h2>
              <div className="sparkline" aria-hidden="true">
                <span />
              </div>
              <p>prices with high liquidity and positive spreads are prioritized for review.</p>
              <div className="confidence-line">
                <span className="score-badge">{marketScore}</span>
                <strong>baseline confidence</strong>
              </div>
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
                  <small>volume filters are next for cleaner rankings</small>
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
