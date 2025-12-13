import { Library, Film, Inbox as InboxIcon, TrendingUp } from 'lucide-react'
import Card from '@/components/Card'
import { useLibraries } from '@/hooks/useLibraries'
import { useEntries } from '@/hooks/useEntries'
import { useInboxItems } from '@/hooks/useInbox'
import { useJobs } from '@/hooks/useJobs'

export default function Dashboard() {
  const { data: libraries } = useLibraries()
  const { data: entries } = useEntries({ limit: 10 })
  const { data: inboxItems } = useInboxItems({ reviewed: false })
  const { data: jobs } = useJobs({ status: 'running' })

  const stats = [
    {
      label: 'Total Libraries',
      value: libraries?.length || 0,
      icon: Library,
      color: 'text-blue-600',
      bgColor: 'bg-blue-100',
    },
    {
      label: 'Total Entries',
      value: entries?.length || 0,
      icon: Film,
      color: 'text-green-600',
      bgColor: 'bg-green-100',
    },
    {
      label: 'Inbox Items',
      value: inboxItems?.length || 0,
      icon: InboxIcon,
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-100',
    },
    {
      label: 'Active Jobs',
      value: jobs?.length || 0,
      icon: TrendingUp,
      color: 'text-purple-600',
      bgColor: 'bg-purple-100',
    },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Dashboard
        </h1>
        <p className="text-gray-600 dark:text-gray-400 mt-2">
          Welcome to Videorama v2.0
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat) => (
          <Card key={stat.label} padding="medium">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  {stat.label}
                </p>
                <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">
                  {stat.value}
                </p>
              </div>
              <div className={`p-3 rounded-lg ${stat.bgColor}`}>
                <stat.icon className={stat.color} size={24} />
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Entries */}
        <Card>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
            Recent Entries
          </h2>
          {entries && entries.length > 0 ? (
            <div className="space-y-3">
              {entries.slice(0, 5).map((entry) => (
                <div
                  key={entry.uuid}
                  className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg"
                >
                  <div className="flex-1">
                    <p className="font-medium text-gray-900 dark:text-white">
                      {entry.title}
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      {entry.platform || 'Unknown platform'}
                    </p>
                  </div>
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    {new Date(entry.added_at * 1000).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 dark:text-gray-400">No entries yet</p>
          )}
        </Card>

        {/* Libraries Overview */}
        <Card>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
            Libraries
          </h2>
          {libraries && libraries.length > 0 ? (
            <div className="space-y-3">
              {libraries.map((library) => (
                <div
                  key={library.id}
                  className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">{library.icon}</span>
                    <div>
                      <p className="font-medium text-gray-900 dark:text-white">
                        {library.name}
                      </p>
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        {library.entry_count || 0} entries
                      </p>
                    </div>
                  </div>
                  {library.is_private && (
                    <span className="px-2 py-1 text-xs font-medium bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300 rounded">
                      Private
                    </span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 dark:text-gray-400">
              No libraries configured
            </p>
          )}
        </Card>
      </div>
    </div>
  )
}
