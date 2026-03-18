import { BrowserRouter, Routes, Route } from 'react-router-dom'
import DraftPage from './pages/DraftPage'
import PlayerStatsPage from './pages/PlayerStatsPage'
import CardDetailPage from './pages/CardDetailPage'
import CardStatsPage from './pages/CardStatsPage'
import LandingPage from './pages/LandingPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"               element={<DraftPage />} />
        <Route path="/player_stats"   element={<PlayerStatsPage />} />
        <Route path="/card/:cardName" element={<CardDetailPage />} />
        <Route path="/stats"          element={<CardStatsPage />} />
        <Route path="/dashboard"      element={<LandingPage />} />
      </Routes>
    </BrowserRouter>
  )
}
