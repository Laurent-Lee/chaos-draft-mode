import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

// Fetch hook
function useAPI(url) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(url)
      .then(r => r.json())
      .then(setData)
      .catch(setError)
      .finally(() => setLoading(false))
  }, [url])

  return { data, loading, error }
}

function ElixirPip({ cost }) {
  return (
    <span className="elixir-pip">{cost}</span>
  )
}

function CardIcon({ card }) {
  if (card.iconUrl) {
    return (
      <img
        src={card.iconUrl}
        alt={card.name}
        title={card.name}
        className="card-icon"
      />
    )
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
  return (
    <div className="empty">{children}</div>
  )
}

export default function LandingPage() {
  const { data: cardStats, loading: cardsLoading } = useAPI('/api/card_stats')
  const { data: playerStats, loading: playersLoading } = useAPI('/api/player_stats')
  const { data: elo, loading: eloLoading } = useAPI('/api/elo')
  const { data: matchHistory, loading: matchesLoading } = useAPI('/api/match_history?limit=5')

  // Derived data
  const totalGames = cardStats?.[0]?.total_games ?? 0

  const topCards = cardStats
    ? [...cardStats]
        .filter(c => c.games_played >= 3)
        .sort((a, b) => b.win_rate - a.win_rate)
        .slice(0, 5)
    : []

  const mostBanned = cardStats
    ? [...cardStats]
        .filter(c => c.player_bans > 0)
        .sort((a, b) => b.player_bans - a.player_bans)
        .slice(0, 5)
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
            winPct:
              s.wins + s.losses > 0
                ? Math.round((s.wins / (s.wins + s.losses)) * 100)
                : 0,
          }))
          .sort((a, b) => b.elo - a.elo)
      : []

  const topPlayer = players[0]

  return (
    <>
      <header>
        <span className="header-title">⚔️ CHAOS Draft</span>
        <nav style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <Link to="/" style={{ color: 'var(--text-muted)', fontSize: '.85rem', textDecoration: 'none' }}>Draft</Link>
          <Link to="/player_stats" style={{ color: 'var(--text-muted)', fontSize: '.85rem', textDecoration: 'none' }}>Players</Link>
          <Link to="/stats" style={{ color: 'var(--text-muted)', fontSize: '.85rem', textDecoration: 'none' }}>Card Stats</Link>
        </nav>
      </header>

      <main>

        {/* Hero */}
        <section style={{ textAlign: 'center', padding: '2rem 0 1.5rem' }}>
          <h1>Clash Royale C.H.A.O.S. Draft</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '.95rem', maxWidth: 480, margin: '.75rem auto 0' }}>
            Ban, pick, and battle. Every game tracked — win rates, ELO, and head-to-head matchups.
          </p>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '.75rem', marginTop: '1.5rem' }}>
            <Link to="/" className="btn btn-gold">⚔️ Start Draft</Link>
            <Link to="/player_stats" className="btn btn-ghost">📊 Leaderboard</Link>
          </div>
        </section>

        {/* Summary stats */}
        <div className="stat-cards" style={{ maxWidth: 520, margin: '0 auto 2rem' }}>
          <StatCard
            label="Total Games"
            value={cardsLoading ? '—' : totalGames}
          />
          <StatCard
            label="Top Player"
            value={eloLoading || playersLoading ? '—' : topPlayer ? topPlayer.name : '—'}
            sub={topPlayer && !eloLoading ? `${topPlayer.elo} ELO · ${topPlayer.wins}W ${topPlayer.losses}L` : undefined}
          />
          <StatCard
            label="Cards in Pool"
            value={cardsLoading ? '—' : (cardStats?.length ?? 0)}
            sub="50-card CHAOS pool"
          />
        </div>

        {/* Top cards + most banned */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>

          {/* Top cards by win rate */}
          <Panel>
            <PanelHeader>🏆 Top Cards by Win Rate <span style={{ fontWeight: 400, opacity: .7 }}>(min 3 games)</span></PanelHeader>
            {cardsLoading ? (
              <EmptyState>Loading…</EmptyState>
            ) : topCards.length === 0 ? (
              <EmptyState>No data yet — play some games!</EmptyState>
            ) : (
              <ul style={{ listStyle: 'none' }}>
                {topCards.map((card, i) => (
                  <li
                    key={card.name}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '.75rem',
                      padding: '.45rem .9rem',
                      borderBottom: '1px solid rgba(42,48,80,.5)',
                    }}
                  >
                    <span style={{ color: 'var(--text-muted)', fontSize: '.75rem', width: 16, flexShrink: 0 }}>{i + 1}</span>
                    <CardIcon card={card} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '.85rem', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {card.name}
                      </div>
                      <div style={{ fontSize: '.72rem', color: 'var(--text-muted)' }}>
                        {card.games_played}g · {card.ban_rate}% ban rate
                      </div>
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

          {/* Most banned */}
          <Panel>
            <PanelHeader>🚫 Most Banned Cards</PanelHeader>
            {cardsLoading ? (
              <EmptyState>Loading…</EmptyState>
            ) : mostBanned.length === 0 ? (
              <EmptyState>No bans recorded yet.</EmptyState>
            ) : (
              <ul style={{ listStyle: 'none' }}>
                {mostBanned.map((card, i) => (
                  <li
                    key={card.name}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '.75rem',
                      padding: '.45rem .9rem',
                      borderBottom: '1px solid rgba(42,48,80,.5)',
                    }}
                  >
                    <span style={{ color: 'var(--text-muted)', fontSize: '.75rem', width: 16, flexShrink: 0 }}>{i + 1}</span>
                    <CardIcon card={card} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '.85rem', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {card.name}
                      </div>
                      <div style={{ fontSize: '.72rem', color: 'var(--text-muted)' }}>
                        {card.ban_rate}% ban rate
                      </div>
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
        </div>

        {/* Player Leaderboard */}
        <Panel>
          <PanelHeader>📊 Player Leaderboard</PanelHeader>
          {playersLoading || eloLoading ? (
            <EmptyState>Loading…</EmptyState>
          ) : players.length === 0 ? (
            <EmptyState>No player data yet.</EmptyState>
          ) : (
            <div style={{ overflowX: 'auto', marginBottom: '1.5rem' }}>
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
                    <tr key={p.name}>
                      <td className="rank-cell">{i + 1}</td>
                      <td className="player-name-cell">
                        <Link to="/player_stats" style={{ color: 'inherit', textDecoration: 'none' }}>
                          {p.name}
                        </Link>
                      </td>
                      <td className="elo-cell" style={{ textAlign: 'right' }}>{p.elo}</td>
                      <td className="win-cell" style={{ textAlign: 'right' }}>{p.wins}</td>
                      <td className="loss-cell" style={{ textAlign: 'right' }}>{p.losses}</td>
                      <td className="winpct-cell" style={{
                        textAlign: 'right',
                        color: p.total === 0 ? 'var(--text-muted)' : p.winPct >= 50 ? 'var(--win)' : 'var(--loss)',
                      }}>
                        {p.total > 0 ? `${p.winPct}%` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        {/* Recent Matches */}
        <div style={{ marginTop: '1.5rem' }}>
          <div className="section-title" style={{ marginBottom: '.75rem' }}>🕹️ Recent Matches</div>
          {matchesLoading ? (
            <div className="loading">Loading…</div>
          ) : !matchHistory || matchHistory.length === 0 ? (
            <div className="empty">No matches recorded yet.</div>
          ) : (
            matchHistory.map((match, i) => {
              const firstPick  = match['1st_pick'] || '?'
              const secondPick = match['2nd_pick'] || '?'
              const firstWon   = match.winner === firstPick
              return (
                <div className="mh-game" key={i}>
                  <div className="mh-header">
                    <span style={{ color: 'var(--win)', fontWeight: 700 }}>🏆 {match.winner} wins</span>
                    {match.game_mode === 'AI Draft'
                      ? <span className="mode-badge mode-badge-ai">🤖 AI Draft</span>
                      : match.game_mode === 'Normal Draft'
                        ? <span className="mode-badge mode-badge-normal">⚔️ Normal Draft</span>
                        : null}
                    {match.timestamp && (
                      <span>{new Date(match.timestamp).toLocaleDateString()}</span>
                    )}
                  </div>
                  <div className="mh-body">
                    <div className={`mh-player-col ${firstWon ? 'mh-won' : 'mh-lost'}`}>
                      <div className="mh-player-name" style={{ color: firstWon ? 'var(--win)' : 'var(--loss)' }}>
                        {firstPick}{firstWon ? ' 🏆' : ''}
                      </div>
                      <div className="mh-section-label">Deck</div>
                      <div className="mh-card-row">
                        {(match.first_picks || []).map(card =>
                          card.iconUrl
                            ? <img key={card.name} src={card.iconUrl} alt={card.name} title={card.name} className="mh-card-img" />
                            : <div key={card.name} style={{ width: 36, height: 36, borderRadius: '.25rem', background: 'var(--surface2)' }} />
                        )}
                      </div>
                    </div>
                    <div className="mh-divider" />
                    <div className={`mh-player-col ${!firstWon ? 'mh-won' : 'mh-lost'}`}>
                      <div className="mh-player-name" style={{ color: !firstWon ? 'var(--win)' : 'var(--loss)' }}>
                        {secondPick}{!firstWon ? ' 🏆' : ''}
                      </div>
                      <div className="mh-section-label">Deck</div>
                      <div className="mh-card-row">
                        {(match.second_picks || []).map(card =>
                          card.iconUrl
                            ? <img key={card.name} src={card.iconUrl} alt={card.name} title={card.name} className="mh-card-img" />
                            : <div key={card.name} style={{ width: 36, height: 36, borderRadius: '.25rem', background: 'var(--surface2)' }} />
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>

      </main>

      <footer style={{ borderTop: '1px solid var(--border)', padding: '1.5rem 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: '.8rem', marginTop: '1rem' }}>
        CHAOS Draft Tool — Clash Royale fan project
      </footer>
    </>
  )
}
