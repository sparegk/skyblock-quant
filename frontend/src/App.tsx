import './App.css'

const marketStats = [
  { label: 'tracked products', value: '1,933' },
  { label: 'latest snapshot', value: 'local sqlite' },
  { label: 'collector mode', value: 'scheduled' },
  { label: 'next feature', value: 'arbitrage' },
]

const topSignals = [
  {
    item: 'Tarantula Web',
    signal: 'watch',
    confidence: 'baseline',
    reason: 'high volume with a visible bid-ask spread',
  },
  {
    item: 'Corrupted Bait',
    signal: 'review',
    confidence: 'baseline',
    reason: 'large spread makes it useful for early risk checks',
  },
  {
    item: 'Sea Lumies',
    signal: 'watch',
    confidence: 'baseline',
    reason: 'active buy and sell volume from the latest snapshot',
  },
]

const buildSteps = [
  'connect frontend to a local backend api',
  'show latest bazaar snapshot rows',
  'add item search and price history',
  'build the first npc arbitrage table',
]

function App() {
  return (
    <main className="app-shell">
      <section className="dashboard-header">
        <div>
          <p className="eyebrow">skyblock quant</p>
          <h1>Market dashboard starter</h1>
          <p className="intro">
            A simple frontend for viewing Bazaar snapshots, market signals, and
            future arbitrage results.
          </p>
        </div>
        <div className="status-panel" aria-label="collector status">
          <span className="status-dot" />
          <div>
            <strong>collector ready</strong>
            <p>SQLite snapshots are being saved locally.</p>
          </div>
        </div>
      </section>

      <section className="stats-grid" aria-label="market stats">
        {marketStats.map((stat) => (
          <article className="stat-card" key={stat.label}>
            <span>{stat.label}</span>
            <strong>{stat.value}</strong>
          </article>
        ))}
      </section>

      <section className="content-grid">
        <div className="table-section">
          <div className="section-heading">
            <p className="eyebrow">sample rows</p>
            <h2>Early signal preview</h2>
          </div>
          <div className="signal-table" role="table" aria-label="signal preview">
            <div className="table-row table-head" role="row">
              <span>item</span>
              <span>signal</span>
              <span>confidence</span>
              <span>reason</span>
            </div>
            {topSignals.map((signal) => (
              <div className="table-row" role="row" key={signal.item}>
                <span>{signal.item}</span>
                <span className="signal-pill">{signal.signal}</span>
                <span>{signal.confidence}</span>
                <span>{signal.reason}</span>
              </div>
            ))}
          </div>
        </div>

        <aside className="next-panel">
          <div className="section-heading">
            <p className="eyebrow">next frontend tasks</p>
            <h2>Build order</h2>
          </div>
          <ol>
            {buildSteps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </aside>
      </section>
    </main>
  )
}

export default App
