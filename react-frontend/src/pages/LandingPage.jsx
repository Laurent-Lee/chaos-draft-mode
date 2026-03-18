import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PLAYERS } from '../data/players'
import { getApiUrl } from '../config'

// ── API helper ────────────────────────────────────────────────────────────────
async function apiCall(path, method = 'GET', body = null) {
  const r = await fetch(getApiUrl(path), {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : null,
  })
  return r.json()
}

// ── Fetch hook ────────────────────────────────────────────────────────────────
function useAPI(url) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(getApiUrl(url))
      .then(r => r.json())
      .then(setData)
      .finally(() => setLoading(false))
  }, [url])

  return { data, loading }
}

// ── Small helpers ─────────────────────────────────────────────────────────────
function ElixirPip({ cost }) {
  return <span className="elixir-pip">{cost}</span>
}

function CardIcon({ card }) {
  if (card.iconUrl) {
    return <img src={card.iconUrl} alt={card.name} title={card.name} className="card-icon" />
  }
  return <div style={{ width: 32, height: 32, borderRadius: '.25rem', background: 'var(--surface2)', flexShrink: 0 }} />
}

function StatCard({ label, value, sub }) {
  return (
    <div className="stat-card">
      <div className="value" style={{ color: 'var(--gold)' }}>{value}</div>
      <div className="label">{label}</div>
      {sub && <div style={{ fontSize: '.7rem', color: 'var(--text-muted)', marginTop: '.2rem' }}>{sub}</div>}
    </div>
  )
}

function PanelHeader({ children }) {
  return (
    <div style={{
      padding: '.45rem .9rem',
      background: 'var(--surface2)',
      borderBottom: '1px solid var(--border)',
      fontSize: '.72rem',
      fontWeight: 700,
      letterSpacing: '.1em',
      textTransform: 'uppercase',
      color: 'var(--text-muted)',
    }}>
      {children}
    </div>
  )
}

function Panel({ children }) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '.75rem',
      overflow: 'hidden',
    }}>
      {children}
    </div>
  )
}

function EmptyState({ children }) {
  return <div className="empty">{children}</div>
}

function ModeBadge({ mode }) {
  if (!mode) return null
  const isAI = mode === 'AI Draft'
  return <span className={`mode-badge ${isAI ? 'mode-badge-ai' : 'mode-badge-normal'}`}>{mode}</span>
}

function CardImg({ card, size = 36, dimmed = false }) {
  if (card.iconUrl) {
    return (
      <img
        src={card.iconUrl} alt={card.name} title={card.name}
        style={{
          width: size, height: size, borderRadius: '.3rem', objectFit: 'cover', flexShrink: 0,
          opacity: dimmed ? .55 : 1,
          filter: dimmed ? 'grayscale(.4)' : 'none',
          border: '1px solid rgba(255,255,255,.08)',
        }}
      />
    )
  }
  return <div style={{ width: size, height: size, borderRadius: '.3rem', background: 'var(--surface2)', flexShrink: 0 }} />
}

