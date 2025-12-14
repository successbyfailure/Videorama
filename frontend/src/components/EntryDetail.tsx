import { useState } from 'react'
import Modal from './Modal'
import Button from './Button'
import Input from './Input'
import Textarea from './Textarea'
import { Entry } from '@/types/entry'
import {
  Play,
  Download,
  Edit2,
  Trash2,
  Tag,
  FileText,
  Heart,
  Clock,
  Film,
  Music,
  Image as ImageIcon,
  ExternalLink,
} from 'lucide-react'

interface EntryDetailProps {
  entry: Entry | null
  isOpen: boolean
  onClose: () => void
  onUpdate?: (uuid: string, updates: any) => Promise<void>
  onDelete?: (uuid: string) => Promise<void>
}

export default function EntryDetail({
  entry,
  isOpen,
  onClose,
  onUpdate,
  onDelete,
}: EntryDetailProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editData, setEditData] = useState<any>({})
  const [isPlaying, setIsPlaying] = useState(false)

  if (!entry) return null

  const handleEdit = () => {
    setEditData({
      title: entry.title,
      description: entry.description || '',
    })
    setIsEditing(true)
  }

  const handleSave = async () => {
    if (onUpdate) {
      await onUpdate(entry.uuid, editData)
    }
    setIsEditing(false)
  }

  const handleDelete = async () => {
    if (confirm('Are you sure you want to delete this entry?')) {
      if (onDelete) {
        await onDelete(entry.uuid)
      }
      onClose()
    }
  }

  const handleToggleFavorite = async () => {
    if (onUpdate) {
      await onUpdate(entry.uuid, { favorite: !entry.favorite })
    }
  }

  // Get file by type
  const videoFile = entry.files?.find((f: any) => f.file_type === 'video')
  const audioFile = entry.files?.find((f: any) => f.file_type === 'audio')
  const thumbnailFile = entry.files?.find((f: any) => f.file_type === 'thumbnail')

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={isEditing ? 'Edit Entry' : entry.title}
      size="xl"
      footer={
        isEditing ? (
          <>
            <Button variant="ghost" onClick={() => setIsEditing(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave}>Save Changes</Button>
          </>
        ) : (
          <>
            <Button variant="danger" onClick={handleDelete}>
              <Trash2 className="w-4 h-4 mr-2" />
              Delete
            </Button>
            <Button variant="secondary" onClick={handleEdit}>
              <Edit2 className="w-4 h-4 mr-2" />
              Edit
            </Button>
          </>
        )
      }
    >
      <div className="space-y-6">
        {/* Media Preview / Player */}
        {!isEditing && (
          <div className="aspect-video bg-gray-900 rounded-lg overflow-hidden relative">
            {isPlaying && (videoFile || audioFile) ? (
              // Video/Audio Player
              videoFile ? (
                <video
                  src={`/api/v1/entries/${entry.uuid}/stream`}
                  controls
                  autoPlay
                  className="w-full h-full"
                  onEnded={() => setIsPlaying(false)}
                  poster={entry.thumbnail_url || undefined}
                >
                  Your browser does not support the video tag.
                </video>
              ) : (
                <audio
                  src={`/api/v1/entries/${entry.uuid}/stream`}
                  controls
                  autoPlay
                  className="w-full"
                  onEnded={() => setIsPlaying(false)}
                >
                  Your browser does not support the audio tag.
                </audio>
              )
            ) : (
              // Thumbnail / Placeholder
              <>
                {thumbnailFile ? (
                  <img
                    src={`/static/${thumbnailFile.file_path}`}
                    alt={entry.title}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-gray-400">
                    {videoFile ? (
                      <Film className="w-16 h-16" />
                    ) : audioFile ? (
                      <Music className="w-16 h-16" />
                    ) : (
                      <ImageIcon className="w-16 h-16" />
                    )}
                  </div>
                )}

                {/* Play overlay */}
                {(videoFile || audioFile) && (
                  <div
                    className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-0 hover:bg-opacity-30 transition-all cursor-pointer"
                    onClick={() => setIsPlaying(true)}
                  >
                    <Play className="w-16 h-16 text-white opacity-70 hover:opacity-100 transition-opacity" />
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Editable Fields */}
        {isEditing ? (
          <div className="space-y-4">
            <Input
              label="Title"
              value={editData.title || ''}
              onChange={(e) =>
                setEditData({ ...editData, title: e.target.value })
              }
            />
            <Textarea
              label="Description"
              value={editData.description || ''}
              onChange={(e) =>
                setEditData({ ...editData, description: e.target.value })
              }
              rows={4}
            />
          </div>
        ) : (
          <>
            {/* Metadata */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">
                  Library
                </h3>
                <p className="text-gray-900 dark:text-white">
                  {entry.library_id}
                </p>
              </div>

              {entry.platform && (
                <div className="space-y-2">
                  <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">
                    Platform
                  </h3>
                  <p className="text-gray-900 dark:text-white">
                    {entry.platform}
                  </p>
                </div>
              )}

              <div className="space-y-2">
                <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 flex items-center gap-2">
                  <Clock className="w-4 h-4" />
                  Added
                </h3>
                <p className="text-gray-900 dark:text-white">
                  {new Date(entry.added_at * 1000).toLocaleDateString()}
                </p>
              </div>

              <div className="space-y-2">
                <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">
                  Views
                </h3>
                <p className="text-gray-900 dark:text-white">
                  {entry.view_count || 0}
                </p>
              </div>
            </div>

            {/* Description */}
            {entry.description && (
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 flex items-center gap-2">
                  <FileText className="w-4 h-4" />
                  Description
                </h3>
                <p className="text-gray-700 dark:text-gray-300">
                  {entry.description}
                </p>
              </div>
            )}

            {/* Files */}
            {entry.files && entry.files.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">
                  Files
                </h3>
                <div className="space-y-2">
                  {entry.files.map((file: any) => (
                    <div
                      key={file.id}
                      className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg"
                    >
                      <div className="flex items-center gap-3">
                        {file.file_type === 'video' && (
                          <Film className="w-5 h-5 text-primary-600" />
                        )}
                        {file.file_type === 'audio' && (
                          <Music className="w-5 h-5 text-primary-600" />
                        )}
                        {file.file_type === 'thumbnail' && (
                          <ImageIcon className="w-5 h-5 text-primary-600" />
                        )}
                        <div>
                          <p className="text-sm font-medium text-gray-900 dark:text-white">
                            {file.file_type} - {file.format}
                          </p>
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            {(file.size / 1024 / 1024).toFixed(2)} MB
                            {file.duration && ` • ${Math.floor(file.duration / 60)}:${String(Math.floor(file.duration % 60)).padStart(2, '0')}`}
                          </p>
                        </div>
                      </div>
                      <Button size="small" variant="ghost">
                        <Download className="w-4 h-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tags */}
            {(entry.user_tags || entry.auto_tags) && (
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 flex items-center gap-2">
                  <Tag className="w-4 h-4" />
                  Tags
                </h3>
                <div className="flex flex-wrap gap-2">
                  {entry.auto_tags?.map((tag: string) => (
                    <span
                      key={tag}
                      className="px-2 py-1 bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 rounded text-xs font-medium"
                    >
                      {tag}
                    </span>
                  ))}
                  {entry.user_tags?.map((tag: string) => (
                    <span
                      key={tag}
                      className="px-2 py-1 bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300 rounded text-xs font-medium"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Properties */}
            {entry.properties && Object.keys(entry.properties).length > 0 && (
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">
                  Properties
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  {Object.entries(entry.properties).map(([key, value]) => (
                    <div
                      key={key}
                      className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg"
                    >
                      <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                        {key}
                      </p>
                      <p className="text-sm text-gray-900 dark:text-white">
                        {String(value)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Original URL */}
            {entry.original_url && (
              <div className="space-y-2">
                <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">
                  Source
                </h3>
                <a
                  href={entry.original_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300"
                >
                  {entry.original_url}
                  <ExternalLink className="w-4 h-4" />
                </a>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-2 pt-4 border-t border-gray-200 dark:border-gray-700">
              <Button
                variant={entry.favorite ? 'primary' : 'ghost'}
                onClick={handleToggleFavorite}
                className="flex-1"
              >
                <Heart
                  className={`w-4 h-4 mr-2 ${entry.favorite ? 'fill-current' : ''}`}
                />
                {entry.favorite ? 'Favorited' : 'Add to Favorites'}
              </Button>
            </div>
          </>
        )}
      </div>
    </Modal>
  )
}
