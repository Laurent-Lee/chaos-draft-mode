import { useState, useEffect, useRef } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { QRCodeCanvas } from 'qrcode.react'
import { CARD_TIER, TIER_ORDER, TIER_ICONS } from '../data/cardTiers'
import { CARD_TYPE, TYPE_ORDER, TYPE_ICONS } from '../data/cardTypes'

// ── API helper ────────────────────────────────────────────────────────────────
async function apiCall(path, method = 'GET', body = null) {
  const r = await fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : null,
  })
  return r.json()
}

// ── Web Audio tick sounds ─────────────────────────────────────────────────────
let audioCtx = null
function getAudioCtx() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)()
  return audioCtx
}
function playTick(urgent) {
  try {
    const ctx  = getAudioCtx()
    const osc  = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.frequency.value = urgent ? 320 : 220
    osc.type = 'square'
    gain.gain.setValueAtTime(urgent ? 0.18 : 0.10, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.08)
    osc.start(ctx.currentTime)
    osc.stop(ctx.currentTime + 0.08)
  } catch (_) { /* audio unavailable */ }
}

// ── Small helper ──────────────────────────────────────────────────────────────
function avgElixir(picks) {
  const costs = picks.filter(c => c.elixir > 0).map(c => c.elixir)
  return costs.length ? (costs.reduce((a, b) => a + b, 0) / costs.length).toFixed(1) : '—'
}

function cardFallback(size = 60) {
  return `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='${size}' height='${size}'%3E%3Crect width='${size}' height='${size}' fill='%23222'/%3E%3Ctext x='${size/2}' y='${size/2+4}' text-anchor='middle' fill='%23555' font-size='12'%3E?%3C/text%3E%3C/svg%3E`
}

// ── Sub-components ────────────────────────────────────────────────────────────

function CardThumb({ card, isBan }) {
  const cls  = isBan ? 'mh-ban-img' : 'mh-card-img'
  const size = isBan ? 28 : 32
  const fb   = cardFallback(size)
  return (
    <img
      className={cls}
      src={card.iconUrl || fb}
      alt={card.name}
      title={card.name}
      onError={e => { e.target.src = fb }}
    />
  )
}

