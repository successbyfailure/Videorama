import { useState } from 'react'
import { Bell, Search, User } from 'lucide-react'
import { useJobs } from '@/hooks/useJobs'
import JobsPanel from './JobsPanel'
import Logo from '@/assets/LogoVideorama.png'

export default function Header() {
  const { data: jobs } = useJobs({ status: 'running' })
  const runningJobsCount = jobs?.length || 0
  const [showJobsPanel, setShowJobsPanel] = useState(false)

  return (
    <>
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between px-6 py-4 gap-4">
          {/* Brand */}
          <div className="flex items-center gap-3 flex-shrink-0">
            <img
              src={Logo}
              alt="Videorama logo"
              className="w-10 h-10 rounded-lg shadow-sm ring-1 ring-gray-200 dark:ring-gray-700 bg-white"
            />
            <div className="leading-tight">
              <p className="text-sm font-semibold text-gray-900 dark:text-white">
                Videorama
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Media Library Manager
              </p>
            </div>
          </div>

          {/* Search */}
          <div className="flex-1 max-w-xl">
            <div className="relative">
              <Search
                className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400"
                size={20}
              />
              <input
                type="text"
                placeholder="Search media..."
                className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-gray-700 dark:text-white"
              />
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-4 ml-4">
            {/* Job notifications */}
            {runningJobsCount > 0 && (
              <button
                onClick={() => setShowJobsPanel(true)}
                className="flex items-center gap-2 px-3 py-1.5 bg-blue-100 dark:bg-blue-900 rounded-full text-blue-700 dark:text-blue-300 text-sm font-medium hover:bg-blue-200 dark:hover:bg-blue-800 transition-colors"
              >
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                {runningJobsCount} {runningJobsCount === 1 ? 'job' : 'jobs'}{' '}
                running
              </button>
            )}

            {/* Notifications */}
            <button className="p-2 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg">
              <Bell size={20} />
            </button>

            {/* User menu */}
            <button className="flex items-center gap-2 p-2 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg">
              <User size={20} />
            </button>
          </div>
        </div>
      </header>

    {/* Jobs Panel */}
    <JobsPanel isOpen={showJobsPanel} onClose={() => setShowJobsPanel(false)} />
  </>
  )
}
