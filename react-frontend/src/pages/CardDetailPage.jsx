import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { CARD_TIER } from '../data/cardTiers'
import { TIER_COLORS } from '../data/tierColors'

// ── Matchup group/sort helpers ────────────────────────────────────────────────

function wrChipClass(wr, gp) {
  if (gp === 0)  return 'wr-chip wr-none'
  if (wr >= 60)  return 'wr-chip wr-hot'
  if (wr >= 45)  return 'wr-chip wr-warm'
  return              'wr-chip wr-cold'
}

function mrChipClass(mr) {
  if (mr == null)       return 'wr-chip wr-none'
  if (mr >= 0.60)       return 'wr-chip wr-hot'
  if (mr >= 0.45)       return 'wr-chip wr-warm'
  return                     'wr-chip wr-cold'
}

function sortMatchups(rows, groupMode) {
  return [...rows].sort((a, b) => {
    if (groupMode === 'win_rate') {
      const av = a.win_rate ?? -1, bv = b.win_rate ?? -1
      if (bv !== av) return bv - av
      return b.games_played - a.games_played
    }
    if (groupMode === 'matchup_rating') {
      const av = a.matchup_rating ?? -1, bv = b.matchup_rating ?? -1
      if (bv !== av) return bv - av
      return b.games_played - a.games_played
    }
    if (groupMode === 'name') return a.card_2.localeCompare(b.card_2)
    if (groupMode === 'games_played') return b.games_played - a.games_played
    return 0
  })
}

function cardFallback(size = 34) {
  return `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='${size}' height='${size}'%3E%3Crect width='${size}' height='${size}' fill='%23111'/%3E%3C/svg%3E`
}

// ── Sub-components ────────────────────────────────────────────────────────────

function MatchupRow({ row }) {
  const fb = cardFallback(34)
  const gpDisplay = row.games_played
    ? row.games_played
    : <span style={{ opacity: .35 }}>0</span>
  const wDisplay = row.games_played
    ? (row.card_1_W || <span style={{ opacity: .5 }}>0</span>)
    : <span style={{ opacity: .35 }}>—</span>
  const lDisplay = row.games_played
    ? (row.card_1_L || <span style={{ opacity: .5 }}>0</span>)
    : <span style={{ opacity: .35 }}>—</span>
  const wrVal  = row.games_played && row.win_rate != null ? `${row.win_rate}%` : '—'
  const mrVal  = row.matchup_rating != null ? (row.matchup_rating * 100).toFixed(1) : '—'

  return (
    <tr>
      <td>
        <img
          className="card-img-sm"
          src={row.card_2_iconUrl || fb}
          alt={row.card_2}
          onError={e => { e.target.src = fb }}
        />
        {row.card_2}
      </td>
      <td className="gp-cell">{gpDisplay}</td>
      <td className="w-cell">{wDisplay}</td>
      <td className="l-cell">{lDisplay}</td>
      <td style={{ textAlign: 'center' }}>
        <span className={wrChipClass(row.win_rate, row.games_played)}>{wrVal}</span>
      </td>
      <td style={{ textAlign: 'center' }}>
        <span className={mrChipClass(row.matchup_rating)}>{mrVal}</span>
      </td>
    </tr>
  )
}

function GroupHeaderRow({ label, count, color }) {
  return (
    <tr className="group-header">
      <td colSpan={6} style={{ color }}>{label} ({count})</td>
    </tr>
  )
}