function MatchHistoryList({ games, mhTotal, mhLimit, onShowMore }) {
  if (!games.length) {
    return <p style={{ color: 'var(--text-muted)', fontSize: '.85rem' }}>No games yet.</p>
  }
  return (
    <>
      {games.map((g, gi) => {
        const firstName      = g['1st_pick'] || '?'
        const secondName     = g['2nd_pick'] || '?'
        const firstWon       = g.winner === firstName
        const modeBadge      = g.game_mode === 'AI Draft'
          ? <span className="mode-badge mode-badge-ai">🤖 AI Draft</span>
          : g.game_mode === 'Normal Draft'
            ? <span className="mode-badge mode-badge-normal">⚔️ Normal Draft</span>
            : null

        return (
          <div className="mh-game" key={gi}>
            <div className="mh-header">
              <span className="mh-winner-tag">🏆 {g.winner || '?'} wins</span>
              {modeBadge}
            </div>
            {(g.random_bans || []).length > 0 && (
              <div style={{ display:'flex', alignItems:'center', gap:'.5rem', padding:'.4rem .9rem .1rem', flexWrap:'wrap' }}>
                <span style={{ fontSize:'.6rem', color:'#ff9944', letterSpacing:'.08em', textTransform:'uppercase' }}>🎲 Random Bans</span>
                <div style={{ display:'flex', gap:'3px', flexWrap:'wrap' }}>
                  {(g.random_bans || []).map((c, i) => <CardThumb key={i} card={c} isBan />)}
                </div>
              </div>
            )}
            <div className="mh-body">
              <div className={`mh-player-col ${firstWon ? 'mh-won' : 'mh-lost'}`}>
                <div className={`mh-player-name ${firstWon ? 'winner' : 'loser'}`}>
                  {firstName}{firstWon ? ' 🏆' : ''}
                </div>
                {(g.first_picks || []).length > 0 && (
                  <>
                    <div className="mh-section-label">Picks</div>
                    <div className="mh-card-row">{(g.first_picks || []).map((c, i) => <CardThumb key={i} card={c} isBan={false} />)}</div>
                  </>
                )}
                {(g.first_bans || []).length > 0 && (
                  <>
                    <div className="mh-section-label" style={{ marginTop: '4px' }}>Bans</div>
                    <div className="mh-ban-row">{(g.first_bans || []).map((c, i) => <CardThumb key={i} card={c} isBan />)}</div>
                  </>
                )}
              </div>
              <div className="mh-divider">⚔️</div>
              <div className={`mh-player-col ${!firstWon ? 'mh-won' : 'mh-lost'}`} style={{ textAlign: 'right' }}>
                <div className={`mh-player-name ${!firstWon ? 'winner' : 'loser'}`}>
                  {!firstWon ? '🏆 ' : ''}{secondName}
                </div>
                {(g.second_picks || []).length > 0 && (
                  <>
                    <div className="mh-section-label">Picks</div>
                    <div className="mh-card-row" style={{ justifyContent: 'flex-end' }}>{(g.second_picks || []).map((c, i) => <CardThumb key={i} card={c} isBan={false} />)}</div>
                  </>
                )}
                {(g.second_bans || []).length > 0 && (
                  <>
                    <div className="mh-section-label" style={{ marginTop: '4px' }}>Bans</div>
                    <div className="mh-ban-row" style={{ justifyContent: 'flex-end' }}>{(g.second_bans || []).map((c, i) => <CardThumb key={i} card={c} isBan />)}</div>
                  </>
                )}
              </div>
            </div>
          </div>
        )
      })}
      {mhTotal > mhLimit && (
        <button className="mh-show-more" onClick={onShowMore}>Show more…</button>
      )}
    </>
  )
}

