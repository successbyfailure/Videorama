import Card from '@/components/Card'

export default function Settings() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Settings
        </h1>
        <p className="text-gray-600 dark:text-gray-400 mt-2">
          Configure your Videorama instance
        </p>
      </div>

      <Card padding="medium">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
          General Settings
        </h2>
        <p className="text-gray-600 dark:text-gray-400">
          Settings page coming soon...
        </p>
      </Card>
    </div>
  )
}
