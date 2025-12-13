import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Libraries from './pages/Libraries'
import Entries from './pages/Entries'
import Inbox from './pages/Inbox'
import Playlists from './pages/Playlists'
import Tags from './pages/Tags'
import Settings from './pages/Settings'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="libraries" element={<Libraries />} />
        <Route path="entries" element={<Entries />} />
        <Route path="inbox" element={<Inbox />} />
        <Route path="playlists" element={<Playlists />} />
        <Route path="tags" element={<Tags />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}

export default App
