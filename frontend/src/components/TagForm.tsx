import { useState, useEffect } from 'react'
import Modal from './Modal'
import Input from './Input'
import Select from './Select'
import Button from './Button'
import { useTags } from '@/hooks/useTags'
import type { Tag, TagCreate, TagUpdate } from '@/types'

interface TagFormProps {
  tag?: Tag | null
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: TagCreate | TagUpdate) => Promise<void>
}

export default function TagForm({
  tag,
  isOpen,
  onClose,
  onSubmit,
}: TagFormProps) {
  const { data: allTags } = useTags()
  const isEdit = !!tag

  const [name, setName] = useState('')
  const [parentId, setParentId] = useState<number | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Load tag data for editing
  useEffect(() => {
    if (tag) {
      setName(tag.name)
      setParentId(tag.parent_id)
    } else {
      setName('')
      setParentId(null)
    }
    setErrors({})
  }, [tag, isOpen])

  const validate = () => {
    const newErrors: Record<string, string> = {}

    if (!name.trim()) {
      newErrors.name = 'Name is required'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!validate()) return

    setIsSubmitting(true)

    try {
      const data: TagCreate | TagUpdate = {
        name: name.trim(),
        parent_id: parentId || null,
      }

      await onSubmit(data)
      onClose()
    } catch (error: any) {
      console.error('Failed to save tag:', error)
      setErrors({
        submit:
          error?.response?.data?.detail ||
          'Failed to save tag. Please try again.',
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  // Filter out current tag and its children from parent selection
  const availableParents = allTags?.filter((t) => {
    if (isEdit && tag) {
      // Can't be its own parent
      if (t.id === tag.id) return false
      // Can't select a child as parent (would create circular reference)
      if (t.parent_id === tag.id) return false
    }
    return true
  })

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEdit ? 'Edit Tag' : 'Create Tag'}
      size="small"
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
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Tag Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          error={errors.name}
          required
          placeholder="e.g., rock, comedy, 2024"
          autoFocus
        />

        <Select
          label="Parent Tag (optional)"
          value={parentId?.toString() || ''}
          onChange={(e) =>
            setParentId(e.target.value ? parseInt(e.target.value) : null)
          }
          helperText="Create hierarchical tags like Music > Rock > Classic Rock"
        >
          <option value="">None (Top Level)</option>
          {availableParents?.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
              {t.usage_count > 0 && ` (${t.usage_count} entries)`}
            </option>
          ))}
        </Select>
      </form>
    </Modal>
  )
}
