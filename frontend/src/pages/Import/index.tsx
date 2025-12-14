import { useState } from 'react'
import { Download, Search } from 'lucide-react'
import Card from '@/components/Card'
import URLImport from './URLImport'
import SearchImport from './SearchImport'

export default function Import() {
  const [activeTab, setActiveTab] = useState<'url' | 'search'>('url')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Import Media</h1>
        <p className="text-gray-600 mt-2">
          Import videos and audio from URLs or search across platforms
        </p>
      </div>

      {/* Tabs */}
      <Card padding="none">
        <div className="border-b border-gray-200 px-6">
          <nav className="-mb-px flex space-x-8" aria-label="Tabs">
            <button
              onClick={() => setActiveTab('url')}
              className={`
                flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm
                ${
                  activeTab === 'url'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }
              `}
            >
              <Download className="w-5 h-5" />
              URL Import
            </button>
            <button
              onClick={() => setActiveTab('search')}
              className={`
                flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm
                ${
                  activeTab === 'search'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }
              `}
            >
              <Search className="w-5 h-5" />
              Search
            </button>
          </nav>
        </div>

        <div className="p-6">
          {activeTab === 'url' && <URLImport />}
          {activeTab === 'search' && <SearchImport />}
        </div>
      </Card>
    </div>
  )
}