function MatchCard({ match }) {
  const isWinner1st = match['1st_pick'] === match.winner
  const winnerPicks = isWinner1st ? match.first_picks  : match.second_picks
  const loserPicks  = isWinner1st ? match.second_picks : match.first_picks
  const winnerBans  = isWinner1st ? match.first_bans   : match.second_bans
  const loserBans   = isWinner1st ? match.second_bans  : match.first_bans
  const randomBans  = match.random_bans || []

  return (
    <div className="mh-game">
      {/* Header */}
      <div className="mh-header">
        <span style={{ display: 'flex', alignItems: 'center', gap: '.4rem', fontWeight: 700, fontSize: '.85rem' }}>
          <span style={{ color: 'var(--gold)' }}>🏆</span>
          <span style={{ color: 'var(--gold)' }}>{match.winner}</span>
          <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>wins</span>
        </span>
        <span style={{ display: 'flex', gap: '.5rem', alignItems: 'center' }}>
          <ModeBadge mode={match.game_mode} />
          {match.timestamp && (
            <span style={{ fontSize: '.72rem', color: 'var(--text-muted)' }}>
              {new Date(match.timestamp).toLocaleDateString()}
            </span>
          )}
        </span>
      </div>

      {/* Random bans */}
      {randomBans.length > 0 && (
        <div className="mh-random-bans">
          <span className="mh-section-label" style={{ flexShrink: 0 }}>🎲 RANDOM BANS</span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.25rem' }}>
            {randomBans.map(card => <CardImg key={card.name} card={card} size={32} dimmed />)}
          </div>
        </div>
      )}

      {/* Player columns */}
      <div className="mh-body">
        {/* Winner */}
        <div className="mh-player-col mh-won">
          <div className="mh-player-name" style={{ color: 'var(--win)' }}>{match.winner} 🏆</div>
          <div className="mh-section-label" style={{ marginTop: '.5rem', marginBottom: '.3rem' }}>PICKS</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.25rem' }}>
            {(winnerPicks || []).map(card => <CardImg key={card.name} card={card} size={38} />)}
          </div>
          {winnerBans && winnerBans.length > 0 && (
            <>
              <div className="mh-section-label" style={{ marginTop: '.6rem', marginBottom: '.3rem' }}>BANS</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.25rem' }}>
                {winnerBans.map(card => <CardImg key={card.name} card={card} size={30} dimmed />)}
              </div>
            </>
          )}
        </div>

        {/* Divider */}
        <div className="mh-divider" style={{ fontSize: '1.3rem', opacity: .5 }}>⚔</div>

        {/* Loser */}
        <div className="mh-player-col mh-lost" style={{ alignItems: 'flex-end' }}>
          <div className="mh-player-name" style={{ color: 'var(--loss)', textAlign: 'right' }}>{match.loser}</div>
          <div className="mh-section-label" style={{ marginTop: '.5rem', marginBottom: '.3rem', textAlign: 'right' }}>PICKS</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.25rem', justifyContent: 'flex-end' }}>
            {(loserPicks || []).map(card => <CardImg key={card.name} card={card} size={38} />)}
          </div>
          {loserBans && loserBans.length > 0 && (
            <>
              <div className="mh-section-label" style={{ marginTop: '.6rem', marginBottom: '.3rem', textAlign: 'right' }}>BANS</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.25rem', justifyContent: 'flex-end' }}>
                {loserBans.map(card => <CardImg key={card.name} card={card} size={30} dimmed />)}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function LandingPage() {
  const navigate = useNavigate()

  // Draft setup state
  const [p1, setP1]                     = useState('Kevin')
  const [p2, setP2]                     = useState('Jason')
  const [setupErr, setSetupErr]         = useState('')
  const [startLoading, setStartLoading] = useState(false)
  const [aiLoading, setAiLoading]       = useState(false)

  // Dashboard data
  const { data: cardStats,    loading: cardsLoading   } = useAPI('/api/card_stats')
  const { data: playerStats,  loading: playersLoading } = useAPI('/api/player_stats')
  const { data: elo,          loading: eloLoading     } = useAPI('/api/elo')
  const { data: matchHistory, loading: matchesLoading } = useAPI('/api/match_history?limit=5')

  // Draft setup actions
  async function startDraft() {
    if (p1 === p2) { setSetupErr('❌ Player 1 and Player 2 must be different players.'); return }
    setSetupErr('')
    setStartLoading(true)
    try {
      const s = await apiCall('/api/start', 'POST', { p1_name: p1, p2_name: p2 })
      if (s.error) throw new Error(s.error)
      navigate('/draft', { state: { draft: s } })
    } catch (e) {
      setSetupErr(`❌ ${e.message}`)
    }
    setStartLoading(false)
  }

  async function startAiDraft() {
    if (p1 === p2) { setSetupErr('❌ Player 1 and Player 2 must be different players.'); return }
    setSetupErr('')
    setAiLoading(true)
    try {
      const s = await apiCall('/api/start', 'POST', { p1_name: p1, p2_name: p2, ai_mode: true })
      if (s.error) throw new Error(s.error)
      navigate('/draft', { state: { draft: s } })
    } catch (e) {
      setSetupErr(`❌ ${e.message}`)
    }
    setAiLoading(false)
  }

  function swapPlayers() {
    setP1(p2)
    setP2(p1)
  }

  // Derived dashboard data
  const totalGames = cardStats?.[0]?.total_games ?? 0

  const topCards = cardStats
    ? [...cardStats].filter(c => c.games_played >= 3).sort((a, b) => b.win_rate - a.win_rate).slice(0, 5)
    : []

  const mostBanned = cardStats
    ? [...cardStats].filter(c => c.player_bans > 0).sort((a, b) => b.player_bans - a.player_bans).slice(0, 5)
    : []

  const highestRated = cardStats
    ? [...cardStats].filter(c => c.overall_rating != null).sort((a, b) => b.overall_rating - a.overall_rating).slice(0, 5)
    : []

  const players =
    playerStats && elo
      ? Object.entries(playerStats)
          .map(([name, s]) => ({
            name,
            wins: s.wins,
            losses: s.losses,
            elo: elo[name] ?? 1000,
            total: s.wins + s.losses,
            winPct: s.wins + s.losses > 0 ? Math.round((s.wins / (s.wins + s.losses)) * 100) : 0,
          }))
          .sort((a, b) => b.elo - a.elo)
      : []

  const topPlayer = players[0]

  return (
    <>
      <header>
        <span className="header-title">⚔️ CHAOS Draft</span>
        <nav style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <Link to="/player_stats" style={{ color: 'var(--text-muted)', fontSize: '.85rem', textDecoration: 'none' }}>Players</Link>
          <Link to="/stats"        style={{ color: 'var(--text-muted)', fontSize: '.85rem', textDecoration: 'none' }}>Card Stats</Link>
        </nav>
      </header>

      <main>

        {/* ── Setup + summary two-column ── */}
        <div id="setup-wrapper">

          {/* Draft setup form */}
          <div id="setup-screen">
            <h2>Draft Setup</h2>
            <div className="field">
              <label>Player 1 Name</label>
              <select value={p1} onChange={e => setP1(e.target.value)}>
                {PLAYERS.map(name => <option key={name} value={name}>{name}</option>)}
              </select>
            </div>
            <div style={{ display: 'flex', justifyContent: 'center', margin: '.1rem 0' }}>
              <button
                onClick={swapPlayers}
                title="Swap players"
                style={{
                  background: 'transparent', border: '1px solid var(--border)', borderRadius: '999px',
                  color: 'var(--text-muted)', cursor: 'pointer', fontSize: '.85rem',
                  padding: '.25rem .75rem', transition: 'all .15s',
                }}
              >
                ⇅ Swap
              </button>
            </div>
            <div className="field">
              <label>Player 2 Name</label>
              <select value={p2} onChange={e => setP2(e.target.value)}>
                {PLAYERS.map(name => <option key={name} value={name}>{name}</option>)}
              </select>
            </div>
            {p1 === p2 && (
              <div className="error-msg">❌ Player 1 and Player 2 must be different players.</div>
            )}
            {setupErr && p1 !== p2 && (
              <div className="error-msg">{setupErr}</div>
            )}
            <button
              className="btn btn-gold"
              onClick={startDraft}
              disabled={startLoading || p1 === p2}
              style={{ width: '100%', marginTop: '.8rem' }}
            >
              {startLoading ? 'Loading cards…' : '⚔️ Begin Draft'}
            </button>
            <button
              className="btn btn-ai"
              onClick={startAiDraft}
              disabled={aiLoading || p1 === p2}
              style={{ width: '100%', marginTop: '.5rem' }}
            >
              {aiLoading ? 'Loading…' : '🤖 AI Draft'}
            </button>
            <div style={{ display: 'flex', gap: '.5rem', marginTop: '.6rem' }}>
              <Link to="/stats"        className="btn btn-ghost" style={{ flex: 1, padding: '.55rem', textAlign: 'center', textDecoration: 'none', fontSize: '.82rem' }}>
                📊 Card Stats
              </Link>
              <Link to="/player_stats" className="btn btn-ghost" style={{ flex: 1, padding: '.55rem', textAlign: 'center', textDecoration: 'none', fontSize: '.82rem' }}>
                👤 Players
              </Link>
            </div>
          </div>

          {/* Summary stats */}
          <div id="match-history">
            <div className="stat-cards">
              <StatCard label="Total Games" value={cardsLoading ? '—' : totalGames} />
              <StatCard
                label="Top Player"
                value={eloLoading || playersLoading ? '—' : topPlayer ? topPlayer.name : '—'}
                sub={topPlayer && !eloLoading ? `${topPlayer.elo} ELO · ${topPlayer.wins}W ${topPlayer.losses}L` : undefined}
              />
              <StatCard label="Cards in Pool" value={cardsLoading ? '—' : (cardStats?.length ?? 0)} sub="50-card CHAOS pool" />
            </div>
          </div>
        </div>

        {/* ── Top cards + most banned ── */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '1rem', margin: '2rem 0' }}>
          <Panel>
            <PanelHeader>🏆 Top Cards by Win Rate <span style={{ fontWeight: 400, opacity: .7 }}>(min 3 games)</span></PanelHeader>
            {cardsLoading ? <EmptyState>Loading…</EmptyState> : topCards.length === 0 ? <EmptyState>No data yet — play some games!</EmptyState> : (
              <ul style={{ listStyle: 'none' }}>
                {topCards.map((card, i) => (
                  <li key={card.name} style={{ display: 'flex', alignItems: 'center', gap: '.75rem', padding: '.45rem .9rem', borderBottom: '1px solid rgba(42,48,80,.5)', cursor: 'pointer' }} onClick={() => navigate(`/card/${encodeURIComponent(card.name)}`)}>

                    <span style={{ color: 'var(--text-muted)', fontSize: '.75rem', width: 16, flexShrink: 0 }}>{i + 1}</span>
                    <CardIcon card={card} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '.85rem', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{card.name}</div>
                      <div style={{ fontSize: '.72rem', color: 'var(--text-muted)' }}>{card.games_played}g · {card.ban_rate}% ban rate</div>
                    </div>
                    <ElixirPip cost={card.elixir} />
                    <span style={{ color: 'var(--win)', fontWeight: 700, fontSize: '.85rem', fontFamily: "'Rajdhani', sans-serif", minWidth: 40, textAlign: 'right' }}>
                      {card.win_rate}%
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel>
            <PanelHeader>🚫 Most Banned Cards</PanelHeader>
            {cardsLoading ? <EmptyState>Loading…</EmptyState> : mostBanned.length === 0 ? <EmptyState>No bans recorded yet.</EmptyState> : (
              <ul style={{ listStyle: 'none' }}>
                {mostBanned.map((card, i) => (
                  <li key={card.name} style={{ display: 'flex', alignItems: 'center', gap: '.75rem', padding: '.45rem .9rem', borderBottom: '1px solid rgba(42,48,80,.5)', cursor: 'pointer' }} onClick={() => navigate(`/card/${encodeURIComponent(card.name)}`)}>

                    <span style={{ color: 'var(--text-muted)', fontSize: '.75rem', width: 16, flexShrink: 0 }}>{i + 1}</span>
                    <CardIcon card={card} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '.85rem', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{card.name}</div>
                      <div style={{ fontSize: '.72rem', color: 'var(--text-muted)' }}>{card.ban_rate}% ban rate</div>
                    </div>
                    <ElixirPip cost={card.elixir} />
                    <span style={{ color: 'var(--ban)', fontWeight: 700, fontSize: '.85rem', fontFamily: "'Rajdhani', sans-serif", minWidth: 40, textAlign: 'right' }}>
                      {card.player_bans}×
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel>
            <PanelHeader>⭐ Highest Rated Cards</PanelHeader>
            {cardsLoading ? <EmptyState>Loading…</EmptyState> : highestRated.length === 0 ? <EmptyState>No rating data yet.</EmptyState> : (
              <ul style={{ listStyle: 'none' }}>
                {highestRated.map((card, i) => (
                  <li key={card.name} style={{ display: 'flex', alignItems: 'center', gap: '.75rem', padding: '.45rem .9rem', borderBottom: '1px solid rgba(42,48,80,.5)', cursor: 'pointer' }} onClick={() => navigate(`/card/${encodeURIComponent(card.name)}`)}>
                    <span style={{ color: 'var(--text-muted)', fontSize: '.75rem', width: 16, flexShrink: 0 }}>{i + 1}</span>
                    <CardIcon card={card} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '.85rem', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{card.name}</div>
                      <div style={{ fontSize: '.72rem', color: 'var(--text-muted)' }}>{card.games_played}g · {card.win_rate}% win rate</div>
                    </div>
                    <ElixirPip cost={card.elixir} />
                    <span style={{ color: 'var(--gold)', fontWeight: 700, fontSize: '.85rem', fontFamily: "'Rajdhani', sans-serif", minWidth: 40, textAlign: 'right' }}>
                      {(card.overall_rating * 100).toFixed(1)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>

        {/* ── Player leaderboard ── */}
        <Panel>
          <PanelHeader>📊 Player Leaderboard</PanelHeader>
          {playersLoading || eloLoading ? <EmptyState>Loading…</EmptyState> : players.length === 0 ? <EmptyState>No player data yet.</EmptyState> : (
            <div style={{ overflowX: 'auto' }}>
              <table className="leaderboard-table">
                <thead>
                  <tr>
                    <th className="rank-cell">#</th>
                    <th>Player</th>
                    <th style={{ textAlign: 'right' }}>ELO</th>
                    <th style={{ textAlign: 'right' }}>W</th>
                    <th style={{ textAlign: 'right' }}>L</th>
                    <th style={{ textAlign: 'right' }}>Win%</th>
                  </tr>
                </thead>
                <tbody>
                  {players.map((p, i) => (
                    <tr key={p.name} style={{ cursor: 'pointer' }} onClick={() => navigate(`/player_stats/${encodeURIComponent(p.name)}`)}>
                      <td className="rank-cell">{i + 1}</td>
                      <td className="player-name-cell">{p.name}</td>
                      <td className="elo-cell" style={{ textAlign: 'right' }}>{p.elo}</td>
                      <td className="win-cell"  style={{ textAlign: 'right' }}>{p.wins}</td>
                      <td className="loss-cell" style={{ textAlign: 'right' }}>{p.losses}</td>
                      <td style={{ textAlign: 'right', color: p.total === 0 ? 'var(--text-muted)' : p.winPct >= 50 ? 'var(--win)' : 'var(--loss)', fontWeight: 700 }}>
                        {p.total > 0 ? `${p.winPct}%` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        {/* ── Recent match history ── */}
        <div style={{ marginTop: '1rem' }}>
          <Panel>
            <PanelHeader>🕘 Recent Matches</PanelHeader>
            {matchesLoading ? <EmptyState>Loading…</EmptyState> : !matchHistory || matchHistory.length === 0 ? <EmptyState>No matches recorded yet.</EmptyState> : (
              matchHistory.map((match, i) => <MatchCard key={i} match={match} />)
            )}
          </Panel>
        </div>

      </main>
    </>
  )
}
