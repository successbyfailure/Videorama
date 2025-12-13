/**
 * Videorama Async Features
 *
 * Funcionalidades asíncronas mejoradas:
 * - Sistema de paginación/infinite scroll
 * - Toast notifications
 * - Job polling con indicadores de progreso
 */

// ============================================================================
// Toast Notifications
// ============================================================================

class ToastManager {
  constructor() {
    this.container = null;
    this.init();
  }

  init() {
    // Crear contenedor de toasts si no existe
    if (!document.getElementById('toast-container')) {
      this.container = document.createElement('div');
      this.container.id = 'toast-container';
      this.container.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 10000;
        display: flex;
        flex-direction: column;
        gap: 10px;
        max-width: 400px;
      `;
      document.body.appendChild(this.container);
    } else {
      this.container = document.getElementById('toast-container');
    }
  }

  show(message, type = 'info', duration = 5000) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.style.cssText = `
      background: ${this._getBackgroundColor(type)};
      color: white;
      padding: 16px 20px;
      border-radius: 12px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
      display: flex;
      align-items: center;
      gap: 12px;
      animation: slideIn 0.3s ease-out;
      border-left: 4px solid ${this._getBorderColor(type)};
    `;

    const icon = this._getIcon(type);
    const content = document.createElement('div');
    content.textContent = message;
    content.style.flex = '1';

    toast.appendChild(icon);
    toast.appendChild(content);

    this.container.appendChild(toast);

    // Auto-remove después de duration
    if (duration > 0) {
      setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-in';
        setTimeout(() => toast.remove(), 300);
      }, duration);
    }

    return toast;
  }

  _getBackgroundColor(type) {
    const colors = {
      success: '#10b981',
      error: '#ef4444',
      warning: '#f59e0b',
      info: '#3b82f6',
    };
    return colors[type] || colors.info;
  }

  _getBorderColor(type) {
    const colors = {
      success: '#059669',
      error: '#dc2626',
      warning: '#d97706',
      info: '#2563eb',
    };
    return colors[type] || colors.info;
  }

  _getIcon(type) {
    const icons = {
      success: '✓',
      error: '✕',
      warning: '⚠',
      info: 'ℹ',
    };
    const icon = document.createElement('div');
    icon.textContent = icons[type] || icons.info;
    icon.style.cssText = `
      width: 24px;
      height: 24px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.2);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: bold;
    `;
    return icon;
  }
}

// Instancia global
const toast = new ToastManager();

// Añadir estilos de animación
const style = document.createElement('style');
style.textContent = `
  @keyframes slideIn {
    from {
      transform: translateX(400px);
      opacity: 0;
    }
    to {
      transform: translateX(0);
      opacity: 1;
    }
  }
  @keyframes slideOut {
    from {
      transform: translateX(0);
      opacity: 1;
    }
    to {
      transform: translateX(400px);
      opacity: 0;
    }
  }
`;
document.head.appendChild(style);


// ============================================================================
// Job Polling
// ============================================================================

class JobPoller {
  constructor() {
    this.activeJobs = new Map();
    this.pollInterval = 2000; // 2 segundos
  }

  /**
   * Inicia el polling de un job.
   *
   * @param {string} jobId - ID del job
   * @param {function} onProgress - Callback para progreso (progress, message)
   * @param {function} onComplete - Callback para completar (result)
   * @param {function} onError - Callback para error (error)
   */
  poll(jobId, onProgress, onComplete, onError) {
    if (this.activeJobs.has(jobId)) {
      return; // Ya está siendo polleado
    }

    const intervalId = setInterval(async () => {
      try {
        const response = await fetch(`/api/jobs/${jobId}`);
        if (!response.ok) {
          clearInterval(intervalId);
          this.activeJobs.delete(jobId);
          onError?.('Job no encontrado');
          return;
        }

        const job = await response.json();

        // Actualizar progreso
        onProgress?.(job.progress, job.message);

        // Verificar si completó
        if (job.status === 'completed') {
          clearInterval(intervalId);
          this.activeJobs.delete(jobId);
          onComplete?.(job.result);
        } else if (job.status === 'failed') {
          clearInterval(intervalId);
          this.activeJobs.delete(jobId);
          onError?.(job.error || 'Job falló');
        }
      } catch (error) {
        clearInterval(intervalId);
        this.activeJobs.delete(jobId);
        onError?.(error.message);
      }
    }, this.pollInterval);

    this.activeJobs.set(jobId, intervalId);
  }

  stop(jobId) {
    const intervalId = this.activeJobs.get(jobId);
    if (intervalId) {
      clearInterval(intervalId);
      this.activeJobs.delete(jobId);
    }
  }

  stopAll() {
    for (const [jobId, intervalId] of this.activeJobs) {
      clearInterval(intervalId);
    }
    this.activeJobs.clear();
  }
}

// Instancia global
const jobPoller = new JobPoller();


// ============================================================================
// Progress Indicator
// ============================================================================

class ProgressIndicator {
  constructor() {
    this.container = null;
    this.progressBar = null;
    this.messageEl = null;
    this.init();
  }

  init() {
    // Crear contenedor de progreso
    this.container = document.createElement('div');
    this.container.id = 'progress-indicator';
    this.container.style.cssText = `
      position: fixed;
      bottom: 20px;
      left: 50%;
      transform: translateX(-50%);
      background: rgba(15, 23, 42, 0.95);
      border: 1px solid rgba(99, 102, 241, 0.4);
      border-radius: 12px;
      padding: 16px 24px;
      min-width: 300px;
      max-width: 500px;
      z-index: 9999;
      display: none;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
    `;

    this.messageEl = document.createElement('div');
    this.messageEl.style.cssText = `
      color: #e2e8f0;
      margin-bottom: 8px;
      font-size: 14px;
    `;

    const progressContainer = document.createElement('div');
    progressContainer.style.cssText = `
      width: 100%;
      height: 8px;
      background: rgba(30, 41, 59, 0.8);
      border-radius: 4px;
      overflow: hidden;
    `;

    this.progressBar = document.createElement('div');
    this.progressBar.style.cssText = `
      height: 100%;
      background: linear-gradient(90deg, #6366f1, #8b5cf6);
      border-radius: 4px;
      width: 0%;
      transition: width 0.3s ease;
    `;

    progressContainer.appendChild(this.progressBar);
    this.container.appendChild(this.messageEl);
    this.container.appendChild(progressContainer);
    document.body.appendChild(this.container);
  }

  show(message = 'Procesando...', progress = 0) {
    this.container.style.display = 'block';
    this.messageEl.textContent = message;
    this.progressBar.style.width = `${progress}%`;
  }

  update(message, progress) {
    if (message) this.messageEl.textContent = message;
    if (progress !== undefined) this.progressBar.style.width = `${progress}%`;
  }

  hide() {
    this.container.style.display = 'none';
  }
}

// Instancia global
const progressIndicator = new ProgressIndicator();


// ============================================================================
// Infinite Scroll Library
// ============================================================================

class InfiniteScrollLibrary {
  constructor(options = {}) {
    this.container = options.container || document.getElementById('library-grid');
    this.limit = options.limit || 20;
    this.offset = 0;
    this.loading = false;
    this.hasMore = true;
    this.currentLibrary = options.library || null;
    this.onLoad = options.onLoad || (() => {});
    this.init();
  }

  init() {
    // Observador de intersección para detectar scroll al final
    this.observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !this.loading && this.hasMore) {
          this.loadMore();
        }
      },
      { rootMargin: '200px' }
    );

    // Crear elemento centinela al final de la lista
    this.sentinel = document.createElement('div');
    this.sentinel.id = 'scroll-sentinel';
    this.sentinel.style.cssText = 'height: 1px; margin-top: 20px;';

    // Insertar después del container
    if (this.container && this.container.parentElement) {
      this.container.parentElement.insertBefore(this.sentinel, this.container.nextSibling);
      this.observer.observe(this.sentinel);
    }
  }

  async loadMore() {
    if (this.loading || !this.hasMore) return;

    this.loading = true;
    this.showLoader();

    try {
      const params = new URLSearchParams({
        limit: this.limit,
        offset: this.offset,
      });

      if (this.currentLibrary) {
        params.append('library', this.currentLibrary);
      }

      const response = await fetch(`/api/library?${params}`);
      if (!response.ok) throw new Error('Error al cargar biblioteca');

      const data = await response.json();

      // Callback con los nuevos items
      this.onLoad(data.items, data);

      // Actualizar estado
      this.offset += data.count;
      this.hasMore = data.has_more;

      if (!this.hasMore) {
        this.hideLoader();
        this.showEndMessage();
      }
    } catch (error) {
      console.error('Error cargando más items:', error);
      toast.show('Error al cargar más videos', 'error');
    } finally {
      this.loading = false;
      this.hideLoader();
    }
  }

  reset(library = null) {
    this.offset = 0;
    this.hasMore = true;
    this.currentLibrary = library;
    if (this.container) {
      this.container.innerHTML = '';
    }
    this.removeEndMessage();
  }

  showLoader() {
    if (document.getElementById('loading-indicator')) return;

    const loader = document.createElement('div');
    loader.id = 'loading-indicator';
    loader.style.cssText = `
      text-align: center;
      padding: 20px;
      color: #94a3b8;
    `;
    loader.innerHTML = '<div class="spinner"></div><p>Cargando más videos...</p>';

    if (this.sentinel && this.sentinel.parentElement) {
      this.sentinel.parentElement.insertBefore(loader, this.sentinel);
    }
  }

  hideLoader() {
    const loader = document.getElementById('loading-indicator');
    if (loader) loader.remove();
  }

  showEndMessage() {
    if (document.getElementById('end-message')) return;

    const message = document.createElement('div');
    message.id = 'end-message';
    message.style.cssText = `
      text-align: center;
      padding: 40px 20px;
      color: #64748b;
      font-size: 14px;
    `;
    message.textContent = '✓ No hay más videos para cargar';

    if (this.sentinel && this.sentinel.parentElement) {
      this.sentinel.parentElement.insertBefore(message, this.sentinel);
    }
  }

  removeEndMessage() {
    const message = document.getElementById('end-message');
    if (message) message.remove();
  }

  destroy() {
    if (this.observer) {
      this.observer.disconnect();
    }
    if (this.sentinel) {
      this.sentinel.remove();
    }
    this.hideLoader();
    this.removeEndMessage();
  }
}


// ============================================================================
// Exportar globalmente
// ============================================================================

window.VideoramaAsync = {
  toast,
  jobPoller,
  progressIndicator,
  InfiniteScrollLibrary,
};
