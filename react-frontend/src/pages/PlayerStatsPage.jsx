import { useState, useEffect, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PLAYERS } from '../data/players'
import { CARD_TIER, TIER_ICONS } from '../data/cardTiers'
import { CARD_TYPE, TYPE_ICONS } from '../data/cardTypes'

const MODES = ['All', 'Normal Draft', 'AI Draft']

/* ── small helpers ── */
function WrBar({ pct }) {
  const color = pct >= 55 ? 'var(--win)' : pct >= 45 ? 'var(--gold)' : 'var(--loss)'
  return (
    <div className="wr-bar-wrap">
      <div className="wr-bar">
        <div className="wr-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="wr-pct" style={{ color }}>{pct}%</span>
    </div>
  )
}

function ModeBadge({ mode }) {
  if (!mode) return null
  const isAI = mode === 'AI Draft'
  return <span className={`mode-badge ${isAI ? 'mode-badge-ai' : 'mode-badge-normal'}`}>{mode}</span>
}

function MhCard({ match, playerName }) {
  const won = match.winner === playerName
  const opponentName = won ? match.loser : match.winner

  // Determine which picks belong to this player
  const myPicks = match['1st_pick'] === playerName ? match.first_picks : match.second_picks
  const oppPicks = match['1st_pick'] === playerName ? match.second_picks : match.first_picks

  const bans = (match.bans || []).filter(b => b.by === playerName || b.by === 'player' || (b.banned_by === playerName))

  return (
    <div className="mh-game">
      <div className="mh-header">
        <span style={{ color: won ? 'var(--win)' : 'var(--loss)', fontWeight: 700 }}>
          {won ? '✓ WIN' : '✗ LOSS'}
        </span>
        <span style={{ display: 'flex', gap: '.5rem', alignItems: 'center' }}>
          <ModeBadge mode={match.game_mode} />
          {match.timestamp && (
            <span>{new Date(match.timestamp).toLocaleDateString()}</span>
          )}
        </span>
        <span>vs {opponentName}</span>
      </div>
      <div className="mh-body">
        <div className={`mh-player-col ${won ? 'mh-won' : 'mh-lost'}`}>
          <div className="mh-player-name" style={{ color: won ? 'var(--win)' : 'var(--loss)' }}>
            {playerName}
          </div>
          <div className="mh-section-label">Deck</div>
          <div className="mh-card-row">
            {(myPicks || []).map(card => (
              card.iconUrl
                ? <img key={card.name} src={card.iconUrl} alt={card.name} title={card.name} className="mh-card-img" />
                : <div key={card.name} style={{ width: 36, height: 36, borderRadius: '.25rem', background: 'var(--surface2)' }} />
            ))}
          </div>
        </div>
        <div className="mh-divider" />
        <div className={`mh-player-col ${!won ? 'mh-won' : 'mh-lost'}`}>
          <div className="mh-player-name" style={{ color: !won ? 'var(--win)' : 'var(--loss)' }}>
            {opponentName}
          </div>
          <div className="mh-section-label">Deck</div>
          <div className="mh-card-row">
            {(oppPicks || []).map(card => (
              card.iconUrl
                ? <img key={card.name} src={card.iconUrl} alt={card.name} title={card.name} className="mh-card-img" />
                : <div key={card.name} style={{ width: 36, height: 36, borderRadius: '.25rem', background: 'var(--surface2)' }} />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

/* ── card stats tab for a player ── */
function PlayerCardStats({ playerName, mode }) {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [overallRatings, setOverallRatings] = useState({})
  const [loading, setLoading] = useState(true)
  const [sortCol, setSortCol] = useState('games_played')
  const [sortAsc, setSortAsc] = useState(false)

  useEffect(() => {
    setLoading(true)
    const params = new URLSearchParams()
    if (mode !== 'All') params.set('game_mode', mode)
    Promise.all([
      fetch(`/api/player_stats/${encodeURIComponent(playerName)}?${params}`).then(r => r.json()),
      fetch('/api/card_stats').then(r => r.json()),
    ]).then(([playerData, cardStats]) => {
      setData(playerData)
      const ratings = {}
      if (Array.isArray(cardStats)) {
        cardStats.forEach(c => { if (c.overall_rating != null) ratings[c.name] = c.overall_rating })
      }
      setOverallRatings(ratings)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [playerName, mode])

  const rows = useMemo(() => {
    if (!data?.cards) return []
    const list = data.cards.map(s => ({
      name: s.name,
      games_played: s.games_played ?? 0,
      wins: s.wins ?? 0,
      losses: s.losses ?? 0,
      win_rate: s.win_rate ?? 0,
      pick_rate: s.play_rate ?? 0,
      ban_rate: s.ban_rate ?? 0,
      player_bans: s.player_bans ?? 0,
      overall_rating: overallRatings[s.name] ?? null,
    }))
    return [...list].sort((a, b) => {
      const av = a[sortCol] ?? 0
      const bv = b[sortCol] ?? 0
      return sortAsc ? av - bv : bv - av
    })
  }, [data, sortCol, sortAsc])

  function handleSort(col) {
    if (sortCol === col) setSortAsc(a => !a)
    else { setSortCol(col); setSortAsc(false) }
  }

  function Th({ col, children }) {
    const active = sortCol === col
    return (
      <th onClick={() => handleSort(col)} style={{ cursor: 'pointer', color: active ? 'var(--gold)' : undefined }}>
        {children}{active ? (sortAsc ? ' ▲' : ' ▼') : ''}
      </th>
    )
  }

  if (loading) return <div className="loading">Loading…</div>
  if (!data || rows.length === 0) return <div className="empty">No card data yet.</div>

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="card-table">
        <thead>
          <tr>
            <Th col="name">Card</Th>
            <Th col="overall_rating">Rating</Th>
            <Th col="games_played">Games</Th>
            <Th col="wins">Wins</Th>
            <Th col="losses">Losses</Th>
            <Th col="win_rate">Win %</Th>
            <Th col="pick_rate">Pick %</Th>
            <Th col="player_bans">Bans</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map(row => {
            const tier = CARD_TIER[row.name]
            const type = CARD_TYPE[row.name]
            const ratingDisplay = row.overall_rating != null ? (row.overall_rating * 100).toFixed(1) : '—'
            const ratingColor = row.overall_rating == null ? undefined
              : row.overall_rating >= 0.55 ? 'var(--win)'
              : row.overall_rating <= 0.40 ? 'var(--loss)'
              : 'var(--gold)'
            return (
              <tr key={row.name} onClick={() => navigate(`/card/${encodeURIComponent(row.name)}`)} style={{ cursor: 'pointer' }}>
                <td>
                  <div className="card-name-cell">
                    <span style={{ marginRight: '.5rem' }}>
                      {tier && <span style={{ fontSize: '.7rem' }}>{TIER_ICONS[tier]}</span>}
                    </span>
                    {row.name}
                    {type && <span style={{ marginLeft: '.4rem', fontSize: '.65rem', color: 'var(--text-muted)' }}>{TYPE_ICONS[type]}</span>}
                  </div>
                </td>
                <td style={{ color: ratingColor }} className={row.overall_rating == null ? 'zero' : ''}>{ratingDisplay}</td>
                <td className={!row.games_played ? 'zero' : ''}>{row.games_played}</td>
                <td className={!row.wins ? 'zero' : ''} style={{ color: row.wins ? 'var(--win)' : undefined }}>{row.wins}</td>
                <td className={!row.losses ? 'zero' : ''} style={{ color: row.losses ? 'var(--loss)' : undefined }}>{row.losses}</td>
                <td className={!row.games_played ? 'zero' : ''} style={{ color: row.games_played ? (row.win_rate >= 50 ? 'var(--win)' : 'var(--loss)') : undefined }}>
                  {row.games_played ? `${row.win_rate}%` : '—'}
                </td>
                <td className={!row.games_played ? 'zero' : ''}>{row.games_played ? `${row.pick_rate}%` : '—'}</td>
                <td className={!row.player_bans ? 'zero' : ''} style={{ color: row.player_bans ? 'var(--ban)' : undefined }}>{row.player_bans}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/* ── recent matches tab for a player ── */
function PlayerMatchHistory({ playerName, mode }) {
  const [matches, setMatches] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showAll, setShowAll] = useState(false)

  useEffect(() => {
    setLoading(true)
    const params = new URLSearchParams()
    if (mode !== 'All') params.set('game_mode', mode)
    fetch(`/api/match_history/${encodeURIComponent(playerName)}?${params}`)
      .then(r => r.json())
      .then(d => { setMatches(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [playerName, mode])

  if (loading) return <div className="loading">Loading…</div>
  if (!matches || matches.length === 0) return <div className="empty">No matches yet.</div>

  const displayed = showAll ? matches : matches.slice(0, 10)

  return (
    <div>
      {displayed.map((match, i) => (
        <MhCard key={i} match={match} playerName={playerName} />
      ))}
      {!showAll && matches.length > 10 && (
        <div className="mh-show-more" onClick={() => setShowAll(true)}>
          Show {matches.length - 10} more matches ▼
        </div>
      )}
    </div>
  )
}

/* ── player detail screen ── */
function PlayerDetail({ playerName, mode, onBack }) {
  const [data, setData] = useState(null)
  const [elo, setElo] = useState(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('stats')

  useEffect(() => {
    setLoading(true)
    const params = new URLSearchParams()
    if (mode !== 'All') params.set('game_mode', mode)
    Promise.all([
      fetch(`/api/player_stats/${encodeURIComponent(playerName)}?${params}`).then(r => r.json()),
      fetch('/api/elo').then(r => r.json()),
    ]).then(([pdata, eloData]) => {
      setData(pdata)
      setElo(eloData[playerName] ?? 1000)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [playerName, mode])

  if (loading) return <div className="loading">Loading player data…</div>

  const s = data ?? {}
  const wins = s.wins ?? 0
  const losses = s.losses ?? 0
  const total = wins + losses
  const winPct = total > 0 ? Math.round((wins / total) * 100) : 0

  return (
    <div>
      <div className="detail-header">
        <button className="btn-back" onClick={onBack}>← All Players</button>
      </div>

      <div className="detail-name" style={{ marginBottom: '1.25rem' }}>{playerName}</div>

      {/* Stat cards */}
      <div className="stat-cards">
        <div className="stat-card">
          <div className="value" style={{ color: 'var(--gold)' }}>{elo ?? 1000}</div>
          <div className="label">ELO</div>
        </div>
        <div className="stat-card">
          <div className="value" style={{ color: 'var(--win)' }}>{wins}</div>
          <div className="label">Wins</div>
        </div>
        <div className="stat-card">
          <div className="value" style={{ color: 'var(--loss)' }}>{losses}</div>
          <div className="label">Losses</div>
        </div>
        <div className="stat-card">
          <div className="value" style={{ color: winPct >= 50 ? 'var(--win)' : 'var(--loss)' }}>
            {total > 0 ? `${winPct}%` : '—'}
          </div>
          <div className="label">Win Rate</div>
        </div>
        <div className="stat-card">
          <div className="value">{total}</div>
          <div className="label">Games</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        <button className={`tab-btn ${tab === 'stats' ? 'active' : ''}`} onClick={() => setTab('stats')}>
          Card Stats
        </button>
        <button className={`tab-btn ${tab === 'history' ? 'active' : ''}`} onClick={() => setTab('history')}>
          Recent Matches
        </button>
      </div>

      <div className={`tab-panel ${tab === 'stats' ? 'active' : ''}`}>
        <PlayerCardStats playerName={playerName} mode={mode} />
      </div>
      <div className={`tab-panel ${tab === 'history' ? 'active' : ''}`}>
        <PlayerMatchHistory playerName={playerName} mode={mode} />
      </div>
    </div>
  )
}

/* ── leaderboard ── */
function Leaderboard({ mode, onSelectPlayer }) {
  const [playerStats, setPlayerStats] = useState(null)
  const [eloData, setEloData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    const params = new URLSearchParams()
    if (mode !== 'All') params.set('mode', mode)
    Promise.all([
      fetch(`/api/player_stats?${params}`).then(r => r.json()),
      fetch('/api/elo').then(r => r.json()),
    ]).then(([ps, elo]) => {
      setPlayerStats(ps)
      setEloData(elo)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [mode])

  if (loading) return <div className="loading">Loading leaderboard…</div>
  if (!playerStats) return <div className="empty">No data yet.</div>

  const players = PLAYERS.map(name => {
    const s = playerStats[name] ?? { wins: 0, losses: 0 }
    const wins = s.wins ?? 0
    const losses = s.losses ?? 0
    const total = wins + losses
    const winPct = total > 0 ? Math.round((wins / total) * 100) : 0
    return { name, wins, losses, total, winPct, elo: eloData?.[name] ?? 1000 }
  }).sort((a, b) => b.elo - a.elo)

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="leaderboard-table">
        <thead>
          <tr>
            <th className="rank-cell">#</th>
            <th>Player</th>
            <th>ELO</th>
            <th>W</th>
            <th>L</th>
            <th>Win Rate</th>
            <th>Games</th>
          </tr>
        </thead>
        <tbody>
          {players.map((p, i) => (
            <tr key={p.name} onClick={() => onSelectPlayer(p.name)}>
              <td className="rank-cell">{i + 1}</td>
              <td className="player-name-cell">{p.name}</td>
              <td className="elo-cell">{p.elo}</td>
              <td className="win-cell">{p.wins}</td>
              <td className="loss-cell">{p.losses}</td>
              <td className="winpct-cell">
                {p.total > 0 ? <WrBar pct={p.winPct} /> : <span style={{ color: 'var(--text-muted)' }}>—</span>}
              </td>
              <td className="games-cell">{p.total}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ── main page component ── */
export default function PlayerStatsPage() {
  const [mode, setMode] = useState('All')
  const [selectedPlayer, setSelectedPlayer] = useState(null)

  return (
    <div>
      <header>
        <span className="header-title">Player Stats</span>
        <nav style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <Link to="/" style={{ color: 'var(--text-muted)', fontSize: '.85rem', textDecoration: 'none' }}>Draft</Link>
          <Link to="/stats" style={{ color: 'var(--text-muted)', fontSize: '.85rem', textDecoration: 'none' }}>Card Stats</Link>
          <Link to="/dashboard" style={{ color: 'var(--text-muted)', fontSize: '.85rem', textDecoration: 'none' }}>Dashboard</Link>
        </nav>
      </header>

      <main>
        {/* Mode filter */}
        <div className="mode-filter">
          <span className="mode-label">Mode</span>
          <div className="seg">
            {MODES.map(m => (
              <button key={m} className={mode === m ? 'active' : ''} onClick={() => setMode(m)}>{m}</button>
            ))}
          </div>
        </div>

        {selectedPlayer
          ? (
            <PlayerDetail
              playerName={selectedPlayer}
              mode={mode}
              onBack={() => setSelectedPlayer(null)}
            />
          )
          : (
            <>
              <div className="section-title" style={{ marginBottom: '1rem' }}>Leaderboard</div>
              <Leaderboard mode={mode} onSelectPlayer={setSelectedPlayer} />
            </>
          )
        }
      </main>
    </div>
  )
}
