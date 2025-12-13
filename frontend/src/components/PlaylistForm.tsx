import { useState, useEffect } from 'react'
import { X, Plus, Trash2 } from 'lucide-react'
import Modal from './Modal'
import Input from './Input'
import Textarea from './Textarea'
import Select from './Select'
import Toggle from './Toggle'
import Button from './Button'
import { useLibraries } from '@/hooks/useLibraries'
import type { Playlist, PlaylistCreate, PlaylistUpdate } from '@/types'

interface PlaylistFormProps {
  playlist?: Playlist | null
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: PlaylistCreate | PlaylistUpdate) => Promise<void>
}

interface DynamicQuery {
  library_id?: string
  platform?: string
  favorite?: boolean
  tags?: string[]
  tags_any?: string[]
  properties?: Record<string, string>
  search?: string
  min_rating?: number
  max_rating?: number
  sort_by?: 'added_at' | 'title' | 'rating' | 'view_count' | 'random'
  sort_order?: 'asc' | 'desc'
  limit?: number
}

export default function PlaylistForm({
  playlist,
  isOpen,
  onClose,
  onSubmit,
}: PlaylistFormProps) {
  const { data: libraries } = useLibraries()
  const isEdit = !!playlist

  // Form state
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [libraryId, setLibraryId] = useState<string>('')
  const [isDynamic, setIsDynamic] = useState(false)
  const [query, setQuery] = useState<DynamicQuery>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Tags input
  const [tagsInput, setTagsInput] = useState('')
  const [tagsAnyInput, setTagsAnyInput] = useState('')

  // Properties input
  const [propertyKey, setPropertyKey] = useState('')
  const [propertyValue, setPropertyValue] = useState('')

  // Load playlist data for editing
  useEffect(() => {
    if (playlist) {
      setName(playlist.name)
      setDescription(playlist.description || '')
      setLibraryId(playlist.library_id || '')
      setIsDynamic(playlist.is_dynamic)

      if (playlist.is_dynamic && playlist.dynamic_query) {
        try {
          const parsedQuery = JSON.parse(playlist.dynamic_query)
          setQuery(parsedQuery)

          // Load tags
          if (parsedQuery.tags) {
            setTagsInput(parsedQuery.tags.join(', '))
          }
          if (parsedQuery.tags_any) {
            setTagsAnyInput(parsedQuery.tags_any.join(', '))
          }
        } catch (e) {
          console.error('Failed to parse query:', e)
        }
      }
    } else {
      // Reset form
      setName('')
      setDescription('')
      setLibraryId('')
      setIsDynamic(false)
      setQuery({})
      setTagsInput('')
      setTagsAnyInput('')
      setPropertyKey('')
      setPropertyValue('')
    }
    setErrors({})
  }, [playlist, isOpen])

  const validate = () => {
    const newErrors: Record<string, string> = {}

    if (!name.trim()) {
      newErrors.name = 'Name is required'
    }

    if (isDynamic) {
      // Dynamic playlists don't need library_id if querying globally
    } else {
      // Static playlists should have a library
      if (!libraryId) {
        newErrors.library_id = 'Library is required for static playlists'
      }
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!validate()) return

    setIsSubmitting(true)

    try {
      const data: PlaylistCreate | PlaylistUpdate = {
        name: name.trim(),
        description: description.trim() || null,
      }

      if (!isEdit) {
        // Create mode
        ;(data as PlaylistCreate).library_id = libraryId || null
        ;(data as PlaylistCreate).is_dynamic = isDynamic
      }

      if (isDynamic) {
        const dynamicQuery: DynamicQuery = {}

        if (query.library_id) dynamicQuery.library_id = query.library_id
        if (query.platform) dynamicQuery.platform = query.platform
        if (query.favorite !== undefined) dynamicQuery.favorite = query.favorite
        if (query.search) dynamicQuery.search = query.search
        if (query.min_rating !== undefined)
          dynamicQuery.min_rating = query.min_rating
        if (query.max_rating !== undefined)
          dynamicQuery.max_rating = query.max_rating
        if (query.sort_by) dynamicQuery.sort_by = query.sort_by
        if (query.sort_order) dynamicQuery.sort_order = query.sort_order
        if (query.limit !== undefined) dynamicQuery.limit = query.limit

        // Parse tags
        if (tagsInput.trim()) {
          dynamicQuery.tags = tagsInput
            .split(',')
            .map((t) => t.trim())
            .filter((t) => t)
        }
        if (tagsAnyInput.trim()) {
          dynamicQuery.tags_any = tagsAnyInput
            .split(',')
            .map((t) => t.trim())
            .filter((t) => t)
        }

        // Properties
        if (query.properties && Object.keys(query.properties).length > 0) {
          dynamicQuery.properties = query.properties
        }

        data.dynamic_query = JSON.stringify(dynamicQuery)
      }

      await onSubmit(data)
      onClose()
    } catch (error) {
      console.error('Failed to save playlist:', error)
      setErrors({
        submit: 'Failed to save playlist. Please try again.',
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  const updateQuery = (updates: Partial<DynamicQuery>) => {
    setQuery((prev) => ({ ...prev, ...updates }))
  }

  const addProperty = () => {
    if (propertyKey.trim() && propertyValue.trim()) {
      updateQuery({
        properties: {
          ...(query.properties || {}),
          [propertyKey.trim()]: propertyValue.trim(),
        },
      })
      setPropertyKey('')
      setPropertyValue('')
    }
  }

  const removeProperty = (key: string) => {
    const newProperties = { ...(query.properties || {}) }
    delete newProperties[key]
    updateQuery({ properties: newProperties })
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Edit Playlist' : 'Create Playlist'}
      size="large"
      footer={
        <div className="flex items-center justify-between w-full">
          <div>
            {errors.submit && (
              <span className="text-sm text-red-600 dark:text-red-400">
                {errors.submit}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <Button variant="ghost" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={isSubmitting}>
              {isSubmitting ? 'Saving...' : isEdit ? 'Update' : 'Create'}
            </Button>
          </div>
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic Info */}
        <div className="space-y-4">
          <Input
            label="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            error={errors.name}
            required
            placeholder="My Playlist"
          />

          <Textarea
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe this playlist..."
            rows={2}
          />

          {!isEdit && (
            <>
              <Select
                label="Library"
                value={libraryId}
                onChange={(e) => setLibraryId(e.target.value)}
                error={errors.library_id}
                required={!isDynamic}
              >
                <option value="">All Libraries</option>
                {libraries?.map((lib) => (
                  <option key={lib.id} value={lib.id}>
                    {lib.icon} {lib.name}
                  </option>
                ))}
              </Select>

              <Toggle
                label="Dynamic Playlist"
                helperText="Automatically updates based on query rules"
                checked={isDynamic}
                onChange={(e) => setIsDynamic(e.target.checked)}
              />
            </>
          )}
        </div>

        {/* Query Builder - only for dynamic playlists */}
        {isDynamic && (
          <div className="space-y-4 border-t border-gray-200 dark:border-gray-700 pt-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Query Rules
            </h3>

            {/* Library filter for dynamic playlists */}
            <Select
              label="Filter by Library"
              value={query.library_id || ''}
              onChange={(e) =>
                updateQuery({
                  library_id: e.target.value || undefined,
                })
              }
            >
              <option value="">All Libraries</option>
              {libraries?.map((lib) => (
                <option key={lib.id} value={lib.id}>
                  {lib.icon} {lib.name}
                </option>
              ))}
            </Select>

            {/* Platform filter */}
            <Input
              label="Platform"
              value={query.platform || ''}
              onChange={(e) =>
                updateQuery({ platform: e.target.value || undefined })
              }
              placeholder="youtube, spotify, etc."
            />

            {/* Search query */}
            <Input
              label="Search Keywords"
              value={query.search || ''}
              onChange={(e) =>
                updateQuery({ search: e.target.value || undefined })
              }
              placeholder="Search in title, description..."
            />

            {/* Favorites filter */}
            <Toggle
              label="Favorites Only"
              checked={query.favorite || false}
              onChange={(e) => updateQuery({ favorite: e.target.checked })}
            />

            {/* Tags (ALL) */}
            <div>
              <Input
                label="Required Tags (must have ALL)"
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                placeholder="comedy, 2023, action (comma-separated)"
                helperText="Entries must have all these tags"
              />
            </div>

            {/* Tags (ANY) */}
            <div>
              <Input
                label="Optional Tags (must have ANY)"
                value={tagsAnyInput}
                onChange={(e) => setTagsAnyInput(e.target.value)}
                placeholder="thriller, horror, sci-fi (comma-separated)"
                helperText="Entries must have at least one of these tags"
              />
            </div>

            {/* Properties */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Properties Filter
              </label>

              {query.properties && Object.keys(query.properties).length > 0 && (
                <div className="space-y-2 mb-3">
                  {Object.entries(query.properties).map(([key, value]) => (
                    <div
                      key={key}
                      className="flex items-center gap-2 p-2 bg-gray-50 dark:bg-gray-700 rounded"
                    >
                      <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                        {key}:
                      </span>
                      <span className="text-sm text-gray-600 dark:text-gray-400">
                        {value}
                      </span>
                      <button
                        type="button"
                        onClick={() => removeProperty(key)}
                        className="ml-auto text-red-600 hover:text-red-700 dark:text-red-400"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex items-end gap-2">
                <Input
                  label="Key"
                  value={propertyKey}
                  onChange={(e) => setPropertyKey(e.target.value)}
                  placeholder="genre"
                  className="flex-1"
                />
                <Input
                  label="Value"
                  value={propertyValue}
                  onChange={(e) => setPropertyValue(e.target.value)}
                  placeholder="Action"
                  className="flex-1"
                />
                <Button
                  type="button"
                  variant="secondary"
                  onClick={addProperty}
                  disabled={!propertyKey.trim() || !propertyValue.trim()}
                >
                  <Plus size={16} className="mr-1" />
                  Add
                </Button>
              </div>
            </div>

            {/* Rating range */}
            <div className="grid grid-cols-2 gap-4">
              <Input
                label="Min Rating"
                type="number"
                min="0"
                max="5"
                step="0.1"
                value={query.min_rating ?? ''}
                onChange={(e) =>
                  updateQuery({
                    min_rating: e.target.value
                      ? parseFloat(e.target.value)
                      : undefined,
                  })
                }
                placeholder="0.0"
              />
              <Input
                label="Max Rating"
                type="number"
                min="0"
                max="5"
                step="0.1"
                value={query.max_rating ?? ''}
                onChange={(e) =>
                  updateQuery({
                    max_rating: e.target.value
                      ? parseFloat(e.target.value)
                      : undefined,
                  })
                }
                placeholder="5.0"
              />
            </div>

            {/* Sorting */}
            <div className="grid grid-cols-2 gap-4">
              <Select
                label="Sort By"
                value={query.sort_by || ''}
                onChange={(e) =>
                  updateQuery({
                    sort_by: (e.target.value as any) || undefined,
                  })
                }
              >
                <option value="">Default</option>
                <option value="added_at">Date Added</option>
                <option value="title">Title</option>
                <option value="rating">Rating</option>
                <option value="view_count">View Count</option>
                <option value="random">Random</option>
              </Select>

              <Select
                label="Order"
                value={query.sort_order || 'desc'}
                onChange={(e) =>
                  updateQuery({
                    sort_order: (e.target.value as any) || 'desc',
                  })
                }
                disabled={!query.sort_by}
              >
                <option value="asc">Ascending</option>
                <option value="desc">Descending</option>
              </Select>
            </div>

            {/* Limit */}
            <Input
              label="Limit"
              type="number"
              min="1"
              max="1000"
              value={query.limit ?? ''}
              onChange={(e) =>
                updateQuery({
                  limit: e.target.value ? parseInt(e.target.value) : undefined,
                })
              }
              placeholder="50"
              helperText="Maximum number of entries to include"
            />
          </div>
        )}
      </form>
    </Modal>
  )
}
