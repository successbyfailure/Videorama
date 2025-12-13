import { useState } from 'react'
import Card from '@/components/Card'
import Button from '@/components/Button'
import Input from '@/components/Input'
import Toggle from '@/components/Toggle'
import { useSettings, useUpdateSettings } from '@/hooks/useSettings'
import { Settings as SettingsIcon, Save, AlertCircle, CheckCircle } from 'lucide-react'

export default function Settings() {
  const { data: settings, isLoading, error } = useSettings()
  const updateSettings = useUpdateSettings()

  const [formData, setFormData] = useState<Record<string, any>>({})
  const [showSuccess, setShowSuccess] = useState(false)

  const handleChange = (field: string, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
  }

  const handleSave = async () => {
    try {
      await updateSettings.mutateAsync(formData)
      setShowSuccess(true)
      setFormData({})
      setTimeout(() => setShowSuccess(false), 3000)
    } catch (err) {
      console.error('Failed to update settings:', err)
    }
  }

  const hasChanges = Object.keys(formData).length > 0

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-600 dark:text-red-400">
          Failed to load settings. Please try again.
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            Settings
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            Configure your Videorama instance
          </p>
        </div>

        {showSuccess && (
          <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
            <CheckCircle className="w-5 h-5" />
            <span>Settings saved! Restart the app to apply changes.</span>
          </div>
        )}
      </div>

      {hasChanges && (
        <Card padding="medium">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-orange-600 dark:text-orange-400">
              <AlertCircle className="w-5 h-5" />
              <span>You have unsaved changes</span>
            </div>
            <div className="flex gap-2">
              <Button
                variant="ghost"
                onClick={() => setFormData({})}
                disabled={updateSettings.isPending}
              >
                Discard
              </Button>
              <Button
                onClick={handleSave}
                isLoading={updateSettings.isPending}
              >
                <Save className="w-4 h-4 mr-2" />
                Save Changes
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* General Settings */}
      <Card padding="medium">
        <div className="flex items-center gap-3 mb-6">
          <SettingsIcon className="w-6 h-6 text-primary-600" />
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            General Settings
          </h2>
        </div>

        <div className="space-y-4">
          <Input
            label="Application Name"
            value={formData.app_name ?? settings?.app_name ?? ''}
            onChange={(e) => handleChange('app_name', e.target.value)}
            placeholder="Videorama"
          />

          <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
            <div>
              <p className="font-medium text-gray-900 dark:text-white">Version</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Current version of Videorama
              </p>
            </div>
            <span className="text-gray-900 dark:text-white font-mono">
              {settings?.version}
            </span>
          </div>

          <Toggle
            label="Debug Mode"
            helperText="Enable verbose logging for development"
            checked={formData.debug ?? settings?.debug ?? false}
            onChange={() => handleChange('debug', !(formData.debug ?? settings?.debug))}
          />

          <Input
            label="Storage Base Path"
            value={formData.storage_base_path ?? settings?.storage_base_path ?? ''}
            onChange={(e) => handleChange('storage_base_path', e.target.value)}
            placeholder="/home/user/Videorama/storage"
            helperText="Base directory for storing media files"
          />
        </div>
      </Card>

      {/* VHS Integration */}
      <Card padding="medium">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
          VHS Integration
        </h2>

        <div className="space-y-4">
          <Input
            label="VHS Base URL"
            value={formData.vhs_base_url ?? settings?.vhs_base_url ?? ''}
            onChange={(e) => handleChange('vhs_base_url', e.target.value)}
            placeholder="http://localhost:8001"
            helperText="URL of your VHS download server"
          />

          <Input
            label="VHS Timeout (seconds)"
            type="number"
            value={formData.vhs_timeout ?? settings?.vhs_timeout ?? 60}
            onChange={(e) => handleChange('vhs_timeout', parseInt(e.target.value))}
            placeholder="60"
            helperText="Timeout for VHS API requests"
          />
        </div>
      </Card>

      {/* LLM Configuration */}
      <Card padding="medium">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
          AI / LLM Configuration
        </h2>

        <div className="space-y-4">
          <Input
            label="OpenAI API Key"
            type="password"
            value={formData.openai_api_key ?? settings?.openai_api_key ?? ''}
            onChange={(e) => handleChange('openai_api_key', e.target.value)}
            placeholder="sk-..."
            helperText="API key for OpenAI or compatible service"
          />

          <Input
            label="OpenAI Base URL"
            value={formData.openai_base_url ?? settings?.openai_base_url ?? ''}
            onChange={(e) => handleChange('openai_base_url', e.target.value)}
            placeholder="https://api.openai.com/v1"
            helperText="Base URL for OpenAI-compatible API"
          />

          <Input
            label="Model"
            value={formData.openai_model ?? settings?.openai_model ?? ''}
            onChange={(e) => handleChange('openai_model', e.target.value)}
            placeholder="gpt-4o"
            helperText="Model to use for classification and metadata extraction"
          />
        </div>
      </Card>

      {/* External APIs */}
      <Card padding="medium">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
          External APIs
        </h2>

        <div className="space-y-4">
          <Input
            label="TMDb API Key"
            type="password"
            value={formData.tmdb_api_key ?? settings?.tmdb_api_key ?? ''}
            onChange={(e) => handleChange('tmdb_api_key', e.target.value)}
            placeholder="Your TMDb API key"
            helperText="For movie and TV show metadata enrichment"
          />

          <Input
            label="Spotify Client ID"
            type="password"
            value={formData.spotify_client_id ?? settings?.spotify_client_id ?? ''}
            onChange={(e) => handleChange('spotify_client_id', e.target.value)}
            placeholder="Your Spotify Client ID"
            helperText="For music metadata enrichment"
          />

          <Input
            label="Spotify Client Secret"
            type="password"
            value={formData.spotify_client_secret ?? settings?.spotify_client_secret ?? ''}
            onChange={(e) => handleChange('spotify_client_secret', e.target.value)}
            placeholder="Your Spotify Client Secret"
          />
        </div>
      </Card>

      {/* Telegram Integration */}
      <Card padding="medium">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
          Telegram Integration
        </h2>

        <div className="space-y-4">
          <Input
            label="Bot Token"
            type="password"
            value={formData.telegram_bot_token ?? settings?.telegram_bot_token ?? ''}
            onChange={(e) => handleChange('telegram_bot_token', e.target.value)}
            placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
            helperText="Token for Telegram bot integration"
          />
        </div>
      </Card>

      {/* Save Button at Bottom */}
      {hasChanges && (
        <div className="flex justify-end gap-2 sticky bottom-4">
          <Button
            variant="secondary"
            onClick={() => setFormData({})}
            disabled={updateSettings.isPending}
          >
            Discard Changes
          </Button>
          <Button
            onClick={handleSave}
            isLoading={updateSettings.isPending}
            size="large"
          >
            <Save className="w-5 h-5 mr-2" />
            Save All Changes
          </Button>
        </div>
      )}
    </div>
  )
}