function Sidebar({ playerName, picks, side }) {
  // Group picks by card type
  const groups = {}
  picks.forEach(c => {
    const t = CARD_TYPE[c.name] || 'Other'
    ;(groups[t] = groups[t] || []).push(c)
  })
  const sortedTypes = Object.keys(groups).sort(
    (a, b) => (TYPE_ORDER[a] ?? 99) - (TYPE_ORDER[b] ?? 99)
  )

  return (
    <div className={`sidebar ${side}-side`}>
      <div className="sidebar-name">{playerName}</div>
      <h3>Picks ({picks.length}/8)</h3>
      <div>
        {sortedTypes.map(type => (
          <div key={type}>
            <div className="type-divider">
              <span>{TYPE_ICONS[type] || ''} {type}</span>
            </div>
            {groups[type].map((c, i) => (
              <div className="mini-card" key={i}>
                <img
                  src={c.iconUrl}
                  alt={c.name}
                  onError={e => { e.target.style.display = 'none' }}
                />
                <span>{c.name}</span>
                <span className="elixir">{c.elixir || '?'}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
      <div className="avg-elixir">Avg: <span>{avgElixir(picks)}</span></div>
    </div>
  )
}

function CardPool({ pool, onAction, rarityFilter, setRarityFilter, sortMode, setSortMode, elixirAsc, setElixirAsc, search, setSearch, aiThinking }) {
  // Filter
  let filtered = pool
  if (rarityFilter !== 'All') filtered = filtered.filter(c => c.rarity === rarityFilter)
  if (search) filtered = filtered.filter(c => c.name.toLowerCase().includes(search.toLowerCase()))

  // Build rendered groups
  let content = null

  if (sortMode === 'elixir') {
    const sorted = [...filtered].sort((a, b) => elixirAsc ? a.elixir - b.elixir : b.elixir - a.elixir)
    content = (
      <div className="card-grid">
        {sorted.map(c => <CardItem key={c.id} card={c} onClick={() => onAction(c.id)} />)}
      </div>
    )
  } else if (sortMode === 'tier') {
    const sorted = [...filtered].sort((a, b) => {
      const tDiff = (TIER_ORDER[CARD_TIER[a.name]] ?? 99) - (TIER_ORDER[CARD_TIER[b.name]] ?? 99)
      if (tDiff !== 0) return tDiff
      return elixirAsc ? a.elixir - b.elixir : b.elixir - a.elixir
    })
    const groups = {}
    sorted.forEach(c => {
      const t = CARD_TIER[c.name] || 'F'
      ;(groups[t] = groups[t] || []).push(c)
    })
    const groupEntries = Object.entries(groups).sort(
      ([ta], [tb]) => (TIER_ORDER[ta] ?? 99) - (TIER_ORDER[tb] ?? 99)
    )
    content = (
      <div className="card-grid">
        {groupEntries.map(([tier, cards]) => (
          <div key={tier} style={{ display: 'contents' }}>
            <div className={`type-label tier-label tier-${tier.replace('+', '\\+')}`} style={{ gridColumn: '1 / -1' }}>
              {TIER_ICONS[tier] || ''} <span style={{ fontSize: '.9rem' }}>{tier}</span>{' '}
              <span className="type-count">{cards.length}</span>
            </div>
            <div className="card-row" style={{ gridColumn: '1 / -1' }}>
              {cards.map(c => <CardItem key={c.id} card={c} onClick={() => onAction(c.id)} />)}
            </div>
          </div>
        ))}
      </div>
    )
  } else {
    // type mode
    const sorted = [...filtered].sort((a, b) => {
      const tDiff = (TYPE_ORDER[CARD_TYPE[a.name]] ?? 99) - (TYPE_ORDER[CARD_TYPE[b.name]] ?? 99)
      if (tDiff !== 0) return tDiff
      return elixirAsc ? a.elixir - b.elixir : b.elixir - a.elixir
    })
    const groups = {}
    sorted.forEach(c => {
      const t = CARD_TYPE[c.name] || 'Other'
      ;(groups[t] = groups[t] || []).push(c)
    })
    const groupEntries = Object.entries(groups).sort(
      ([ta], [tb]) => (TYPE_ORDER[ta] ?? 99) - (TYPE_ORDER[tb] ?? 99)
    )
    content = (
      <div className="card-grid">
        {groupEntries.map(([type, cards]) => (
          <div key={type} style={{ display: 'contents' }}>
            <div className="type-label" style={{ gridColumn: '1 / -1' }}>
              {TYPE_ICONS[type] || ''} {type}{' '}
              <span className="type-count">{cards.length}</span>
            </div>
            <div className="card-row" style={{ gridColumn: '1 / -1' }}>
              {cards.map(c => <CardItem key={c.id} card={c} onClick={() => onAction(c.id)} />)}
            </div>
          </div>
        ))}
      </div>
    )
  }

  const rarities = ['All', 'Common', 'Rare', 'Epic', 'Legendary', 'Champion']

  return (
    <div id="pool-area" style={{ position: 'relative' }}>
      {aiThinking && (
        <div id="ai-thinking-overlay" style={{ display: 'flex' }}>
          <div className="ai-spinner">🤖</div>
          <div className="ai-label">AI is thinking…</div>
        </div>
      )}
      <div className="filters">
        <input
          id="search-box"
          type="text"
          placeholder="Search…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        {rarities.map(r => (
          <button
            key={r}
            className={`filter-btn${rarityFilter === r ? ' active' : ''}`}
            onClick={() => setRarityFilter(r)}
          >
            {r}
          </button>
        ))}
        <div className="sort-toggle">
          <button
            id="sort-type-btn"
            className={sortMode === 'type' ? 'active' : ''}
            onClick={() => setSortMode('type')}
          >
            ⚔️ Type
          </button>
          <button
            id="sort-tier-btn"
            className={sortMode === 'tier' ? 'active' : ''}
            onClick={() => setSortMode('tier')}
          >
            🏆 Tier
          </button>
          <button
            id="sort-elixir-btn"
            className={sortMode === 'elixir' ? 'active' : ''}
            onClick={() => setSortMode('elixir')}
          >
            <img src="/elixir.svg" alt="elixir" style={{ width: '14px', height: '14px', verticalAlign: 'middle', marginRight: '2px' }} /> Elixir
          </button>
        </div>
        <button
          id="elixir-dir-btn"
          className="filter-btn"
          onClick={() => setElixirAsc(v => !v)}
          title="Toggle elixir sort direction"
        >
          <img src="/elixir.svg" alt="elixir" style={{ width: '14px', height: '14px', verticalAlign: 'middle', marginRight: '2px' }} />
          {elixirAsc ? '▲' : '▼'}
        </button>
      </div>
      <h3 id="pool-title">Card Pool ({filtered.length} available)</h3>
      {content}
    </div>
  )
}

function CardItem({ card, onClick }) {
  const fb = cardFallback(60)
  return (
    <div className={`card rarity-${card.rarity}`} onClick={onClick}>
      <img
        src={card.iconUrl}
        alt={card.name}
        onError={e => { e.target.src = fb }}
      />
      <div className="card-name">{card.name}</div>
      <div className="card-elixir">{card.elixir || '?'}</div>
    </div>
  )
}

function BannedStrip({ banned, p1Name, p2Name }) {
  if (!banned || !banned.length) return null
  return (
    <div id="banned-area">
      <div className="banned-strip" id="banned-list">
        <label>🚫 Banned ({banned.length})</label>
        {banned.map((b, i) => {
          const byColor = b.by === 'random' ? 'var(--text-muted)' : b.by === 1 ? 'var(--p1)' : 'var(--p2)'
          const byLabel = b.by === 'random' ? 'RANDOM' : b.by === 1 ? p1Name : p2Name
          return (
            <div className="mini-card" key={i}>
              <img
                src={b.card.iconUrl}
                alt={b.card.name}
                onError={e => { e.target.style.display = 'none' }}
              />
              <span>{b.card.name}</span>
              <span style={{ marginLeft: 'auto', fontSize: '.65rem', color: byColor }}>
                {byLabel}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function TurnBar({ draft, timerSecs, timerPaused, onTogglePause, onUndo }) {
  const seq = draft.phase === 'ban' ? draft.ban_sequence : draft.pick_sequence
  const idx = draft.action_index
  const p1t = <span className="p1c">{draft.p1_name}</span>
  const p2t = <span className="p2c">{draft.p2_name}</span>
  const act = draft.phase === 'ban' ? 'bans a card' : 'picks a card'
  const nothingToUndo = draft.phase === 'ban' && draft.action_index === 0

  const mm = String(Math.floor(timerSecs / 60)).padStart(2, '0')
  const ss = String(timerSecs % 60).padStart(2, '0')
  const timerClass = timerSecs <= 10 ? 'urgent' : 'ok'

  return (
    <div id="turn-bar">
      <div className="turn-text" id="turn-text">
        {draft.current_player === 1 ? p1t : p2t} {act}
        {draft.ai_mode && <span className="ai-mode-tag">🤖 AI Mode</span>}
      </div>
      <div className="progress-dots" id="progress-dots">
        {seq.map((p, i) => {
          let cls = 'dot ' + (p === 1 ? 'p1' : 'p2')
          if (i < idx) cls += ' done'
          if (i === idx) cls += ' active'
          return (
            <div
              key={i}
              className={cls}
              title={`${p === 1 ? draft.p1_name : draft.p2_name} ${draft.phase === 'ban' ? 'ban' : 'pick'} ${i + 1}`}
            />
          )
        })}
      </div>
      <div id="timer-block" style={{ display: draft.ai_mode ? 'none' : 'flex' }}>
        <button
          className="btn-timer"
          id="btn-undo"
          onClick={onUndo}
          title="Undo last pick or ban"
          disabled={nothingToUndo}
        >
          ↩ Undo
        </button>
        <button
          className={`btn-timer${timerPaused ? ' paused' : ''}`}
          id="btn-pause"
          onClick={onTogglePause}
        >
          {timerPaused ? '▶ Resume' : '⏸ Pause'}
        </button>
        <div id="timer-display" className={timerClass}>{mm}:{ss}</div>
      </div>
    </div>
  )
}

function DeckPanel({ playerName, picks, link, playerNum, onWin, wonAlready, onCopyLink }) {
  const color = playerNum === 1 ? 'var(--p1)' : 'var(--p2)'
  return (
    <div className="deck-box">
      <div className="deck-player-name" style={{ color }}>{playerName}</div>

      <div className="done-grid">
        {picks.map((c, i) => (
          <div className="done-card" key={i}>
            <img src={c.iconUrl} alt={c.name} onError={e => { e.target.style.display = 'none' }} />
            <div className="cn">{c.name}</div>
          </div>
        ))}
      </div>

      <a className="deck-link-url" href={link} target="_blank" rel="noreferrer">{link}</a>

      <div className="btn-row" style={{ marginTop: '.75rem' }}>
        <button className="btn btn-copy-green" onClick={onCopyLink}>📋 COPY DECK LINK</button>
        <a className="btn btn-open-cr" href={link} target="_blank" rel="noreferrer">📲 OPEN IN CR</a>
      </div>

      <div className="qr-section">
        <div className="qr-label">📱 SCAN TO IMPORT DECK</div>
        <QRCodeCanvas value={link || 'https://example.com'} size={180} />
      </div>

      <div className="avg-elixir-row">
        Avg elixir: <span style={{ color: 'var(--gold)', fontWeight: 700 }}>{avgElixir(picks)}</span>
      </div>

      <button
        className="btn-winner-full"
        onClick={onWin}
        disabled={wonAlready}
      >
        🏆 {playerName.toUpperCase()} WINS!
      </button>
    </div>
  )
}

function DoneScreen({ draft, winnerInfo, onDeclareWinner, onReset, onCopyLink, aiLogOpen, setAiLogOpen }) {
  const p1Link = draft.p1_deck_link || '#'
  const p2Link = draft.p2_deck_link || '#'

  return (
    <div id="done-screen" style={{ display: 'block' }}>
      <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
        <h2 style={{ fontFamily: "'Cinzel Decorative', serif", color: 'var(--gold)', fontSize: '1.4rem', marginBottom: '.4rem' }}>
          🏆 Draft Complete!
        </h2>
        <p style={{ color: 'var(--text-muted)' }}>
          Copy a deck link and open it on your phone — it imports straight into Clash Royale.
        </p>
      </div>

      <div className="done-decks">
        <DeckPanel
          playerName={draft.p1_name}
          picks={draft.p1_picks || []}
          link={p1Link}
          playerNum={1}
          onWin={() => onDeclareWinner(1)}
          wonAlready={!!winnerInfo}
          onCopyLink={() => onCopyLink(1, p1Link)}
        />
        <DeckPanel
          playerName={draft.p2_name}
          picks={draft.p2_picks || []}
          link={p2Link}
          playerNum={2}
          onWin={() => onDeclareWinner(2)}
          wonAlready={!!winnerInfo}
          onCopyLink={() => onCopyLink(2, p2Link)}
        />
      </div>

      {/* AI reasoning log (done screen) */}
      {draft.ai_mode && draft.ai_log && draft.ai_log.length > 0 && (
        <div id="done-ai-log" style={{ display: 'block' }}>
          <div
            id="done-ai-log-header"
            onClick={() => setAiLogOpen(v => !v)}
          >
            <span>🤖 AI Draft Reasoning</span>
            <span id="done-ai-log-toggle" className={aiLogOpen ? 'open' : ''}>▼</span>
          </div>
          {aiLogOpen && (
            <div id="done-ai-log-body" style={{ display: 'flex', flexDirection: 'column' }}>
              {(() => {
                const bans  = draft.ai_log.filter(e => e.phase === 'ban')
                const picks = draft.ai_log.filter(e => e.phase === 'pick')
                return (
                  <>
                    {bans.length > 0 && (
                      <>
                        <div className="done-ai-phase-label">🚫 Ban Phase</div>
                        {bans.map((e, i) => (
                          <DoneAiEntry key={i} entry={e} />
                        ))}
                      </>
                    )}
                    {picks.length > 0 && (
                      <>
                        <div className="done-ai-phase-label">✅ Pick Phase</div>
                        {picks.map((e, i) => (
                          <DoneAiEntry key={i} entry={e} />
                        ))}
                      </>
                    )}
                  </>
                )
              })()}
            </div>
          )}
        </div>
      )}

      {/* Winner banner */}
      {winnerInfo && (
        <div id="winner-banner" style={{ display: 'block' }}>
          <h3 id="winner-banner-text">🏆 {winnerInfo.winner} wins!</h3>
          <p id="winner-banner-sub">
            {winnerInfo.winner} defeated {winnerInfo.loser} — result saved to output.csv
          </p>
          <button className="btn btn-gold" style={{ maxWidth: '200px' }} onClick={onReset}>
            ↺ New Draft
          </button>
        </div>
      )}
    </div>
  )
}

function DoneAiEntry({ entry }) {
  const color  = entry.player === 1 ? 'var(--p1)' : 'var(--p2)'
  const action = entry.phase === 'ban' ? '🚫 banned' : '✅ picked'
  return (
    <div className="done-ai-entry">
      <span className="done-ai-entry-who" style={{ color }}>{entry.player_name}</span>
      <span className="done-ai-entry-action">{action}</span>
      <span className="done-ai-entry-card">{entry.card}</span>
      {entry.reason && <div className="done-ai-entry-reason">{entry.reason}</div>}
    </div>
  )
}

// ── Main DraftPage component ──────────────────────────────────────────────────
export default function DraftPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const { lobbyId } = useParams()

  const [draft, setDraft]               = useState(null)
  const [rarityFilter, setRarityFilter] = useState('All')
  const [sortMode, setSortMode]         = useState('type')
  const [elixirAsc, setElixirAsc]       = useState(true)
  const [search, setSearch]             = useState('')
  const [timerSecs, setTimerSecs]       = useState(30)
  const [timerPaused, setTimerPaused]   = useState(false)
  const [winnerInfo, setWinnerInfo]     = useState(null)
  const [aiThinking, setAiThinking]     = useState(false)
  const [aiLogOpen, setAiLogOpen]       = useState(false)
  const [copyMsg, setCopyMsg]           = useState({})  // { 1: bool, 2: bool }

  // Refs to avoid stale closures
  const draftRef      = useRef(draft)
  const timerRef      = useRef(null)
  const tickTimeoutRef = useRef(null)
  const pausedRef     = useRef(timerPaused)
  const stickyTopRef  = useRef(null)

  // Keep refs in sync
  useEffect(() => { draftRef.current = draft }, [draft])
  useEffect(() => { pausedRef.current = timerPaused }, [timerPaused])

  // Fetch draft state from API on mount (supports opening in a new tab)
  useEffect(() => {
    if (!lobbyId) { navigate('/'); return }
    fetch(`/api/${lobbyId}/state`)
      .then(r => r.json())
      .then(s => {
        if (s.error) { navigate('/'); return }
        setDraft(s)
        if (s.phase !== 'done' && !s.ai_mode) startTimer()
      })
      .catch(() => navigate('/'))
  }, [lobbyId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Track sticky-top height so sidebars can stick directly below it
  useEffect(() => {
    const el = stickyTopRef.current
    if (!el) return
    const header = document.querySelector('header')
    function update() {
      const offset = (header?.offsetHeight || 0) + (el?.offsetHeight || 0)
      document.documentElement.style.setProperty('--controls-offset', `${offset}px`)
    }
    const ro = new ResizeObserver(update)
    ro.observe(el)
    if (header) ro.observe(header)
    update()
    return () => ro.disconnect()
  }, []) // runs once on mount

  // ── Timer ───────────────────────────────────────────────────────────────────
  function scheduleTickSound(secs) {
    clearTimeout(tickTimeoutRef.current)
    if (pausedRef.current || secs <= 0 || secs > 10) return
    const delay = secs > 5 ? 800 : secs > 3 ? 500 : 250
    tickTimeoutRef.current = setTimeout(() => {
      if (pausedRef.current) return
      playTick(true)
      // get updated secs from closure — re-read state via interval pattern
      scheduleTickSound(secs - (delay / 1000))
    }, delay)
  }

  function stopTimer() {
    clearInterval(timerRef.current)
    clearTimeout(tickTimeoutRef.current)
    timerRef.current = null
    tickTimeoutRef.current = null
  }

  function startTimer() {
    stopTimer()
    setTimerSecs(30)
    setTimerPaused(false)
    pausedRef.current = false

    let secs = 30
    timerRef.current = setInterval(() => {
      if (pausedRef.current) return
      secs--
      if (secs <= 0) {
        secs = 0
        setTimerSecs(0)
        stopTimer()
        autoPickRandom()
        return
      }
      setTimerSecs(secs)
      if (secs === 10) {
        scheduleTickSound(secs)
      }
    }, 1000)
  }

  function autoPickRandom() {
    const d = draftRef.current
    if (!d || !d.pool || d.pool.length === 0) return
    const randomCard = d.pool[Math.floor(Math.random() * d.pool.length)]
    apiCall(`/api/${lobbyId}/action`, 'POST', { card_id: randomCard.id }).then(s => {
      if (s.error) { console.warn('Auto-pick failed:', s.error); return }
      applyState(s)
    })
  }

  function togglePause() {
    setTimerPaused(prev => {
      const next = !prev
      pausedRef.current = next
      if (!next) {
        // resuming — reschedule tick sound
        scheduleTickSound(timerSecs)
      } else {
        clearTimeout(tickTimeoutRef.current)
      }
      return next
    })
  }

  // ── AI auto-trigger ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!draft) return
    if (!draft.ai_mode) return
    if (draft.phase !== 'ban' && draft.phase !== 'pick') return

    setAiThinking(true)
    const t = setTimeout(async () => {
      try {
        const s = await apiCall(`/api/${lobbyId}/ai_action`, 'POST')
        if (s && s.error) {
          setAiThinking(false)
          console.warn('AI action error:', s.error)
          return
        }
        setAiThinking(false)
        setDraft(s)
      } catch (e) {
        setAiThinking(false)
        console.warn('AI action failed:', e)
      }
    }, 800)
    return () => clearTimeout(t)
  }, [draft?.action_index, draft?.phase, draft?.ai_mode]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Apply state (transition phases) ────────────────────────────────────────
  function applyState(s) {
    setAiThinking(false)
    setDraft(s)
    if (s.phase !== 'done') {
      if (!s.ai_mode) {
        startTimer()
      } else {
        stopTimer()
      }
    } else {
      stopTimer()
    }
  }

  // ── Actions ─────────────────────────────────────────────────────────────────
  async function doAction(id) {
    const s = await apiCall(`/api/${lobbyId}/action`, 'POST', { card_id: id })
    if (s.error) { alert(s.error); return }
    applyState(s)
  }

  async function undoAction() {
    const s = await apiCall(`/api/${lobbyId}/undo`, 'POST')
    if (s.error) { alert(s.error); return }
    applyState(s)
  }

  async function resetDraft() {
    stopTimer()
    await apiCall(`/api/${lobbyId}/reset`, 'POST')
    navigate('/')
  }

  async function declareWinner(player) {
    try {
      const res = await apiCall(`/api/${lobbyId}/record_winner`, 'POST', { winner: player })
      if (res.error) { alert('Error saving result: ' + res.error); return }
      setWinnerInfo({ winner: res.winner, loser: res.loser })
    } catch (e) {
      alert('Failed to save result: ' + e.message)
    }
  }

  function handleCopyLink(player, link) {
    navigator.clipboard.writeText(link).then(() => {
      setCopyMsg(prev => ({ ...prev, [player]: true }))
      setTimeout(() => setCopyMsg(prev => ({ ...prev, [player]: false })), 2200)
    })
  }

  // ── Phase badge ─────────────────────────────────────────────────────────────
  function phaseBadge() {
    if (!draft) return null
    const ph = draft.phase
    const label = ph === 'ban' ? '🚫 Ban Phase' : ph === 'pick' ? '✅ Pick Phase' : '🏆 Done'
    return <div id="phase-badge" className={`phase-badge phase-${ph}`}>{label}</div>
  }

  // ── Render ──────────────────────────────────────────────────────────────────
  const showDraft = draft && draft.phase !== 'done'
  const showDone  = draft && draft.phase === 'done'

  return (
    <>
      <header>
        <h1>⚔️ CR Draft</h1>
        {phaseBadge()}
        <button className="btn btn-ghost" onClick={resetDraft}>↺ Restart</button>
      </header>

      <main>

        {/* ── DRAFT SCREEN ── */}
        {showDraft && (
          <div id="draft-screen" style={{ display: 'block' }}>
            <div id="sticky-top" ref={stickyTopRef}>
              <TurnBar
                draft={draft}
                timerSecs={timerSecs}
                timerPaused={timerPaused}
                onTogglePause={togglePause}
                onUndo={undoAction}
              />
              <BannedStrip
                banned={draft.banned}
                p1Name={draft.p1_name}
                p2Name={draft.p2_name}
              />
            </div>

            <div className="draft-layout">
              <Sidebar playerName={draft.p1_name} picks={draft.p1_picks || []} side="p1" />
              <CardPool
                pool={draft.pool || []}
                onAction={doAction}
                rarityFilter={rarityFilter}
                setRarityFilter={setRarityFilter}
                sortMode={sortMode}
                setSortMode={setSortMode}
                elixirAsc={elixirAsc}
                setElixirAsc={setElixirAsc}
                search={search}
                setSearch={setSearch}
                aiThinking={aiThinking}
              />
              <Sidebar playerName={draft.p2_name} picks={draft.p2_picks || []} side="p2" />
            </div>

            {/* AI live chat log */}
            {draft.ai_mode && (
              <div id="ai-chat" style={{ display: 'block' }}>
                <div id="ai-chat-header">🤖 AI Reasoning</div>
                <div id="ai-chat-log">
                  {(!draft.ai_log || !draft.ai_log.length) ? (
                    <div style={{ color: 'var(--text-muted)', fontSize: '.8rem', padding: '.2rem .4rem' }}>
                      Waiting for AI…
                    </div>
                  ) : (
                    draft.ai_log.map((e, i) => {
                      const color  = e.player === 1 ? 'var(--p1)' : 'var(--p2)'
                      const action = e.phase === 'ban' ? '🚫 banned' : '✅ picked'
                      return (
                        <div className="ai-entry" key={i}>
                          <span className="ai-entry-name" style={{ color }}>{e.player_name}</span>
                          <span className="ai-entry-action">{action}</span>
                          <span className="ai-entry-card">{e.card}</span>
                          {e.reason && <span className="ai-entry-reason">— {e.reason}</span>}
                        </div>
                      )
                    })
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── DONE SCREEN ── */}
        {showDone && (
          <DoneScreen
            draft={draft}
            winnerInfo={winnerInfo}
            onDeclareWinner={declareWinner}
            onReset={resetDraft}
            onCopyLink={handleCopyLink}
            aiLogOpen={aiLogOpen}
            setAiLogOpen={setAiLogOpen}
          />
        )}

      </main>
    </>
  )
}
