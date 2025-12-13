import { useState, useEffect } from 'react'
import Modal from './Modal'
import Input from './Input'
import Textarea from './Textarea'
import Toggle from './Toggle'
import Button from './Button'
import { Library, LibraryCreate, LibraryUpdate } from '@/types/library'

interface LibraryFormProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: LibraryCreate | LibraryUpdate) => Promise<void>
  library?: Library | null
  isLoading?: boolean
}

const LIBRARY_ICONS = ['🎬', '🎵', '📚', '🎮', '🖼️', '📺', '🎙️', '📹', '🎸', '🎨']

export default function LibraryForm({
  isOpen,
  onClose,
  onSubmit,
  library,
  isLoading = false,
}: LibraryFormProps) {
  const [formData, setFormData] = useState<LibraryCreate>({
    id: '',
    name: '',
    icon: '🎬',
    default_path: '',
    auto_organize: false,
    is_private: false,
  })

  const [errors, setErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    if (library) {
      setFormData({
        id: library.id,
        name: library.name,
        icon: library.icon || '🎬',
        default_path: library.default_path,
        auto_organize: library.auto_organize,
        is_private: library.is_private,
        path_template: library.path_template || undefined,
        llm_threshold: library.llm_threshold || undefined,
        watch_folders: library.watch_folders || undefined,
      })
    } else {
      setFormData({
        id: '',
        name: '',
        icon: '🎬',
        default_path: '',
        auto_organize: false,
        is_private: false,
      })
    }
    setErrors({})
  }, [library, isOpen])

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {}

    if (!formData.id.trim()) {
      newErrors.id = 'Library ID is required'
    } else if (!/^[a-z0-9_-]+$/.test(formData.id)) {
      newErrors.id = 'ID must contain only lowercase letters, numbers, hyphens and underscores'
    }

    if (!formData.name.trim()) {
      newErrors.name = 'Library name is required'
    }

    if (!formData.default_path.trim()) {
      newErrors.default_path = 'Default path is required'
    }

    if (formData.llm_threshold !== undefined) {
      const threshold = parseFloat(formData.llm_threshold.toString())
      if (isNaN(threshold) || threshold < 0 || threshold > 1) {
        newErrors.llm_threshold = 'Threshold must be between 0 and 1'
      }
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async () => {
    if (!validate()) return

    try {
      await onSubmit(formData)
      onClose()
    } catch (err) {
      console.error('Form submission error:', err)
    }
  }

  const handleChange = (field: keyof LibraryCreate, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
    if (errors[field]) {
      setErrors((prev) => {
        const newErrors = { ...prev }
        delete newErrors[field]
        return newErrors
      })
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={library ? 'Edit Library' : 'Create Library'}
      size="large"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} isLoading={isLoading}>
            {library ? 'Save Changes' : 'Create Library'}
          </Button>
        </>
      }
    >
      <div className="space-y-6">
        {/* Basic Info */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Basic Information
          </h3>

          <Input
            label="Library ID"
            value={formData.id}
            onChange={(e) => handleChange('id', e.target.value)}
            error={errors.id}
            placeholder="movies"
            helperText="Unique identifier (lowercase, no spaces)"
            required
            disabled={!!library}
          />

          <Input
            label="Library Name"
            value={formData.name}
            onChange={(e) => handleChange('name', e.target.value)}
            error={errors.name}
            placeholder="Movies"
            required
          />

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Icon
            </label>
            <div className="flex gap-2 flex-wrap">
              {LIBRARY_ICONS.map((icon) => (
                <button
                  key={icon}
                  type="button"
                  onClick={() => handleChange('icon', icon)}
                  className={`text-3xl p-2 rounded-lg border-2 transition-colors ${
                    formData.icon === icon
                      ? 'border-primary-600 bg-primary-50 dark:bg-primary-900/20'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                  }`}
                >
                  {icon}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Storage Settings */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Storage Settings
          </h3>

          <Input
            label="Default Path"
            value={formData.default_path}
            onChange={(e) => handleChange('default_path', e.target.value)}
            error={errors.default_path}
            placeholder="/home/user/Videos/Movies"
            helperText="Base directory where files will be stored"
            required
          />

          <Toggle
            label="Auto-organize"
            helperText="Automatically organize files using path template"
            checked={formData.auto_organize}
            onChange={() => handleChange('auto_organize', !formData.auto_organize)}
          />

          {formData.auto_organize && (
            <Input
              label="Path Template"
              value={formData.path_template || ''}
              onChange={(e) => handleChange('path_template', e.target.value)}
              placeholder="{genre}/{artist}/{album}/{track:02d} - {title}.{ext}"
              helperText="Template for organizing files. Variables: {genre}, {artist}, {album}, {title}, {track}, {ext}"
            />
          )}
        </div>

        {/* AI Settings */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            AI Classification
          </h3>

          <Input
            label="LLM Confidence Threshold"
            type="number"
            step="0.1"
            min="0"
            max="1"
            value={formData.llm_threshold?.toString() || '0.7'}
            onChange={(e) => handleChange('llm_threshold', parseFloat(e.target.value))}
            error={errors.llm_threshold}
            placeholder="0.7"
            helperText="Minimum confidence (0-1) for automatic import. Lower values go to inbox."
          />
        </div>

        {/* Privacy */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Privacy
          </h3>

          <Toggle
            label="Private Library"
            helperText="Exclude from global searches and LLM suggestions"
            checked={formData.is_private}
            onChange={() => handleChange('is_private', !formData.is_private)}
          />
        </div>

        {/* Watch Folders */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Watch Folders (Optional)
          </h3>

          <Textarea
            label="Watch Folders"
            value={
              Array.isArray(formData.watch_folders)
                ? formData.watch_folders.join('\n')
                : formData.watch_folders || ''
            }
            onChange={(e) =>
              handleChange(
                'watch_folders',
                e.target.value.split('\n').filter((f) => f.trim())
              )
            }
            placeholder="/home/user/Downloads&#10;/home/user/Desktop"
            helperText="One folder per line. Files in these folders will be automatically imported."
            rows={4}
          />
        </div>
      </div>
    </Modal>
  )
}
