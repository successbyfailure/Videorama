import { useState } from 'react'
import { Plus, ListVideo, Zap, Edit, Trash2, List, Filter } from 'lucide-react'
import Card from '@/components/Card'
import Button from '@/components/Button'
import PlaylistForm from '@/components/PlaylistForm'
import { useToast } from '@/contexts/ToastContext'
import {
  usePlaylists,
  useCreatePlaylist,
  useUpdatePlaylist,
  useDeletePlaylist,
} from '@/hooks/usePlaylists'
import { useLibraries } from '@/hooks/useLibraries'
import type { Playlist } from '@/types'

export default function Playlists() {
  const toast = useToast()
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [editingPlaylist, setEditingPlaylist] = useState<Playlist | null>(null)
  const [filterLibrary, setFilterLibrary] = useState<string>('')
  const [filterType, setFilterType] = useState<string>('')

  const { data: libraries } = useLibraries()
  const { data: playlists, isLoading } = usePlaylists({
    library_id: filterLibrary || undefined,
    is_dynamic: filterType === 'dynamic' ? true : filterType === 'static' ? false : undefined,
  })
  const createPlaylist = useCreatePlaylist()
  const updatePlaylist = useUpdatePlaylist()
  const deletePlaylist = useDeletePlaylist()

  const handleCreate = () => {
    setEditingPlaylist(null)
    setIsFormOpen(true)
  }

  const handleEdit = (playlist: Playlist) => {
    setEditingPlaylist(playlist)
    setIsFormOpen(true)
  }

  const handleDelete = async (id: string, name: string) => {
    if (confirm('Are you sure you want to delete this playlist?')) {
      try {
        await deletePlaylist.mutateAsync(id)
        toast.success(`Playlist "${name}" deleted successfully`)
      } catch (error: any) {
        toast.error(error?.response?.data?.detail || 'Failed to delete playlist')
      }
    }
  }

  const handleSubmit = async (data: any) => {
    try {
      if (editingPlaylist) {
        await updatePlaylist.mutateAsync({
          id: editingPlaylist.id,
          updates: data,
        })
        toast.success(`Playlist "${data.name}" updated successfully`)
      } else {
        await createPlaylist.mutateAsync(data)
        toast.success(`Playlist "${data.name}" created successfully`)
      }
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || 'Failed to save playlist')
      throw error
    }
  }

  const getLibraryName = (libraryId: string | null) => {
    if (!libraryId) return 'All Libraries'
    const library = libraries?.find((lib) => lib.id === libraryId)
    return library ? `${library.icon} ${library.name}` : libraryId
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            Playlists
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            Organize your media into collections
          </p>
        </div>
        <Button onClick={handleCreate}>
          <Plus size={20} className="mr-2" />
          New Playlist
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
            value={filterLibrary}
            onChange={(e) => setFilterLibrary(e.target.value)}
            className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white max-w-xs"
          >
            <option value="">All Libraries</option>
            {libraries?.map((lib) => (
              <option key={lib.id} value={lib.id}>
                {lib.icon} {lib.name}
              </option>
            ))}
          </select>

          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
          >
            <option value="">All Types</option>
            <option value="static">Static</option>
            <option value="dynamic">Dynamic</option>
          </select>
        </div>
      </Card>

      {/* Playlists Grid */}
      {isLoading ? (
        <div className="text-center py-12">Loading playlists...</div>
      ) : playlists && playlists.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {playlists.map((playlist) => (
            <Card key={playlist.id} padding="medium" className="hover:shadow-lg transition-shadow">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-2">
                  {playlist.is_dynamic ? (
                    <Zap size={20} className="text-blue-500" />
                  ) : (
                    <List size={20} className="text-gray-500" />
                  )}
                  <h3 className="font-semibold text-gray-900 dark:text-white">
                    {playlist.name}
                  </h3>
                </div>
                <span className="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-700 rounded text-gray-600 dark:text-gray-400">
                  {playlist.is_dynamic ? 'Dynamic' : 'Static'}
                </span>
              </div>

              {playlist.description && (
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-4 line-clamp-2">
                  {playlist.description}
                </p>
              )}

              <div className="space-y-2 mb-4 text-sm text-gray-600 dark:text-gray-400">
                <div className="flex items-center justify-between">
                  <span>Library:</span>
                  <span className="font-medium">{getLibraryName(playlist.library_id)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Entries:</span>
                  <span className="font-medium">{playlist.entry_count || 0}</span>
                </div>
                {playlist.is_dynamic && playlist.dynamic_query && (
                  <div className="mt-2 p-2 bg-blue-50 dark:bg-blue-900/20 rounded text-xs">
                    <span className="font-medium text-blue-700 dark:text-blue-400">
                      Dynamic Query Active
                    </span>
                  </div>
                )}
              </div>

              <div className="flex items-center gap-2 pt-4 border-t border-gray-200 dark:border-gray-700">
                <Button
                  size="small"
                  variant="ghost"
                  className="flex-1"
                  onClick={() => handleEdit(playlist)}
                >
                  <Edit size={16} className="mr-1" />
                  Edit
                </Button>
                <Button
                  size="small"
                  variant="danger"
                  onClick={() => handleDelete(playlist.id, playlist.name)}
                >
                  <Trash2 size={16} />
                </Button>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card padding="large">
          <div className="text-center py-12">
            <ListVideo size={48} className="mx-auto text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              No playlists yet
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              Create static or dynamic playlists to organize your media
            </p>
            <Button onClick={handleCreate}>
              <Plus size={20} className="mr-2" />
              Create Playlist
            </Button>
          </div>
        </Card>
      )}

      {/* Playlist Form Modal */}
      <PlaylistForm
        playlist={editingPlaylist}
        isOpen={isFormOpen}
        onClose={() => {
          setIsFormOpen(false)
          setEditingPlaylist(null)
        }}
        onSubmit={handleSubmit}
      />
    </div>
  )
}
