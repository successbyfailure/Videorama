import { NavLink } from 'react-router-dom'
import {
  Home,
  Library,
  Film,
  Download,
  Inbox,
  ListVideo,
  Settings,
} from 'lucide-react'

const navItems = [
  { to: '/', icon: Home, label: 'Dashboard' },
  { to: '/libraries', icon: Library, label: 'Libraries' },
  { to: '/entries', icon: Film, label: 'Entries' },
  { to: '/import', icon: Download, label: 'Import' },
  { to: '/inbox', icon: Inbox, label: 'Inbox' },
  { to: '/playlists', icon: ListVideo, label: 'Playlists' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function Sidebar() {
  return (
    <aside className="w-64 bg-white dark:bg-gray-800 shadow-lg">
      <div className="flex flex-col h-full">
        {/* Logo */}
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <h1 className="text-2xl font-bold text-gray-800 dark:text-white">
            Videorama
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">v2.0.0</p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-2">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                  isActive
                    ? 'bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300'
                    : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`
              }
            >
              <Icon size={20} />
              <span className="font-medium">{label}</span>
            </NavLink>
          ))}
        </nav>
      </div>
    </aside>
  )
}
