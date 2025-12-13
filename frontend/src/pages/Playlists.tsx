import { Plus, ListVideo, Zap } from 'lucide-react'
import Card from '@/components/Card'
import Button from '@/components/Button'

export default function Playlists() {
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
        <Button>
          <Plus size={20} className="mr-2" />
          New Playlist
        </Button>
      </div>

      <Card padding="large">
        <div className="text-center py-12">
          <ListVideo size={48} className="mx-auto text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            No playlists yet
          </h3>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            Create static or dynamic playlists to organize your media
          </p>
          <div className="flex items-center justify-center gap-4">
            <Button>
              <Plus size={20} className="mr-2" />
              Static Playlist
            </Button>
            <Button variant="secondary">
              <Zap size={20} className="mr-2" />
              Dynamic Playlist
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}
