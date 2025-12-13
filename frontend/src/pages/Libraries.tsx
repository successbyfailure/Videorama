import { useState } from 'react'
import { Plus, Edit, Trash2, Library as LibraryIcon } from 'lucide-react'
import Card from '@/components/Card'
import Button from '@/components/Button'
import LibraryForm from '@/components/LibraryForm'
import {
  useLibraries,
  useDeleteLibrary,
  useCreateLibrary,
  useUpdateLibrary,
} from '@/hooks/useLibraries'
import { Library, LibraryCreate, LibraryUpdate } from '@/types/library'

export default function Libraries() {
  const { data: libraries, isLoading } = useLibraries(true) // Include private
  const deleteLibrary = useDeleteLibrary()
  const createLibrary = useCreateLibrary()
  const updateLibrary = useUpdateLibrary()

  const [isFormOpen, setIsFormOpen] = useState(false)
  const [selectedLibrary, setSelectedLibrary] = useState<Library | null>(null)

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this library?')) {
      await deleteLibrary.mutateAsync(id)
    }
  }

  const handleCreate = () => {
    setSelectedLibrary(null)
    setIsFormOpen(true)
  }

  const handleEdit = (library: Library) => {
    setSelectedLibrary(library)
    setIsFormOpen(true)
  }

  const handleSubmit = async (data: LibraryCreate | LibraryUpdate) => {
    if (selectedLibrary) {
      await updateLibrary.mutateAsync({
        id: selectedLibrary.id,
        updates: data as LibraryUpdate,
      })
    } else {
      await createLibrary.mutateAsync(data as LibraryCreate)
    }
    setIsFormOpen(false)
    setSelectedLibrary(null)
  }

  if (isLoading) {
    return <div>Loading libraries...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            Libraries
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            Manage your media libraries
          </p>
        </div>
        <Button onClick={handleCreate}>
          <Plus size={20} className="mr-2" />
          New Library
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {libraries && libraries.length > 0 ? (
          libraries.map((library) => (
            <Card key={library.id} padding="medium">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-4xl">{library.icon}</span>
                  <div>
                    <h3 className="font-semibold text-gray-900 dark:text-white">
                      {library.name}
                    </h3>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      {library.id}
                    </p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleEdit(library)}
                    className="p-2 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
                  >
                    <Edit size={16} />
                  </button>
                  <button
                    onClick={() => handleDelete(library.id)}
                    className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>

              <div className="mt-4 space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400">
                    Entries:
                  </span>
                  <span className="font-medium text-gray-900 dark:text-white">
                    {library.entry_count || 0}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400">
                    Auto-organize:
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      library.auto_organize
                        ? 'bg-green-100 text-green-700'
                        : 'bg-gray-100 text-gray-700'
                    }`}
                  >
                    {library.auto_organize ? 'On' : 'Off'}
                  </span>
                </div>
                {library.is_private && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600 dark:text-gray-400">
                      Visibility:
                    </span>
                    <span className="px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-700">
                      Private
                    </span>
                  </div>
                )}
                {library.path_template && (
                  <div className="mt-2 p-2 bg-gray-50 dark:bg-gray-700 rounded text-xs font-mono text-gray-700 dark:text-gray-300 break-all">
                    {library.path_template}
                  </div>
                )}
              </div>
            </Card>
          ))
        ) : (
          <div className="col-span-full">
            <Card padding="large">
              <div className="text-center py-12">
                <LibraryIcon size={48} className="mx-auto text-gray-400 mb-4" />
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                  No libraries yet
                </h3>
                <p className="text-gray-600 dark:text-gray-400 mb-6">
                  Create your first library to start organizing media
                </p>
                <Button onClick={handleCreate}>
                  <Plus size={20} className="mr-2" />
                  Create Library
                </Button>
              </div>
            </Card>
          </div>
        )}
      </div>

      <LibraryForm
        isOpen={isFormOpen}
        onClose={() => {
          setIsFormOpen(false)
          setSelectedLibrary(null)
        }}
        onSubmit={handleSubmit}
        library={selectedLibrary}
        isLoading={createLibrary.isPending || updateLibrary.isPending}
      />
    </div>
  )
}
