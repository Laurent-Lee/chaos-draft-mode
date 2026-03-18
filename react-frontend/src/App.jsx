import { BrowserRouter, Routes, Route } from 'react-router-dom'
import LandingPage from './pages/LandingPage'
import DraftPage from './pages/DraftPage'
import PlayerStatsPage from './pages/PlayerStatsPage'
import CardDetailPage from './pages/CardDetailPage'
import CardStatsPage from './pages/CardStatsPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"               element={<LandingPage />} />
        <Route path="/draft"          element={<DraftPage />} />
        <Route path="/player_stats"              element={<PlayerStatsPage />} />
        <Route path="/player_stats/:playerName" element={<PlayerStatsPage />} />
        <Route path="/card/:cardName" element={<CardDetailPage />} />
        <Route path="/stats"          element={<CardStatsPage />} />
      </Routes>
    </BrowserRouter>
  )
}
