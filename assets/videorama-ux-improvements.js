/**
 * Videorama UX Improvements
 *
 * Mejoras de experiencia de usuario:
 * - Infinite scroll para la biblioteca
 * - Hero colapsable
 * - Integration con sistema de jobs
 */

(function() {
  'use strict';

  // ============================================================================
  // Hero Colapsable
  // ============================================================================

  function initCollapsibleHero() {
    const heroMeta = document.querySelector('.library-meta');
    if (!heroMeta) return;

    // Crear botón para colapsar/expandir
    const toggleButton = document.createElement('button');
    toggleButton.type = 'button';
    toggleButton.className = 'hero-toggle-btn';
    toggleButton.innerHTML = '▼ Mostrar menos';
    toggleButton.style.cssText = `
      background: rgba(99, 102, 241, 0.15);
      border: 1px solid rgba(99, 102, 241, 0.3);
      color: #e2e8f0;
      padding: 0.5rem 1rem;
      border-radius: 999px;
      cursor: pointer;
      font-size: 0.85rem;
      font-weight: 600;
      margin-top: 0.75rem;
      transition: all 0.2s ease;
    `;

    toggleButton.addEventListener('mouseenter', () => {
      toggleButton.style.background = 'rgba(99, 102, 241, 0.25)';
    });

    toggleButton.addEventListener('mouseleave', () => {
      toggleButton.style.background = 'rgba(99, 102, 241, 0.15)';
    });

    // Estado colapsado por defecto
    let isCollapsed = true;
    heroMeta.style.display = 'none';

    toggleButton.addEventListener('click', () => {
      isCollapsed = !isCollapsed;
      heroMeta.style.display = isCollapsed ? 'none' : 'block';
      toggleButton.innerHTML = isCollapsed ? '▼ Mostrar estadísticas' : '▲ Ocultar estadísticas';
    });

    // Insertar botón después del hero-switch
    const heroSwitch = document.querySelector('.hero-switch');
    if (heroSwitch && heroSwitch.parentElement) {
      heroSwitch.parentElement.appendChild(toggleButton);
    }
  }

  // ============================================================================
  // Infinite Scroll
  // ============================================================================

  let infiniteScroller = null;

  function initInfiniteScroll() {
    // Verificar que VideoramaAsync esté disponible
    if (typeof window.VideoramaAsync === 'undefined') {
      console.warn('VideoramaAsync no está disponible. Infinite scroll deshabilitado.');
      return;
    }

    const libraryGrid = document.getElementById('library-grid');
    if (!libraryGrid) {
      console.warn('library-grid no encontrado. Infinite scroll deshabilitado.');
      return;
    }

    // Deshabilitar la carga inicial completa
    // La biblioteca ahora se cargará progresivamente

    infiniteScroller = new window.VideoramaAsync.InfiniteScrollLibrary({
      container: libraryGrid,
      limit: 30,
      library: window.libraryState?.activeLibrary || null,
      onLoad: (items, data) => {
        // Actualizar totales
        if (data.totals && window.libraryState) {
          window.libraryState.totals = data.totals;
          if (typeof window.updateLibraryHeader === 'function') {
            window.updateLibraryHeader();
          }
        }

        // Añadir items al estado
        if (window.libraryState) {
          // Solo añadir items nuevos (evitar duplicados)
          const existingIds = new Set(window.libraryState.entries.map(e => e.id));
          const newItems = items.filter(item => !existingIds.has(item.id));
          window.libraryState.entries.push(...newItems);
        }

        // Renderizar las nuevas tarjetas
        items.forEach(entry => {
          if (typeof window.renderVideoCard === 'function') {
            window.renderVideoCard(entry);
          }
        });

        // Aplicar filtros si existe la función
        if (typeof window.applyFilters === 'function') {
          window.applyFilters();
        }
      }
    });

    // Iniciar la carga
    infiniteScroller.loadMore();
  }

  function resetInfiniteScroll(newLibrary) {
    if (infiniteScroller) {
      infiniteScroller.reset(newLibrary);
      infiniteScroller.loadMore();
    }
  }

  // Exponer funciones globalmente para que puedan ser usadas desde el HTML principal
  window.resetInfiniteScroll = resetInfiniteScroll;

  // ============================================================================
  // Integración con Sistema de Jobs
  // ============================================================================

  function setupJobMonitoring() {
    // Interceptar los formularios de importación para usar el sistema de jobs
    const importForm = document.getElementById('import-form');
    if (importForm) {
      const originalSubmit = importForm.onsubmit;

      importForm.onsubmit = async function(event) {
        event.preventDefault();

        const formData = new FormData(importForm);
        const url = formData.get('url');
        const autoDownload = formData.get('auto_download') === 'on';
        const library = window.libraryState?.activeLibrary || 'video';

        if (!url) {
          window.VideoramaAsync.toast.show('Por favor, introduce una URL', 'error');
          return false;
        }

        try {
          // Enviar a la API
          const response = await fetch('/api/library', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
              url: url,
              auto_download: autoDownload,
              library: library
            })
          });

          if (!response.ok) {
            throw new Error('Error al añadir el video');
          }

          const data = await response.json();

          if (data.job_id && window.VideoramaAsync) {
            // Mostrar toast y progress indicator
            window.VideoramaAsync.toast.show('Video añadido a la cola de procesamiento', 'info');
            window.VideoramaAsync.progressIndicator.show('Procesando video...', 0);

            // Iniciar polling del job
            window.VideoramaAsync.jobPoller.poll(
              data.job_id,
              (progress, message) => {
                // Actualizar indicador de progreso
                window.VideoramaAsync.progressIndicator.update(message, progress);
              },
              (result) => {
                // Job completado
                window.VideoramaAsync.progressIndicator.hide();
                window.VideoramaAsync.toast.show('¡Video añadido correctamente!', 'success');

                // Añadir el video a la biblioteca
                if (result && result.id && window.libraryState) {
                  window.libraryState.entries.unshift(result);

                  // Re-renderizar
                  if (typeof window.applyFilters === 'function') {
                    window.applyFilters();
                  }

                  // Abrir el player si la función existe
                  if (typeof window.openPlayer === 'function') {
                    window.openPlayer(result);
                  }
                }

                // Limpiar formulario
                importForm.reset();
              },
              (error) => {
                // Job falló
                window.VideoramaAsync.progressIndicator.hide();
                window.VideoramaAsync.toast.show(`Error: ${error}`, 'error');
              }
            );
          } else {
            // Fallback para modo legacy
            window.VideoramaAsync.toast.show('Video añadido correctamente', 'success');
          }

        } catch (error) {
          window.VideoramaAsync.toast.show(error.message, 'error');
        }

        return false;
      };
    }
  }

  // ============================================================================
  // Inicialización
  // ============================================================================

  function init() {
    // Esperar a que el DOM esté listo
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => {
        setTimeout(init, 100);
      });
      return;
    }

    // Inicializar mejoras
    initCollapsibleHero();

    // Esperar un poco más para el infinite scroll (para que libraryState esté disponible)
    setTimeout(() => {
      initInfiniteScroll();
      setupJobMonitoring();
    }, 500);
  }

  init();
})();