function MatchupTable({ matchups, groupMode, setGroupMode, showZero, setShowZero }) {
  const seen   = matchups.filter(r => r.games_played > 0)
  const unseen = matchups.filter(r => r.games_played === 0)

  const groupOptions = [
    { key: 'win_rate',       label: 'By Win Rate'   },
    { key: 'matchup_rating', label: 'By Rating'     },
    { key: 'name',           label: 'Alphabetical'  },
    { key: 'games_played',   label: 'By Games'      },
  ]

  let rows = null

  if (groupMode === 'win_rate' && seen.length > 0) {
    const favourable = sortMatchups(seen.filter(r => r.win_rate >= 55), groupMode)
    const even       = sortMatchups(seen.filter(r => r.win_rate >= 45 && r.win_rate < 55), groupMode)
    const unfav      = sortMatchups(seen.filter(r => r.win_rate < 45), groupMode)
    rows = (
      <>
        {favourable.length > 0 && (
          <>
            <GroupHeaderRow label="✅ Favourable" count={favourable.length} color="var(--green)" />
            {favourable.map((r, i) => <MatchupRow key={i} row={r} />)}
          </>
        )}
        {even.length > 0 && (
          <>
            <GroupHeaderRow label="⚖️ Even" count={even.length} color="var(--gold)" />
            {even.map((r, i) => <MatchupRow key={i} row={r} />)}
          </>
        )}
        {unfav.length > 0 && (
          <>
            <GroupHeaderRow label="❌ Unfavourable" count={unfav.length} color="var(--red)" />
            {unfav.map((r, i) => <MatchupRow key={i} row={r} />)}
          </>
        )}
        {seen.length === 0 && (
          <tr><td colSpan={6} className="empty">No matchup data yet.</td></tr>
        )}
      </>
    )
  } else {
    const sorted = sortMatchups(seen, groupMode)
    rows = sorted.length > 0
      ? sorted.map((r, i) => <MatchupRow key={i} row={r} />)
      : <tr><td colSpan={6} className="empty">No matchup data yet.</td></tr>
  }

  return (
    <>
      <div className="mu-controls">
        <div className="mu-seg" id="mu-group-seg">
          {groupOptions.map(opt => (
            <button
              key={opt.key}
              className={groupMode === opt.key ? 'active' : ''}
              onClick={() => setGroupMode(opt.key)}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <label className="show-zero-label">
          <input
            type="checkbox"
            checked={showZero}
            onChange={e => setShowZero(e.target.checked)}
          />
          Show unseen matchups
        </label>
      </div>

      <div className="matchup-wrap fade-in delay-4">
        <table id="matchup-table">
          <thead>
            <tr>
              <th>Opponent</th>
              <th style={{ textAlign: 'center' }}>GP</th>
              <th style={{ textAlign: 'center' }}>W</th>
              <th style={{ textAlign: 'center' }}>L</th>
              <th style={{ textAlign: 'center' }}>Win %</th>
              <th style={{ textAlign: 'center' }}>Rating</th>
            </tr>
          </thead>
          <tbody id="matchup-tbody">
            {rows}
            {showZero && unseen.length > 0 && (
              <>
                <GroupHeaderRow
                  label="🔲 Not Yet Seen"
                  count={unseen.length}
                  color="var(--text-muted)"
                />
                {sortMatchups(unseen, groupMode === 'win_rate' ? 'name' : groupMode).map((r, i) => (
                  <MatchupRow key={i} row={r} />
                ))}
              </>
            )}
          </tbody>
        </table>
      </div>
    </>
  )
}

// ── Main CardDetailPage ───────────────────────────────────────────────────────
export default function CardDetailPage() {
  const { cardName } = useParams()
  const decodedName  = decodeURIComponent(cardName || '')

  const [data,      setData]      = useState(null)
  const [loading,   setLoading]   = useState(true)
  const [error,     setError]     = useState(null)
  const [groupMode, setGroupMode] = useState('win_rate')
  const [showZero,  setShowZero]  = useState(false)

  // ── Fetch card detail ───────────────────────────────────────────────────────
  useEffect(() => {
    if (!decodedName) { setLoading(false); return }
    setLoading(true)
    fetch(`/api/card_detail/${encodeURIComponent(decodedName)}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [decodedName])

  // ── Tier theme (CSS variables) ──────────────────────────────────────────────
  useEffect(() => {
    if (!data) return
    const tier = CARD_TIER[data.overall.name] || 'F'
    const tc   = TIER_COLORS[tier] || TIER_COLORS['F']
    document.documentElement.style.setProperty('--tier-color', tc.color)
    document.documentElement.style.setProperty('--tier-glow', tc.glow)
    document.title = `${data.overall.name} — CR Draft`
    return () => {
      document.documentElement.style.setProperty('--tier-color', 'var(--gold)')
      document.documentElement.style.setProperty('--tier-glow', 'rgba(245,200,66,.35)')
    }
  }, [data])

  // ── Animate stat bars ───────────────────────────────────────────────────────
  useEffect(() => {
    if (!data) return
    requestAnimationFrame(() => {
      document.querySelectorAll('.stat-bar-fill[data-pct]').forEach(el => {
        el.style.width = el.dataset.pct + '%'
      })
    })
  }, [data])

  // ── Loading / error ─────────────────────────────────────────────────────────
  if (loading) {
    return (
      <>
        <header>
          <div className="header-title">⚔️ Card Profile</div>
          <Link to="/stats" className="back-btn">← Card Stats</Link>
        </header>
        <main>
          <div id="page-loading">
            <div className="spinner"></div>
            <div className="loading-text">Loading card data…</div>
          </div>
        </main>
      </>
    )
  }

  if (error || !data) {
    return (
      <>
        <header>
          <div className="header-title">⚔️ Card Profile</div>
          <Link to="/stats" className="back-btn">← Card Stats</Link>
        </header>
        <main>
          <div id="page-loading">
            <div className="empty">{error ? `Failed to load data: ${error}` : 'No card specified.'}</div>
          </div>
        </main>
      </>
    )
  }

  const o   = data.overall
  const tier = CARD_TIER[o.name] || 'F'

  // Stat card value/color helpers
  const wpClass    = o.win_rate >= 55 ? 'sc-green' : o.win_rate <= 40 ? 'sc-red' : 'sc-gold'
  const ratingVal  = o.overall_rating != null ? (o.overall_rating * 100).toFixed(1) : '—'
  const ratingPct  = o.overall_rating != null ? o.overall_rating * 100 : null
  const ratingClass = ratingPct == null
    ? 'sc-gold'
    : ratingPct >= 55 ? 'sc-green'
    : ratingPct <= 40 ? 'sc-red'
    : 'sc-gold'

  const playPct = Math.min(o.play_rate || 0, 100)
  const winPct  = o.win_rate   || 0
  const banPct  = Math.min((o.ban_rate || 0) * 2, 100)

  const seen = (data.matchups || []).filter(r => r.games_played > 0)

  const fb200 = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Crect width='200' height='200' fill='%23111'/%3E%3Ctext x='100' y='110' text-anchor='middle' fill='%23444' font-size='64'%3E%3F%3C/text%3E%3C/svg%3E`

  return (
    <>
      <header>
        <div className="header-title" id="header-title">⚔️ {o.name}</div>
        <Link to="/stats" className="back-btn">← Card Stats</Link>
      </header>

      <main>
        <div id="page-content">

          {/* ── HERO ── */}
          <div className="hero fade-in">
            {/* Portrait */}
            <div className="card-portrait-wrap">
              <div className="card-portrait-ring" id="portrait-ring" />
              <img
                id="card-img"
                className="card-portrait"
                src={o.iconUrl || fb200}
                alt={o.name}
                onError={e => { e.target.src = fb200 }}
              />
            </div>

            {/* Hero right */}
            <div className="hero-right">
              <div className="card-name-badge" id="card-name-badge">{o.name}</div>
              <div className="card-meta-row" id="card-meta-row">
                <span className="tier-badge">{tier}</span>
                <span className="rarity-badge">{o.rarity || '—'}</span>
                <span className="elixir-badge">
                  <svg width="10" height="12" viewBox="0 0 10 12" fill="none">
                    <path d="M5 0L9 5H6V12H4V5H1L5 0Z" fill="#ddb8ff" />
                  </svg>
                  {o.elixir || '?'}
                </span>
              </div>
              {/* Stat cards */}
              <div className="stat-cards-grid fade-in delay-1" id="stat-cards-grid">
                <div className="stat-card">
                  <div className="sc-value sc-gold">{o.total_games}</div>
                  <div className="sc-label">Total Games</div>
                </div>
                <div className="stat-card">
                  <div className="sc-value sc-blue">{o.games_played}</div>
                  <div className="sc-label">Appearances</div>
                </div>
                <div className="stat-card">
                  <div className="sc-value sc-green">{o.wins}</div>
                  <div className="sc-label">Wins</div>
                </div>
                <div className="stat-card">
                  <div className="sc-value sc-red">{o.losses}</div>
                  <div className="sc-label">Losses</div>
                </div>
                <div className="stat-card">
                  <div className={`sc-value ${ratingClass}`}>{ratingVal}</div>
                  <div className="sc-label">Overall Rating</div>
                </div>
              </div>

              {/* Stat bars */}
              <div className="fade-in delay-2">
                <div className="stat-bars" id="stat-bars">
                  <div className="stat-bar-row">
                    <div className="stat-bar-label">Play Rate</div>
                    <div className="stat-bar-track">
                      <div
                        className="stat-bar-fill fill-play"
                        data-pct={playPct}
                        style={{ width: 0 }}
                      />
                    </div>
                    <div className="stat-bar-pct">
                      {o.games_played ? `${o.play_rate}%` : '—'}
                    </div>
                  </div>
                  <div className="stat-bar-row">
                    <div className="stat-bar-label">Win Rate</div>
                    <div className="stat-bar-track">
                      <div
                        className="stat-bar-fill fill-win"
                        data-pct={winPct}
                        style={{ width: 0 }}
                      />
                    </div>
                    <div className="stat-bar-pct">
                      {o.games_played ? `${o.win_rate}%` : '—'}
                    </div>
                  </div>
                  <div className="stat-bar-row">
                    <div className="stat-bar-label">Ban Rate</div>
                    <div className="stat-bar-track">
                      <div
                        className="stat-bar-fill fill-ban"
                        data-pct={banPct}
                        style={{ width: 0 }}
                      />
                    </div>
                    <div className="stat-bar-pct">
                      {o.total_games ? `${o.ban_rate}%` : '—'}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ── MATCHUP TABLE ── */}
          <div className="fade-in delay-3">
            <div className="section-title">
              ⚔️ Matchup Record
              <span className="section-badge" id="matchup-badge">
                {seen.length} seen / 49 total
              </span>
            </div>
            <MatchupTable
              matchups={data.matchups || []}
              groupMode={groupMode}
              setGroupMode={setGroupMode}
              showZero={showZero}
              setShowZero={setShowZero}
            />
          </div>

        </div>
      </main>
    </>
  )
}
