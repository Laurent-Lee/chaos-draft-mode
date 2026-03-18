import { useState, useEffect, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { CARD_TIER, TIER_ORDER, TIER_ICONS } from '../data/cardTiers'
import { CARD_TYPE, TYPE_ORDER, TYPE_ICONS } from '../data/cardTypes'

const MODES = ['All', 'Normal Draft', 'AI Draft']

function TierBadge({ tier }) {
  if (!tier) return null
  const cls = tier === 'S+' ? 'tier-Sp' : `tier-${tier}`
  return <span className={`tier-badge ${cls}`}>{TIER_ICONS[tier] || ''} {tier}</span>
}

function BarCell({ value, max, fillClass }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div className="bar-wrap">
      <div className="bar-track">
        <div className={`bar-fill ${fillClass}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="bar-pct">{value}%</span>
    </div>
  )
}

export default function CardStatsPage() {
  const navigate = useNavigate()
  const [cards, setCards] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [mode, setMode] = useState('All')
  const [tierFilter, setTierFilter] = useState('All')
  const [typeFilter, setTypeFilter] = useState('All')
  const [search, setSearch] = useState('')
  const [sortCol, setSortCol] = useState('play_rate')
  const [sortAsc, setSortAsc] = useState(false)

  useEffect(() => {
    const params = new URLSearchParams()
    if (mode !== 'All') params.set('game_mode', mode)
    fetch(getApiUrl(`/api/card_stats?${params}`))
      .then(r => r.json())
      .then(data => { setCards(data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [mode])

  const tiers = ['All', ...Object.keys(TIER_ORDER)]
  const types = ['All', ...Object.keys(TYPE_ORDER).sort((a, b) => TYPE_ORDER[a] - TYPE_ORDER[b])]

  const filtered = useMemo(() => {
    let list = cards.filter(c => {
      if (tierFilter !== 'All' && CARD_TIER[c.name] !== tierFilter) return false
      if (typeFilter !== 'All' && CARD_TYPE[c.name] !== typeFilter) return false
      if (search && !c.name.toLowerCase().includes(search.toLowerCase())) return false
      return true
    })
    list = [...list].sort((a, b) => {
      let av = a[sortCol] ?? 0
      let bv = b[sortCol] ?? 0
      if (typeof av === 'string') av = av.toLowerCase()
      if (typeof bv === 'string') bv = bv.toLowerCase()
      if (av < bv) return sortAsc ? -1 : 1
      if (av > bv) return sortAsc ? 1 : -1
      return 0
    })
    return list
  }, [cards, tierFilter, typeFilter, search, sortCol, sortAsc])

  const maxPlay = Math.max(...filtered.map(c => c.play_rate ?? 0), 1)
  const maxWin  = Math.max(...filtered.map(c => c.win_rate ?? 0), 1)
  const maxBan  = Math.max(...filtered.map(c => c.ban_rate ?? 0), 1)

  const totalGames = cards[0]?.total_games ?? 0

  function handleSort(col) {
    if (sortCol === col) setSortAsc(a => !a)
    else { setSortCol(col); setSortAsc(false) }
  }

  function SortTh({ col, children, align = 'right' }) {
    const active = sortCol === col
    return (
      <th
        onClick={() => handleSort(col)}
        style={{ textAlign: align, cursor: 'pointer' }}
        className={active ? 'text-gold' : ''}
      >
        {children}{active ? (sortAsc ? ' ▲' : ' ▼') : ''}
      </th>
    )
  }

  return (
    <div>
      <header>
        <span className="header-title">Card Stats</span>
        <nav style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <Link to="/" style={{ color: 'var(--text-muted)', fontSize: '.85rem', textDecoration: 'none' }}>Home</Link>
          <Link to="/player_stats" style={{ color: 'var(--text-muted)', fontSize: '.85rem', textDecoration: 'none' }}>Players</Link>
        </nav>
      </header>

      <main>
        {/* Summary */}
        {!loading && !error && (
          <div className="summary">
            <div className="stat-pill">Total Games <span>{totalGames}</span></div>
            <div className="stat-pill">Cards Shown <span>{filtered.length}</span></div>
          </div>
        )}

        {/* Controls */}
        <div className="controls">
          <span className="ctrl-label">Mode</span>
          <div className="seg">
            {MODES.map(m => (
              <button key={m} className={mode === m ? 'active' : ''} onClick={() => setMode(m)}>{m}</button>
            ))}
          </div>

          <span className="ctrl-label" style={{ marginLeft: '.5rem' }}>Tier</span>
          <div className="seg">
            {tiers.map(t => (
              <button key={t} className={tierFilter === t ? 'active' : ''} onClick={() => setTierFilter(t)}>
                {t === 'All' ? 'All' : `${TIER_ICONS[t] || ''} ${t}`}
              </button>
            ))}
          </div>

          <span className="ctrl-label" style={{ marginLeft: '.5rem' }}>Type</span>
          <div className="seg">
            {types.map(t => (
              <button key={t} className={typeFilter === t ? 'active' : ''} onClick={() => setTypeFilter(t)}>
                {t === 'All' ? 'All' : `${TYPE_ICONS[t] || ''} ${t}`}
              </button>
            ))}
          </div>

          <input
            id="search"
            placeholder="Search cards…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ marginLeft: 'auto' }}
          />

          <a className="export-btn" href={getApiUrl('/api/export_card_data')} download>
            ⬇ Export card_data.csv
          </a>
        </div>

        {/* Table */}
        {loading && <div id="loading">Loading card stats…</div>}
        {error && <div className="no-data">Error: {error}</div>}
        {!loading && !error && filtered.length === 0 && (
          <div className="no-data">No cards match your filters.</div>
        )}

        {!loading && !error && filtered.length > 0 && (
          <div className="tbl-wrap">
            <table>
              <thead>
                <tr>
                  <SortTh col="name" align="left">Card</SortTh>
                  <SortTh col="elixir">Elixir</SortTh>
                  <SortTh col="overall_rating">Rating</SortTh>
                  <SortTh col="play_rate">Play %</SortTh>
                  <SortTh col="win_rate">Win %</SortTh>
                  <SortTh col="ban_rate">Ban %</SortTh>
                  <SortTh col="games_played">Games</SortTh>
                  <SortTh col="wins">Wins</SortTh>
                  <SortTh col="losses">Losses</SortTh>
                  <SortTh col="player_bans">Bans</SortTh>
                </tr>
              </thead>
              <tbody>
                {filtered.map(card => {
                  const tier = CARD_TIER[card.name]
                  const type = CARD_TYPE[card.name]
                  const rarityClass = card.rarity ? `r-${card.rarity}` : ''
                  return (
                    <tr key={card.name} onClick={() => navigate(`/card/${encodeURIComponent(card.name)}`)}>
                      <td>
                        <div className="card-cell">
                          {card.iconUrl
                            ? <img src={card.iconUrl} alt={card.name} className="card-icon" />
                            : <div style={{ width: 32, height: 32, borderRadius: '.25rem', background: 'var(--surface2)', flexShrink: 0 }} />
                          }
                          <div>
                            <div className={`font-semibold ${rarityClass}`}>{card.name}</div>
                            <div style={{ display: 'flex', gap: '.3rem', marginTop: '.15rem', flexWrap: 'wrap' }}>
                              <TierBadge tier={tier} />
                              {type && (
                                <span style={{ fontSize: '.65rem', color: 'var(--text-muted)' }}>
                                  {TYPE_ICONS[type]} {type}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <span className="elixir-pip">{card.elixir}</span>
                      </td>
                      <td style={{
                        color: card.overall_rating == null ? undefined
                          : card.overall_rating >= 0.55 ? 'var(--win)'
                          : card.overall_rating <= 0.40 ? 'var(--loss)'
                          : 'var(--gold)',
                        fontWeight: card.overall_rating != null ? 600 : undefined,
                      }}>
                        {card.overall_rating != null ? (card.overall_rating * 100).toFixed(1) : <span className="zero">—</span>}
                      </td>
                      <td>
                        <BarCell value={card.play_rate ?? 0} max={maxPlay} fillClass="fill-play" />
                      </td>
                      <td>
                        <BarCell value={card.win_rate ?? 0} max={maxWin} fillClass="fill-win" />
                      </td>
                      <td>
                        <BarCell value={card.ban_rate ?? 0} max={maxBan} fillClass="fill-ban" />
                      </td>
                      <td className={!card.games_played ? 'zero' : ''}>{card.games_played ?? 0}</td>
                      <td className={!card.wins ? 'zero' : ''} style={{ color: card.wins ? 'var(--win)' : undefined }}>{card.wins ?? 0}</td>
                      <td className={!card.losses ? 'zero' : ''} style={{ color: card.losses ? 'var(--loss)' : undefined }}>{card.losses ?? 0}</td>
                      <td className={!card.player_bans ? 'zero' : ''} style={{ color: card.player_bans ? 'var(--ban)' : undefined }}>{card.player_bans ?? 0}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  )
}
