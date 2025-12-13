import { useState } from 'react'
import {
  Plus,
  Tag as TagIcon,
  Edit,
  Trash2,
  Search,
  GitMerge,
  X,
} from 'lucide-react'
import Card from '@/components/Card'
import Button from '@/components/Button'
import Input from '@/components/Input'
import TagForm from '@/components/TagForm'
import Modal from '@/components/Modal'
import { useToast } from '@/contexts/ToastContext'
import {
  useTags,
  useCreateTag,
  useUpdateTag,
  useDeleteTag,
  useMergeTags,
} from '@/hooks/useTags'
import type { Tag } from '@/types'

export default function Tags() {
  const toast = useToast()
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [editingTag, setEditingTag] = useState<Tag | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedTags, setSelectedTags] = useState<number[]>([])
  const [isMergeMode, setIsMergeMode] = useState(false)
  const [mergeTarget, setMergeTarget] = useState<number | null>(null)
  const [isMergeModalOpen, setIsMergeModalOpen] = useState(false)

  const { data: tags, isLoading } = useTags({
    search: searchQuery || undefined,
    limit: 500,
  })
  const createTag = useCreateTag()
  const updateTag = useUpdateTag()
  const deleteTag = useDeleteTag()
  const mergeTags = useMergeTags()

  const handleCreate = () => {
    setEditingTag(null)
    setIsFormOpen(true)
  }

  const handleEdit = (tag: Tag) => {
    setEditingTag(tag)
    setIsFormOpen(true)
  }

  const handleDelete = async (id: number, tagName: string) => {
    if (
      confirm(
        `Are you sure you want to delete "${tagName}"? This will remove it from all entries.`
      )
    ) {
      try {
        await deleteTag.mutateAsync(id)
        toast.success(`Tag "${tagName}" deleted successfully`)
      } catch (error: any) {
        toast.error(error?.response?.data?.detail || 'Failed to delete tag')
      }
    }
  }

  const handleSubmit = async (data: any) => {
    try {
      if (editingTag) {
        await updateTag.mutateAsync({
          id: editingTag.id,
          updates: data,
        })
        toast.success(`Tag "${data.name}" updated successfully`)
      } else {
        await createTag.mutateAsync(data)
        toast.success(`Tag "${data.name}" created successfully`)
      }
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || 'Failed to save tag')
      throw error
    }
  }

  const toggleTagSelection = (tagId: number) => {
    setSelectedTags((prev) =>
      prev.includes(tagId)
        ? prev.filter((id) => id !== tagId)
        : [...prev, tagId]
    )
  }

  const handleStartMerge = () => {
    if (selectedTags.length < 2) {
      toast.warning('Please select at least 2 tags to merge')
      return
    }
    setIsMergeMode(true)
    setIsMergeModalOpen(true)
  }

  const handleMerge = async () => {
    if (!mergeTarget || selectedTags.length < 1) return

    // Remove target from source tags if selected
    const sourceTags = selectedTags.filter((id) => id !== mergeTarget)

    if (sourceTags.length === 0) {
      toast.warning('Please select at least one tag to merge into the target')
      return
    }

    try {
      const targetTag = tags?.find((t) => t.id === mergeTarget)
      await mergeTags.mutateAsync({
        source_tag_ids: sourceTags,
        target_tag_id: mergeTarget,
      })

      toast.success(`Successfully merged ${sourceTags.length} tag(s) into "${targetTag?.name}"`)
      setSelectedTags([])
      setMergeTarget(null)
      setIsMergeMode(false)
      setIsMergeModalOpen(false)
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || 'Failed to merge tags')
    }
  }

  const cancelMerge = () => {
    setIsMergeMode(false)
    setIsMergeModalOpen(false)
    setMergeTarget(null)
  }

  const getTagHierarchy = (tag: Tag) => {
    if (!tag.parent_id) return tag.name

    const parent = tags?.find((t) => t.id === tag.parent_id)
    if (!parent) return tag.name

    return `${parent.name} > ${tag.name}`
  }

  const selectedTagObjects = tags?.filter((tag) =>
    selectedTags.includes(tag.id)
  )
  const targetTagObject = tags?.find((tag) => tag.id === mergeTarget)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            Tags
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            Organize and manage your content tags
          </p>
        </div>
        <div className="flex items-center gap-3">
          {selectedTags.length > 0 && (
            <>
              <Button variant="secondary" onClick={handleStartMerge}>
                <GitMerge size={20} className="mr-2" />
                Merge ({selectedTags.length})
              </Button>
              <Button
                variant="ghost"
                onClick={() => setSelectedTags([])}
                size="small"
              >
                Clear Selection
              </Button>
            </>
          )}
          <Button onClick={handleCreate}>
            <Plus size={20} className="mr-2" />
            New Tag
          </Button>
        </div>
      </div>

      {/* Search */}
      <Card padding="medium">
        <div className="flex items-center gap-2">
          <Search size={20} className="text-gray-400" />
          <input
            type="text"
            placeholder="Search tags..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1 px-3 py-2 border-none bg-transparent text-gray-900 dark:text-white focus:outline-none"
          />
        </div>
      </Card>

      {/* Tags List */}
      {isLoading ? (
        <div className="text-center py-12">Loading tags...</div>
      ) : tags && tags.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {tags.map((tag) => (
            <Card
              key={tag.id}
              padding="medium"
              className={`transition-all ${
                selectedTags.includes(tag.id)
                  ? 'ring-2 ring-blue-500 bg-blue-50 dark:bg-blue-900/20'
                  : 'hover:shadow-lg'
              }`}
              onClick={() => isMergeMode && toggleTagSelection(tag.id)}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  {isMergeMode && (
                    <input
                      type="checkbox"
                      checked={selectedTags.includes(tag.id)}
                      onChange={() => toggleTagSelection(tag.id)}
                      className="rounded"
                    />
                  )}
                  <TagIcon
                    size={18}
                    className="text-gray-400 flex-shrink-0"
                  />
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-gray-900 dark:text-white truncate">
                      {tag.name}
                    </h3>
                    {tag.parent_id && (
                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                        {getTagHierarchy(tag)}
                      </p>
                    )}
                  </div>
                </div>
                <span className="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-700 rounded text-gray-600 dark:text-gray-400 flex-shrink-0">
                  {tag.usage_count}
                </span>
              </div>

              {!isMergeMode && (
                <div className="flex items-center gap-2 pt-3 border-t border-gray-200 dark:border-gray-700">
                  <Button
                    size="small"
                    variant="ghost"
                    className="flex-1"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleEdit(tag)
                    }}
                  >
                    <Edit size={14} className="mr-1" />
                    Edit
                  </Button>
                  <Button
                    size="small"
                    variant="danger"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDelete(tag.id, tag.name)
                    }}
                  >
                    <Trash2 size={14} />
                  </Button>
                </div>
              )}
            </Card>
          ))}
        </div>
      ) : (
        <Card padding="large">
          <div className="text-center py-12">
            <TagIcon size={48} className="mx-auto text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              {searchQuery ? 'No tags found' : 'No tags yet'}
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              {searchQuery
                ? 'Try a different search term'
                : 'Create tags to organize your media entries'}
            </p>
            {!searchQuery && (
              <Button onClick={handleCreate}>
                <Plus size={20} className="mr-2" />
                Create First Tag
              </Button>
            )}
          </div>
        </Card>
      )}

      {/* Tag Form Modal */}
      <TagForm
        tag={editingTag}
        isOpen={isFormOpen}
        onClose={() => {
          setIsFormOpen(false)
          setEditingTag(null)
        }}
        onSubmit={handleSubmit}
      />

      {/* Merge Modal */}
      <Modal
        isOpen={isMergeModalOpen}
        onClose={cancelMerge}
        title="Merge Tags"
        size="medium"
        footer={
          <div className="flex items-center justify-between w-full">
            <div>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                All entries will be retagged to the target
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Button variant="ghost" onClick={cancelMerge}>
                Cancel
              </Button>
              <Button onClick={handleMerge} disabled={!mergeTarget}>
                Merge Tags
              </Button>
            </div>
          </div>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Source Tags (will be deleted)
            </label>
            <div className="flex flex-wrap gap-2">
              {selectedTagObjects?.map((tag) => (
                <span
                  key={tag.id}
                  className="inline-flex items-center gap-1 px-3 py-1 bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-200 rounded-full text-sm"
                >
                  {tag.name}
                  <span className="text-xs opacity-75">
                    ({tag.usage_count})
                  </span>
                  <button
                    onClick={() => toggleTagSelection(tag.id)}
                    className="ml-1 hover:text-red-900 dark:hover:text-red-100"
                  >
                    <X size={14} />
                  </button>
                </span>
              ))}
            </div>
            {selectedTagObjects && selectedTagObjects.length === 0 && (
              <p className="text-sm text-gray-500 dark:text-gray-400 italic">
                No tags selected
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Target Tag (keep this one)
            </label>
            <select
              value={mergeTarget?.toString() || ''}
              onChange={(e) =>
                setMergeTarget(e.target.value ? parseInt(e.target.value) : null)
              }
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            >
              <option value="">Select target tag...</option>
              {tags?.map((tag) => (
                <option key={tag.id} value={tag.id}>
                  {tag.name} ({tag.usage_count} entries)
                </option>
              ))}
            </select>
            {targetTagObject && (
              <div className="mt-2">
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200 rounded-full text-sm">
                  {targetTagObject.name}
                  <span className="text-xs opacity-75">
                    ({targetTagObject.usage_count})
                  </span>
                </span>
              </div>
            )}
          </div>

          {mergeTarget && selectedTagObjects && selectedTagObjects.length > 0 && (
            <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
              <p className="text-sm text-blue-900 dark:text-blue-100">
                <strong>Result:</strong> All entries tagged with{' '}
                {selectedTagObjects
                  .filter((t) => t.id !== mergeTarget)
                  .map((t) => `"${t.name}"`)
                  .join(', ')}{' '}
                will be retagged to "{targetTagObject?.name}". Source tags will
                be deleted.
              </p>
            </div>
          )}
        </div>
      </Modal>
    </div>
  )
}
