import { useState } from 'react'
import { Plus, Star, Eye, Edit, Trash2, Filter } from 'lucide-react'
import Card from '@/components/Card'
import Button from '@/components/Button'
import { useEntries, useDeleteEntry } from '@/hooks/useEntries'
import { useLibraries } from '@/hooks/useLibraries'

export default function Entries() {
  const [selectedLibrary, setSelectedLibrary] = useState<string | undefined>()
  const [searchQuery, setSearchQuery] = useState('')
  const [showFavorites, setShowFavorites] = useState(false)

  const { data: libraries } = useLibraries()
  const { data: entries, isLoading } = useEntries({
    library_id: selectedLibrary,
    search: searchQuery || undefined,
    favorite: showFavorites || undefined,
    limit: 50,
  })
  const deleteEntry = useDeleteEntry()

  const handleDelete = async (uuid: string) => {
    if (confirm('Are you sure you want to delete this entry?')) {
      await deleteEntry.mutateAsync(uuid)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            Media Entries
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            Browse and manage your media collection
          </p>
        </div>
        <Button>
          <Plus size={20} className="mr-2" />
          Add Entry
        </Button>
      </div>

      {/* Filters */}
      <Card padding="medium">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <Filter size={20} className="text-gray-600 dark:text-gray-400" />
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Filters:
            </span>
          </div>

          <select
            value={selectedLibrary || ''}
            onChange={(e) => setSelectedLibrary(e.target.value || undefined)}
            className="input-field max-w-xs"
          >
            <option value="">All Libraries</option>
            {libraries?.map((lib) => (
              <option key={lib.id} value={lib.id}>
                {lib.icon} {lib.name}
              </option>
            ))}
          </select>

          <input
            type="text"
            placeholder="Search..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input-field max-w-sm"
          />

          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={showFavorites}
              onChange={(e) => setShowFavorites(e.target.checked)}
              className="rounded"
            />
            <span className="text-sm text-gray-700 dark:text-gray-300">
              Favorites only
            </span>
          </label>
        </div>
      </Card>

      {/* Entries Grid */}
      {isLoading ? (
        <div className="text-center py-12">Loading entries...</div>
      ) : entries && entries.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {entries.map((entry) => (
            <Card key={entry.uuid} padding="none">
              {/* Thumbnail placeholder */}
              <div className="aspect-video bg-gray-200 dark:bg-gray-700 rounded-t-lg flex items-center justify-center">
                <Eye size={48} className="text-gray-400" />
              </div>

              <div className="p-4">
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-semibold text-gray-900 dark:text-white line-clamp-2">
                    {entry.title}
                  </h3>
                  {entry.favorite && (
                    <Star
                      size={16}
                      className="text-yellow-500 fill-yellow-500 flex-shrink-0 ml-2"
                    />
                  )}
                </div>

                <div className="space-y-1 text-sm text-gray-600 dark:text-gray-400">
                  {entry.platform && (
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-xs">
                        {entry.platform}
                      </span>
                    </div>
                  )}
                  <div className="flex items-center justify-between">
                    <span>{entry.view_count || 0} views</span>
                    {entry.rating && (
                      <span className="text-yellow-600">★ {entry.rating}/5</span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 mt-4">
                  <Button size="small" variant="ghost" className="flex-1">
                    <Edit size={16} className="mr-1" />
                    Edit
                  </Button>
                  <Button
                    size="small"
                    variant="danger"
                    onClick={() => handleDelete(entry.uuid)}
                  >
                    <Trash2 size={16} />
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card padding="large">
          <div className="text-center py-12">
            <Eye size={48} className="mx-auto text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              No entries found
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              Try adjusting your filters or add your first entry
            </p>
            <Button>
              <Plus size={20} className="mr-2" />
              Add Entry
            </Button>
          </div>
        </Card>
      )}
    </div>
  )
}
