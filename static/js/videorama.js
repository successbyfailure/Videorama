      const DEFAULT_FORMAT = {{ default_format | tojson }};
      const suggestedTags = {{ popular_tags | tojson }};
      const libraryState = {
        entries: [],
        filtered: [],
        favorites: new Set(),
        categories: [],
        categoryStats: [],
        categorySettings: [],
        activeCategory: 'all',
        activePlaylistId: null,
        playlists: [],
        customPlaylists: [],
        search: '',
        activeLibrary: 'video',
        totals: { all: 0, video: 0, music: 0 },
      };
      const playbackPreferences = { musicMode: 'auto', autoNext: true, autoPick: true };
      const playerState = { currentEntry: null, nextEntryId: null };
      const playerElements = {};
      const librarySubtitle = document.getElementById('library-subtitle');
      const libraryCountLabel = document.getElementById('library-count-label');
      const libraryCountValue = document.getElementById('library-count-value');
      const libraryToggleButtons = document.querySelectorAll('[data-library-target]');
      const musicModeButtons = document.querySelectorAll('[data-music-mode]');
      const musicModeGroup = document.getElementById('music-mode-group');
      const autoNextToggle = document.getElementById('auto-next-toggle');
      const autoPickToggle = document.getElementById('auto-pick-toggle');
      const nextPicker = document.getElementById('next-picker');
      const nextEntrySelect = document.getElementById('next-entry-select');
      const playNextButton = document.getElementById('play-next-now');

      const STATIC_PLAYLISTS = [
        {
          id: 'recent',
          name: 'Últimos estrenos',
          description: 'Lo más nuevo añadido a la biblioteca.',
          category: 'static',
          source: 'system',
          resolve: (items) =>
            items
              .slice()
              .sort((a, b) => (b.added_at || 0) - (a.added_at || 0))
              .slice(0, 12),
        },
        {
          id: 'longform',
          name: 'Sesión de sofá',
          description: 'Vídeos de más de 15 minutos para maratones caseras.',
          category: 'static',
          source: 'system',
          resolve: (items) => items.filter((item) => (item.duration || 0) >= 900),
        },
        {
          id: 'clips',
          name: 'Clips exprés',
          description: 'Duración inferior a 3 minutos.',
          category: 'static',
          source: 'system',
          resolve: (items) => items.filter((item) => (item.duration || 0) > 0 && item.duration <= 180),
        },
        {
          id: 'random',
          name: 'Zapping retro',
          description: 'Selección aleatoria para descubrir joyas olvidadas.',
          category: 'static',
          source: 'system',
          resolve: (items) => shuffle(items).slice(0, 9),
        },
      ];

      document.addEventListener('DOMContentLoaded', init);

      async function init() {
        restoreFavorites();
        attachSearch();
        attachLibrarySwitch();
        attachPlaybackControls();
        attachMenuButtons();
        setupPlayerUI();
        setupManagerForms();
        try {
          await Promise.all([fetchLibrary(), fetchCustomPlaylists(), fetchCategorySettings()]);
          buildCategories();
          buildPlaylists();
          applyFilters();
          await openEntryFromUrl();
          renderPlaylistManager();
          renderCategoryManager();
        } catch (error) {
          showLibraryError(error.message);
        }
      }

      function fetchLibrary() {
        const params = new URLSearchParams();
        if (libraryState.activeLibrary) {
          params.set('library', libraryState.activeLibrary);
        }
        const url = params.toString() ? `/api/library?${params}` : '/api/library';
        return fetch(url)
          .then((response) => {
            if (!response.ok) {
              throw new Error('No se pudo cargar la biblioteca.');
            }
            return response.json();
          })
          .then((payload) => {
            libraryState.entries = Array.isArray(payload.items) ? payload.items : [];
            libraryState.totals = payload.totals || libraryState.totals;
            updateLibraryHeader();
          });
      }

      function fetchCustomPlaylists() {
        return fetch('/api/playlists')
          .then((response) => {
            if (!response.ok) {
              throw new Error('No se pudieron cargar las playlists personalizadas.');
            }
            return response.json();
          })
          .then((payload) => {
            libraryState.customPlaylists = Array.isArray(payload.items) ? payload.items : [];
          });
      }

      function fetchCategorySettings() {
        return fetch('/api/category-settings')
          .then((response) => {
            if (!response.ok) {
              throw new Error('No se pudieron cargar las categorías personalizadas.');
            }
            return response.json();
          })
          .then((payload) => {
            libraryState.categorySettings = Array.isArray(payload.settings) ? payload.settings : [];
          });
      }

      function attachLibrarySwitch() {
        setActiveLibraryButton();
        libraryToggleButtons.forEach((button) => {
          button.addEventListener('click', () => switchLibrary(button.dataset.libraryTarget));
        });
      }

      function attachPlaybackControls() {
        if (autoNextToggle) {
          autoNextToggle.addEventListener('change', () => {
            playbackPreferences.autoNext = autoNextToggle.checked;
            updatePlaybackControls();
          });
        }
        if (autoPickToggle) {
          autoPickToggle.addEventListener('change', () => {
            playbackPreferences.autoPick = autoPickToggle.checked;
            updatePlaybackControls();
          });
        }
        musicModeButtons.forEach((button) => {
          button.addEventListener('click', () => {
            playbackPreferences.musicMode = button.dataset.musicMode || 'audio';
            updatePlaybackControls();
            if (playerState.currentEntry && playerState.currentEntry.library === 'music') {
              openPlayer(playerState.currentEntry);
            }
          });
        });
        if (nextEntrySelect) {
          nextEntrySelect.addEventListener('change', () => {
            playerState.nextEntryId = nextEntrySelect.value || null;
          });
        }
        if (playNextButton) {
          playNextButton.addEventListener('click', () => playNextEntry(true));
        }
        updatePlaybackControls();
      }

      function setActiveLibraryButton() {
        libraryToggleButtons.forEach((button) => {
          const isActive = button.dataset.libraryTarget === libraryState.activeLibrary;
          button.classList.toggle('active', isActive);
          button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        });
        updateLibraryHeader();
        updatePlaybackControls();
      }

      async function switchLibrary(target) {
        const normalized = (target || '').toLowerCase();
        if (!normalized || normalized === libraryState.activeLibrary) {
          return;
        }
        libraryState.activeLibrary = normalized;
        libraryState.activeCategory = 'all';
        libraryState.activePlaylistId = null;
        stopPlayer();
        setActiveLibraryButton();
        try {
          await fetchLibrary();
          buildCategories();
          buildPlaylists();
          applyFilters();
        } catch (error) {
          showLibraryError(error.message);
        }
      }

      function updatePlaybackControls() {
        const isMusicLibrary = libraryState.activeLibrary === 'music';
        if (!isMusicLibrary && playbackPreferences.musicMode === 'audio') {
          playbackPreferences.musicMode = 'auto';
        }
        if (musicModeGroup) {
          musicModeGroup.hidden = !isMusicLibrary;
        }
        musicModeButtons.forEach((button) => {
          const active = button.dataset.musicMode === playbackPreferences.musicMode;
          button.classList.toggle('active', active);
          button.disabled = !isMusicLibrary;
          button.setAttribute('aria-disabled', button.disabled ? 'true' : 'false');
        });
        if (autoNextToggle) {
          autoNextToggle.checked = playbackPreferences.autoNext;
        }
        if (autoPickToggle) {
          autoPickToggle.checked = playbackPreferences.autoPick;
        }
        renderNextOptions();
      }

      function updateLibraryHeader() {
        const pretty = libraryState.activeLibrary === 'music' ? 'música' : 'video';
        const total = libraryState.totals[libraryState.activeLibrary] ?? libraryState.entries.length;
        if (librarySubtitle) {
          librarySubtitle.textContent = `Explorando la biblioteca de ${pretty}.`;
        }
        if (libraryCountLabel) {
          libraryCountLabel.textContent = total;
        }
        if (libraryCountValue) {
          libraryCountValue.textContent = new Intl.NumberFormat('es-ES').format(total);
        }
      }

      function showLibraryError(message) {
        const grid = document.getElementById('library-grid');
        grid.innerHTML = `<p class="empty-state">${message}</p>`;
      }

      function restoreFavorites() {
        try {
          const raw = localStorage.getItem('videorama:favorites');
          if (raw) {
            const parsed = JSON.parse(raw);
            if (Array.isArray(parsed)) {
              libraryState.favorites = new Set(parsed);
            }
          }
        } catch (error) {
          console.warn('No se pudieron restaurar favoritos', error);
        }
        updateFavoriteCounter();
      }

      function persistFavorites() {
        localStorage.setItem('videorama:favorites', JSON.stringify([...libraryState.favorites]));
        updateFavoriteCounter();
        buildCategories();
      }

      function updateFavoriteCounter() {
        const counter = document.getElementById('favorite-count');
        counter.textContent = libraryState.favorites.size;
      }

      function attachSearch() {
        const searchInput = document.getElementById('search');
        searchInput.addEventListener('input', (event) => {
          libraryState.search = event.target.value.toLowerCase();
          applyFilters();
        });
      }

      function attachMenuButtons() {
        document.querySelectorAll('[data-open-modal]').forEach((button) => {
          button.addEventListener('click', () => openModal(button.getAttribute('data-open-modal')));
        });
        document.querySelectorAll('[data-close-modal]').forEach((button) => {
          button.addEventListener('click', () => closeModal(button.closest('.modal')));
        });
        document.querySelectorAll('.modal').forEach((modal) => {
          modal.addEventListener('click', (event) => {
            if (event.target === modal) {
              closeModal(modal);
            }
          });
        });
        document.addEventListener('keydown', (event) => {
          if (event.key === 'Escape') {
            document.querySelectorAll('.modal.open').forEach((modal) => closeModal(modal));
          }
        });
      }

      function setupPlayerUI() {
        playerElements.modal = document.getElementById('player-panel');
        playerElements.placeholder = document.getElementById('player-placeholder');
        if (!playerElements.modal) {
          return;
        }
        playerElements.video = document.getElementById('player-video');
        playerElements.title = document.getElementById('player-title');
        playerElements.uploader = document.getElementById('player-uploader');
        playerElements.category = document.getElementById('player-category');
        playerElements.duration = document.getElementById('player-duration');
        playerElements.notes = document.getElementById('player-notes');
        playerElements.notesHeading = document.getElementById('player-notes-heading');
        playerElements.tags = document.getElementById('player-tags');
        playerElements.editForm = document.getElementById('player-edit-form');
        playerElements.editTitle = document.getElementById('edit-title');
        playerElements.editCategory = document.getElementById('edit-category');
        playerElements.editTags = document.getElementById('edit-tags');
        playerElements.tagSuggestions = document.getElementById('tag-suggestions');
        playerElements.autoTagResults = document.getElementById('auto-tag-results');
        playerElements.editNotes = document.getElementById('edit-notes');
        playerElements.editNotesLabel = document.getElementById('edit-notes-label');
        playerElements.editStatus = document.getElementById('edit-status');
        playerElements.autoTagsButton = document.getElementById('auto-tags-button');
        playerElements.autoSummaryButton = document.getElementById('auto-summary-button');
        playerElements.refreshMetadataButton = document.getElementById('refresh-metadata-button');
        playerElements.refreshThumbnailButton = document.getElementById('refresh-thumbnail-button');
        playerElements.thumbnailImage = document.getElementById('player-thumbnail-image');
        playerElements.metadata = document.getElementById('player-metadata');
        playerElements.facts = document.getElementById('player-facts');
        playerElements.formatSelect = document.getElementById('player-format');
        playerElements.downloadLink = document.getElementById('player-download');
        playerElements.sourceLink = document.getElementById('player-source');
        playerElements.downloadMenu = document.getElementById('player-download-menu');
        playerElements.deleteButton = document.getElementById('player-delete');
        if (playerElements.formatSelect) {
          playerElements.formatSelect.addEventListener('change', updatePlayerDownloadLink);
        }
        if (playerElements.deleteButton) {
          playerElements.deleteButton.addEventListener('click', handlePlayerDelete);
        }
        if (playerElements.editForm) {
          playerElements.editForm.addEventListener('submit', handlePlayerUpdate);
        }
        if (playerElements.autoTagsButton) {
          playerElements.autoTagsButton.addEventListener('click', handleAutoTags);
        }
        if (playerElements.autoSummaryButton) {
          playerElements.autoSummaryButton.addEventListener('click', handleAutoSummary);
        }
        if (playerElements.refreshMetadataButton) {
          playerElements.refreshMetadataButton.addEventListener('click', handleRefreshMetadata);
        }
        if (playerElements.refreshThumbnailButton) {
          playerElements.refreshThumbnailButton.addEventListener('click', handleRefreshThumbnail);
        }
        renderTagSuggestions();
        resetPlayerView();
      }

      function openPlayer(entry) {
        if (!playerElements.modal) {
          return;
        }
        playerElements.modal.classList.remove('is-empty');
        if (playerElements.placeholder) {
          playerElements.placeholder.hidden = true;
        }
        playerState.currentEntry = entry;
        playerState.nextEntryId = null;
        updateEntryQueryParam(entry.id);
        if (playerElements.title) {
          playerElements.title.textContent = entry.title || 'Sin título';
        }
        if (playerElements.uploader) {
          playerElements.uploader.textContent = entry.uploader ? `Autor: ${entry.uploader}` : 'Autor desconocido';
        }
        if (playerElements.category) {
          playerElements.category.textContent = `Categoría: ${toTitle(entry.category || 'miscelánea')}`;
        }
        if (playerElements.duration) {
          playerElements.duration.textContent = `Duración: ${formatDuration(entry.duration)}`;
        }
        const isMusic = entry.library === 'music';
        if (playerElements.notesHeading) {
          playerElements.notesHeading.textContent = isMusic ? 'Letras' : 'Resumen';
        }
        if (playerElements.notes) {
          const text = isMusic ? entry.lyrics || 'Sin letras registradas.' : entry.notes || 'Sin notas adicionales.';
          playerElements.notes.textContent = text;
        }
        if (playerElements.editNotesLabel) {
          playerElements.editNotesLabel.textContent = isMusic ? 'Letras' : 'Descripción o notas';
        }
        populateEditForm(entry);
        renderTagChips(playerElements.tags, entry.tags || []);
        renderFactList(entry);
        renderMetadata(entry.metadata);
        if (playerElements.sourceLink) {
          playerElements.sourceLink.href = entry.url;
        }
        if (playerElements.downloadMenu) {
          playerElements.downloadMenu.open = false;
        }
        if (playerElements.deleteButton) {
          playerElements.deleteButton.disabled = false;
          playerElements.deleteButton.textContent = 'Eliminar video';
        }
        if (playerElements.video) {
          const playbackFormat =
            isMusic && playbackPreferences.musicMode === 'audio'
              ? 'audio'
              : entry.preferred_format || DEFAULT_FORMAT;
          const streamUrl = buildStreamUrl(entry, playbackFormat);
          const poster = entry.thumbnail || '/assets/LogoVideorama.png';
          playerElements.video.src = streamUrl;
          playerElements.video.poster = poster;
          playerElements.video.load();
          playerElements.video.autoplay = true;
          playerElements.video.onended = () => {
            if (playbackPreferences.autoNext) {
              playNextEntry(true);
            }
          };
          playerElements.video.ontimeupdate = () => {
            const remaining = (playerElements.video.duration || 0) - (playerElements.video.currentTime || 0);
            if (remaining <= 10 && playbackPreferences.autoNext && !playerState.nextEntryId) {
              playerState.nextEntryId = nextEntrySelect?.value || pickNextCandidateId();
              renderNextOptions();
            }
          };
          requestAnimationFrame(() => {
            playerElements.video?.play().catch(() => {});
          });
        }
        if (playerElements.thumbnailImage) {
          playerElements.thumbnailImage.src = entry.thumbnail || '/assets/LogoVideorama.png';
          playerElements.thumbnailImage.alt = entry.title ? `Miniatura de ${entry.title}` : 'Miniatura del video';
        }
        if (playerElements.formatSelect) {
          playerElements.formatSelect.innerHTML = formatOptions(entry.preferred_format || DEFAULT_FORMAT)
            .map((option) => `<option value="${option.value}" ${option.selected ? 'selected' : ''}>${option.label}</option>`)
            .join('');
        }
        renderAutoTagResults([]);
        updatePlayerDownloadLink();
        renderNextOptions();
        playerElements.modal.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }

      function resetPlayerView() {
        playerState.currentEntry = null;
        playerState.nextEntryId = null;
        updateEntryQueryParam(null);
        if (playerElements.modal) {
          playerElements.modal.classList.add('is-empty');
        }
        if (playerElements.placeholder) {
          playerElements.placeholder.hidden = false;
        }
        if (playerElements.title) {
          playerElements.title.textContent = 'Elige un video o canción';
        }
        if (playerElements.notesHeading) {
          playerElements.notesHeading.textContent = 'Resumen';
        }
        if (playerElements.uploader) {
          playerElements.uploader.textContent = '';
        }
        if (playerElements.category) {
          playerElements.category.textContent = '';
        }
        if (playerElements.duration) {
          playerElements.duration.textContent = '';
        }
        if (playerElements.notes) {
          playerElements.notes.textContent = 'Reproduce algo para ver detalles aquí.';
        }
        renderTagChips(playerElements.tags, []);
        renderDefinitionList(playerElements.facts, [], 'Sin ficha disponible.');
        renderDefinitionList(playerElements.metadata, [], 'Sin metadatos disponibles.');
        if (playerElements.thumbnailImage) {
          playerElements.thumbnailImage.src = '/assets/LogoVideorama.png';
          playerElements.thumbnailImage.alt = 'Miniatura de Videorama';
        }
        if (playerElements.video) {
          playerElements.video.pause();
          playerElements.video.removeAttribute('src');
          playerElements.video.poster = '/assets/LogoVideorama.png';
          playerElements.video.load();
        }
        if (playerElements.formatSelect) {
          playerElements.formatSelect.innerHTML = '';
        }
        if (playerElements.downloadLink) {
          playerElements.downloadLink.removeAttribute('href');
        }
        if (playerElements.sourceLink) {
          playerElements.sourceLink.removeAttribute('href');
        }
        if (playerElements.downloadMenu) {
          playerElements.downloadMenu.open = false;
        }
        if (nextPicker) {
          nextPicker.hidden = true;
        }
        renderAutoTagResults([]);
      }

      function renderTagChips(container, tags) {
        if (!container) {
          return;
        }
        container.innerHTML = '';
        const cleaned = (tags || []).filter(Boolean);
        if (!cleaned.length) {
          const hint = document.createElement('span');
          hint.className = 'hint';
          hint.textContent = 'Sin etiquetas registradas.';
          container.appendChild(hint);
          return;
        }
        cleaned.slice(0, 8).forEach((tag) => {
          const chip = document.createElement('span');
          chip.className = 'tag';
          chip.textContent = tag;
          container.appendChild(chip);
        });
      }

      function renderFactList(entry) {
        if (!playerElements.facts) {
          return;
        }
        const availability = [];
        if (entry.audio_url) {
          availability.push('Audio');
        }
        if (entry.video_url) {
          availability.push('Videoclip');
        }
        const band = entry.band || entry.metadata?.band || entry.uploader;
        const album = entry.album || entry.metadata?.album;
        const track = entry.track_number || entry.metadata?.track_number;
        const localPath =
          entry.local_path || entry.metadata?.local_path || entry.metadata?.local_url || '';
        const facts = [
          { label: 'Biblioteca', value: entry.library === 'music' ? 'Música' : 'Videos' },
          { label: 'Banda', value: band || '—' },
          { label: 'Álbum', value: album || '—' },
          { label: 'Track', value: track ? `#${track}` : '—' },
          { label: 'Disponibilidad', value: availability.length ? availability.join(' · ') : '—' },
          { label: 'Ruta local', value: localPath || '—' },
          { label: 'Categoría', value: toTitle(entry.category || 'miscelánea') },
          { label: 'Autor', value: entry.uploader || 'Desconocido' },
          { label: 'Duración', value: formatDuration(entry.duration) },
          { label: 'Extractor', value: entry.extractor || '—' },
          { label: 'Resolución', value: inferResolutionFromMetadata(entry.metadata) || '—' },
          { label: 'Códecs', value: inferCodecsFromMetadata(entry.metadata) || '—' },
          {
            label: 'Tamaño',
            value: inferSizeFromMetadata(entry.metadata) ? formatFileSize(inferSizeFromMetadata(entry.metadata)) : '—',
          },
          { label: 'Etiquetas', value: (entry.tags || []).join(', ') || '—' },
          { label: 'Añadido', value: formatDate(entry.added_at) },
        ];
        renderDefinitionList(playerElements.facts, facts, 'Sin ficha disponible.');
      }

      function renderMetadata(metadata) {
        if (!playerElements.metadata) {
          return;
        }
        const normalized = metadata && !Array.isArray(metadata) && typeof metadata === 'object' ? metadata : {};
        const prioritized = [];
        if (Array.isArray(normalized.tags) && normalized.tags.length) {
          prioritized.push({ label: 'Etiquetas originales', value: metadataValueToString(normalized.tags) });
        }
        const remaining = Object.entries(normalized)
          .filter(([label]) => label !== 'tags')
          .slice(0, Math.max(0, 10 - prioritized.length))
          .map(([label, value]) => ({ label, value: metadataValueToString(value) }));
        renderDefinitionList(
          playerElements.metadata,
          [...prioritized, ...remaining],
          'Sin metadatos disponibles.',
        );
      }

      function renderDefinitionList(container, items, emptyMessage) {
        if (!container) {
          return;
        }
        container.innerHTML = '';
        if (!items.length) {
          const empty = document.createElement('p');
          empty.className = 'hint';
          empty.textContent = emptyMessage || 'Sin datos disponibles.';
          container.appendChild(empty);
          return;
        }
        items.forEach(({ label, value }) => {
          const dt = document.createElement('dt');
          dt.textContent = label;
          const dd = document.createElement('dd');
          dd.textContent = value;
          container.appendChild(dt);
          container.appendChild(dd);
        });
      }

      function updateEntryQueryParam(entryId) {
        const params = new URLSearchParams(window.location.search);
        if (entryId) {
          params.set('entry', entryId);
        } else {
          params.delete('entry');
        }
        const query = params.toString();
        const newUrl = query ? `${window.location.pathname}?${query}` : window.location.pathname;
        window.history.replaceState({}, '', newUrl);
      }

      function metadataValueToString(value) {
        if (value === null || value === undefined) {
          return '—';
        }
        if (Array.isArray(value)) {
          return value
            .map((item) => metadataValueToString(item))
            .filter(Boolean)
            .slice(0, 5)
            .join(', ');
        }
        if (typeof value === 'object') {
          try {
            const serialized = JSON.stringify(value);
            return serialized.length > 140 ? `${serialized.slice(0, 140)}…` : serialized;
          } catch (error) {
            console.warn('No se pudo serializar metadato', error);
            return '[objeto]';
          }
        }
        return String(value);
      }

      function formatDate(timestamp) {
        if (!timestamp) {
          return '—';
        }
        try {
          return new Date(timestamp * 1000).toLocaleString('es-ES');
        } catch (error) {
          return '—';
        }
      }

      function updatePlayerDownloadLink() {
        if (!playerElements.formatSelect || !playerElements.downloadLink || !playerState.currentEntry) {
          return;
        }
        const format = playerElements.formatSelect.value || playerState.currentEntry.preferred_format || DEFAULT_FORMAT;
        const href = buildDownloadUrl(playerState.currentEntry, format);
        playerElements.downloadLink.href = href;
      }

      function populateEditForm(entry) {
        if (!playerElements.editForm) {
          return;
        }
        const isMusic = entry.library === 'music';
        if (playerElements.editTitle) {
          playerElements.editTitle.value = entry.title || '';
        }
        if (playerElements.editCategory) {
          playerElements.editCategory.value = entry.category || '';
        }
        if (playerElements.editTags) {
          playerElements.editTags.value = (entry.tags || []).join(', ');
        }
        if (playerElements.editNotes) {
          playerElements.editNotes.value = isMusic ? entry.lyrics || '' : entry.notes || '';
          playerElements.editNotes.placeholder = isMusic
            ? 'Añade la letra o notas musicales'
            : 'Idea principal, capítulo destacado, etc.';
        }
        if (playerElements.editNotesLabel) {
          playerElements.editNotesLabel.textContent = isMusic ? 'Letras' : 'Descripción o notas';
        }
        setEditStatus('');
      }

      function parseTagInput(raw) {
        if (!raw) {
          return [];
        }
        const parts = raw
          .split(',')
          .map((part) => part.trim())
          .filter(Boolean);
        return [...new Set(parts)];
      }

      function addSuggestedTag(tag) {
        if (!playerElements.editTags) return;
        const existing = parseTagInput(playerElements.editTags.value);
        if (!existing.includes(tag)) {
          existing.push(tag);
          playerElements.editTags.value = existing.join(', ');
        }
      }

      function renderAutoTagResults(tags) {
        if (!playerElements.autoTagResults) return;
        playerElements.autoTagResults.innerHTML = '';
        const cleaned = Array.isArray(tags) ? tags.filter(Boolean) : [];
        if (!cleaned.length) {
          const hint = document.createElement('p');
          hint.className = 'hint';
          hint.textContent = 'Usa "Sugerir etiquetas" para rellenarlas automáticamente.';
          playerElements.autoTagResults.appendChild(hint);
          return;
        }
        cleaned.forEach((tag) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.textContent = tag;
          button.addEventListener('click', () => addSuggestedTag(tag));
          playerElements.autoTagResults.appendChild(button);
        });
      }

      function renderTagSuggestions() {
        if (!playerElements.tagSuggestions) return;
        const seeds = Array.isArray(suggestedTags) ? suggestedTags.slice(0, 12) : [];
        playerElements.tagSuggestions.innerHTML = '';
        if (!seeds.length) {
          const fallback = document.createElement('p');
          fallback.className = 'hint';
          fallback.textContent = 'Aún no hay etiquetas populares que sugerir.';
          playerElements.tagSuggestions.appendChild(fallback);
          return;
        }
        seeds.forEach((tag) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.textContent = tag;
          button.addEventListener('click', () => addSuggestedTag(tag));
          playerElements.tagSuggestions.appendChild(button);
        });
      }

      function pickNextCandidateId() {
        if (!libraryState.filtered.length) {
          return null;
        }
        const currentId = playerState.currentEntry?.id;
        if (!currentId) {
          return libraryState.filtered[0]?.id || null;
        }
        const currentIndex = libraryState.filtered.findIndex((item) => item.id === currentId);
        if (currentIndex >= 0 && currentIndex < libraryState.filtered.length - 1) {
          return libraryState.filtered[currentIndex + 1].id;
        }
        return libraryState.filtered[0]?.id || null;
      }

      function playNextEntry(forceAuto = false) {
        if (!libraryState.filtered.length) {
          return;
        }
        let nextId = nextEntrySelect?.value || playerState.nextEntryId;
        if (!nextId && (forceAuto || playbackPreferences.autoPick)) {
          nextId = pickNextCandidateId();
        }
        if (!nextId) {
          return;
        }
        const nextEntry = libraryState.filtered.find((item) => item.id === nextId);
        if (nextEntry) {
          playerState.nextEntryId = null;
          openPlayer(nextEntry);
        }
      }

      function setEditStatus(message) {
        if (playerElements.editStatus) {
          playerElements.editStatus.textContent = message || '';
        }
      }

      async function handlePlayerUpdate(event) {
        event.preventDefault();
        if (!playerState.currentEntry || !playerElements.editForm) {
          return;
        }
        const title = playerElements.editTitle ? playerElements.editTitle.value.trim() : undefined;
        const category = playerElements.editCategory ? playerElements.editCategory.value.trim() : undefined;
        const notesValue = playerElements.editNotes ? playerElements.editNotes.value.trim() : undefined;
        const tagsValue = playerElements.editTags ? playerElements.editTags.value : '';
        const isMusic = playerState.currentEntry.library === 'music';
        const payload = {
          title: title === undefined ? undefined : title || null,
          category: category === undefined ? undefined : category || null,
          notes: isMusic ? null : notesValue === undefined ? undefined : notesValue || null,
          lyrics: isMusic ? (notesValue === undefined ? undefined : notesValue || null) : undefined,
          tags: parseTagInput(tagsValue),
        };
        setEditStatus('Guardando cambios…');
        try {
          const response = await fetch(`/api/library/${playerState.currentEntry.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          });
          const result = await response.json().catch(() => ({}));
          if (!response.ok) {
            throw new Error(result.detail || 'No se pudo actualizar el video.');
          }
          updateEntryInLibrary(result);
          playerState.currentEntry = result;
          openPlayer(result);
          applyFilters();
          setEditStatus('Cambios guardados.');
        } catch (error) {
          console.error(error);
          setEditStatus(error.message || 'No se pudo guardar.');
        }
      }

      async function handleAutoTags() {
        if (!playerState.currentEntry) {
          return;
        }
        setEditStatus('Generando etiquetas…');
        try {
          const response = await fetch('/api/import/auto-tags', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              url: playerState.currentEntry.url,
              title: playerElements.editTitle?.value || playerState.currentEntry.title,
              notes: playerElements.editNotes?.value || playerState.currentEntry.notes,
              metadata: playerState.currentEntry.metadata || {},
              prefer_transcription: true,
            }),
          });
          const result = await response.json().catch(() => ({}));
          if (!response.ok) {
            throw new Error(result.detail || 'No se pudieron sugerir etiquetas.');
          }
          if (playerElements.editTags) {
            playerElements.editTags.value = (result.tags || []).join(', ');
          }
          renderAutoTagResults(result.tags || []);
          setEditStatus('Etiquetas sugeridas listas.');
        } catch (error) {
          console.error(error);
          setEditStatus(error.message || 'No se pudieron obtener etiquetas.');
        }
      }

      async function handleAutoSummary() {
        if (!playerState.currentEntry) {
          return;
        }
        setEditStatus('Generando descripción…');
        try {
          const response = await fetch('/api/import/auto-summary', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              url: playerState.currentEntry.url,
              title: playerElements.editTitle?.value || playerState.currentEntry.title,
              notes: playerElements.editNotes?.value || playerState.currentEntry.notes,
              metadata: playerState.currentEntry.metadata || {},
              prefer_transcription: true,
            }),
          });
          const result = await response.json().catch(() => ({}));
          if (!response.ok) {
            throw new Error(result.detail || 'No se pudo sugerir la descripción.');
          }
          if (playerElements.editNotes && result.summary) {
            playerElements.editNotes.value = result.summary;
          }
          setEditStatus('Descripción sugerida aplicada.');
        } catch (error) {
          console.error(error);
          setEditStatus(error.message || 'No se pudo generar la descripción.');
        }
      }

      async function handleRefreshMetadata() {
        if (!playerState.currentEntry || !playerElements.refreshMetadataButton) {
          return;
        }
        const button = playerElements.refreshMetadataButton;
        const originalLabel = button.textContent;
        button.disabled = true;
        button.textContent = 'Reescaneando…';
        setEditStatus('Actualizando metadatos…');
        try {
          const response = await fetch(`/api/library/${playerState.currentEntry.id}/metadata`, {
            method: 'POST',
          });
          const result = await response.json().catch(() => ({}));
          if (!response.ok) {
            throw new Error(result.detail || 'No se pudo reescanear los metadatos.');
          }
          playerState.currentEntry = result;
          updateEntryInLibrary(result);
          applyFilters();
          openPlayer(result);
          setEditStatus('Metadatos actualizados.');
        } catch (error) {
          console.error(error);
          setEditStatus(error.message || 'No se pudo actualizar metadatos.');
        } finally {
          button.disabled = false;
          button.textContent = originalLabel;
        }
      }

      async function handleRefreshThumbnail() {
        if (!playerState.currentEntry || !playerElements.refreshThumbnailButton) {
          return;
        }
        const button = playerElements.refreshThumbnailButton;
        const originalLabel = button.textContent;
        button.disabled = true;
        button.textContent = 'Buscando miniatura…';
        setEditStatus('Obteniendo nueva miniatura…');
        try {
          const response = await fetch(`/api/library/${playerState.currentEntry.id}/thumbnail`, {
            method: 'POST',
          });
          const result = await response.json().catch(() => ({}));
          if (!response.ok) {
            throw new Error(result.detail || 'No se pudo regenerar la miniatura.');
          }
          playerState.currentEntry = result;
          updateEntryInLibrary(result);
          applyFilters();
          if (playerElements.video) {
            const poster = result.thumbnail || 'https://placehold.co/640x360?text=Videorama';
            playerElements.video.poster = poster;
          }
          if (playerElements.thumbnailImage) {
            playerElements.thumbnailImage.src = result.thumbnail || 'https://placehold.co/640x360?text=Videorama';
          }
          setEditStatus('Miniatura actualizada.');
        } catch (error) {
          console.error(error);
          setEditStatus(error.message || 'No se pudo regenerar la miniatura.');
        } finally {
          button.disabled = false;
          button.textContent = originalLabel;
        }
      }

      async function handlePlayerDelete() {
        if (!playerElements.deleteButton || !playerState.currentEntry) {
          return;
        }
        const entry = playerState.currentEntry;
        const confirmed = window.confirm(
          `¿Seguro que deseas eliminar "${entry.title || 'este video'}" de la biblioteca? Esta acción no se puede deshacer.`,
        );
        if (!confirmed) {
          return;
        }
        const originalLabel = playerElements.deleteButton.textContent;
        playerElements.deleteButton.disabled = true;
        playerElements.deleteButton.textContent = 'Eliminando…';
        try {
          const response = await fetch(`/api/library/${entry.id}`, { method: 'DELETE' });
          const payload = await response.json().catch(() => ({}));
          if (!response.ok) {
            throw new Error(payload.detail || 'No se pudo eliminar el video.');
          }
          removeEntryFromLibrary(entry.id);
          stopPlayer();
        } catch (error) {
          alert(error.message);
        } finally {
          playerElements.deleteButton.disabled = false;
          playerElements.deleteButton.textContent = originalLabel;
        }
      }

      function removeEntryFromLibrary(entryId) {
        if (!entryId) {
          return;
        }
        libraryState.entries = libraryState.entries.filter((item) => item.id !== entryId);
        libraryState.favorites.delete(entryId);
        buildCategories();
        buildPlaylists();
        applyFilters();
      }

      function updateEntryInLibrary(updatedEntry) {
        if (!updatedEntry?.id) {
          return;
        }
        libraryState.entries = libraryState.entries.map((item) =>
          item.id === updatedEntry.id ? { ...item, ...updatedEntry } : item,
        );
        libraryState.filtered = libraryState.filtered.map((item) =>
          item.id === updatedEntry.id ? { ...item, ...updatedEntry } : item,
        );
        buildCategories();
        buildPlaylists();
        updateFavoriteCounter();
      }

      function stopPlayer() {
        if (playerElements.video) {
          playerElements.video.pause();
          playerElements.video.removeAttribute('src');
          playerElements.video.load();
        }
        resetPlayerView();
      }

      function setupManagerForms() {
        const staticForm = document.getElementById('static-playlist-form');
        const dynamicForm = document.getElementById('dynamic-playlist-form');
        const categoryForm = document.getElementById('category-settings-form');
        if (staticForm) {
          staticForm.addEventListener('submit', handleStaticPlaylistSubmit);
        }
        if (dynamicForm) {
          dynamicForm.addEventListener('submit', handleDynamicPlaylistSubmit);
        }
        if (categoryForm) {
          categoryForm.addEventListener('submit', handleCategorySettingsSubmit);
        }
      }

      function openModal(id) {
        const modal = document.getElementById(id);
        if (!modal) {
          return;
        }
        modal.classList.add('open');
        modal.setAttribute('aria-hidden', 'false');
      }

      function closeModal(modal) {
        if (!modal) {
          return;
        }
        modal.classList.remove('open');
        modal.setAttribute('aria-hidden', 'true');
      }

      function buildCategories() {
        const categories = new Map();
        libraryState.entries.forEach((entry) => {
          const name = normalize(entry.category) || 'miscelánea';
          categories.set(name, (categories.get(name) || 0) + 1);
        });
        libraryState.categoryStats = [...categories.entries()].map(([slug, count]) => ({ slug, count }));
        const preferenceMap = new Map(libraryState.categorySettings.map((pref) => [pref.slug, pref]));
        preferenceMap.forEach((pref, slug) => {
          if (!categories.has(slug)) {
            libraryState.categoryStats.push({ slug, count: 0 });
          }
        });
        const chips = [
          { id: 'all', label: 'Todos', count: libraryState.entries.length },
          { id: 'favorites', label: 'Favoritos', count: libraryState.favorites.size },
        ];
        libraryState.categoryStats.forEach(({ slug, count }) => {
          const pref = preferenceMap.get(slug);
          if (pref?.hidden) {
            return;
          }
          const label = pref?.label?.trim() || toTitle(slug);
          chips.push({ id: slug, label, count });
        });
        libraryState.categories = chips;
        renderCategoryChips();
      }

      function renderCategoryChips() {
        const container = document.getElementById('category-chips');
        container.innerHTML = '';
        libraryState.categories.forEach((chip) => {
          const element = document.createElement('button');
          element.type = 'button';
          element.className = `chip ${libraryState.activeCategory === chip.id ? 'active' : ''}`;
          element.textContent = `${chip.label} (${chip.count})`;
          element.addEventListener('click', () => {
            libraryState.activeCategory = chip.id;
            libraryState.activePlaylistId = null;
            applyFilters();
          });
          container.appendChild(element);
        });
      }

      function buildPlaylists() {
        const auto = buildAutoPlaylists(libraryState.entries);
        const custom = buildCustomPlaylists(libraryState.customPlaylists);
        libraryState.playlists = [...STATIC_PLAYLISTS, ...auto, ...custom];
        const playlistCount = document.getElementById('playlist-count');
        playlistCount.textContent = libraryState.playlists.length;
        renderPlaylists();
      }

      function buildAutoPlaylists(items) {
        const categoryCounts = aggregateCounts(items.map((entry) => normalize(entry.category)));
        const topCategories = categoryCounts.slice(0, 4).map((cat) => ({
          id: `cat-${cat.value}`,
          name: `Categoría: ${toTitle(cat.value)}`,
          description: `${cat.count} piezas seleccionadas automáticamente.`,
          category: 'dynamic',
          source: 'system',
          resolve: (entries) => entries.filter((entry) => normalize(entry.category) === cat.value).slice(0, 12),
        }));

        const tagCounts = aggregateCounts(
          items
            .flatMap((entry) => (Array.isArray(entry.tags) ? entry.tags : []))
            .map((tag) => normalize(tag))
            .filter(Boolean),
        ).slice(0, 3);

        const tagPlaylists = tagCounts.map((tag) => ({
          id: `tag-${tag.value}`,
          name: `Etiqueta: ${toTitle(tag.value)}`,
          description: 'Agrupación dinámica según etiquetas coincidentes.',
          category: 'dynamic',
          source: 'system',
          resolve: (entries) =>
            entries.filter((entry) => (entry.tags || []).some((tagName) => normalize(tagName) === tag.value)).slice(0, 12),
        }));

        return [...topCategories, ...tagPlaylists];
      }

      function buildCustomPlaylists(items) {
        return items.map((playlist) => {
          if (playlist.mode === 'static') {
            const entryIds = playlist.config?.entry_ids || [];
            return {
              ...playlist,
              category: 'static',
              source: 'custom',
              resolve: (entries) => entries.filter((entry) => entryIds.includes(entry.id)),
            };
          }
          return {
            ...playlist,
            category: 'dynamic',
            source: 'custom',
            resolve: (entries) => applyCustomRule(entries, playlist.config?.rules || {}),
          };
        });
      }

      function applyCustomRule(entries, rules) {
        if (!rules || !rules.type) {
          return entries;
        }
        let results = entries;
        const term = normalize(rules.term);
        if (rules.type === 'tag' && term) {
          results = results.filter((entry) => (entry.tags || []).some((tag) => normalize(tag) === term));
        } else if (rules.type === 'category' && term) {
          results = results.filter((entry) => normalize(entry.category) === term);
        } else if (rules.type === 'uploader' && term) {
          results = results.filter((entry) => normalize(entry.uploader) === term);
        } else if (rules.type === 'duration_min' && Number.isFinite(Number(rules.minutes))) {
          const threshold = Number(rules.minutes) * 60;
          results = results.filter((entry) => (entry.duration || 0) >= threshold);
        } else if (rules.type === 'duration_max' && Number.isFinite(Number(rules.minutes))) {
          const threshold = Number(rules.minutes) * 60;
          results = results.filter((entry) => (entry.duration || 0) <= threshold);
        }
        return results.slice(0, 36);
      }

      function renderPlaylists() {
        const staticList = document.getElementById('static-playlists');
        const dynamicList = document.getElementById('dynamic-playlists');
        staticList.innerHTML = '';
        dynamicList.innerHTML = '';
        libraryState.playlists.forEach((playlist) => {
          const listItem = document.createElement('li');
          const button = document.createElement('button');
          button.type = 'button';
          button.className = libraryState.activePlaylistId === playlist.id ? 'active' : '';
          const badge = playlist.source === 'custom' ? 'Personalizada' : playlist.category === 'static' ? 'Lista fija' : 'Búsqueda';
          button.innerHTML = `${playlist.name}<small>${badge}</small>`;
          button.addEventListener('click', () => {
            libraryState.activePlaylistId = playlist.id;
            libraryState.activeCategory = 'all';
            applyFilters();
            renderPlaylists();
          });
          listItem.appendChild(button);
          if (playlist.category === 'static') {
            staticList.appendChild(listItem);
          } else {
            dynamicList.appendChild(listItem);
          }
        });
      }

      function applyFilters() {
        let items = [...libraryState.entries];
        if (libraryState.activePlaylistId) {
          const playlist = libraryState.playlists.find((pl) => pl.id === libraryState.activePlaylistId);
          if (playlist) {
            items = playlist.resolve(libraryState.entries);
          }
        } else if (libraryState.activeCategory === 'favorites') {
          items = items.filter((entry) => libraryState.favorites.has(entry.id));
        } else if (libraryState.activeCategory !== 'all') {
          items = items.filter((entry) => normalize(entry.category) === libraryState.activeCategory);
        }

        if (libraryState.search) {
          items = items.filter((entry) => {
            const haystack = [entry.title, entry.uploader, entry.notes, entry.category]
              .concat(entry.tags || [])
              .join(' ')
              .toLowerCase();
            return haystack.includes(libraryState.search);
          });
        }

        libraryState.filtered = items;
        renderLibrary(items);
        updateCounters();
        renderNextOptions();
      }

      async function openEntryFromUrl() {
        const params = new URLSearchParams(window.location.search);
        const entryId = params.get('entry');
        if (!entryId) {
          return;
        }
        const cached = libraryState.entries.find((item) => item.id === entryId);
        if (cached) {
          openPlayer(cached);
          return;
        }
        try {
          const response = await fetch(`/api/library/${entryId}`);
          if (!response.ok) {
            return;
          }
          const entry = await response.json();
          if (!entry?.id) {
            return;
          }
          libraryState.entries = [entry, ...libraryState.entries];
          buildCategories();
          buildPlaylists();
          applyFilters();
          openPlayer(entry);
        } catch (error) {
          console.warn('No se pudo cargar la entrada solicitada', error);
        }
      }

      function renderLibrary(items) {
        const grid = document.getElementById('library-grid');
        const emptyState = document.getElementById('empty-state');
        grid.innerHTML = '';
        if (!items.length) {
          emptyState.hidden = false;
          return;
        }
        emptyState.hidden = true;
        const fragment = document.createDocumentFragment();
        items.forEach((entry) => {
          fragment.appendChild(createVideoCard(entry));
        });
        grid.appendChild(fragment);
      }

      function renderNextOptions() {
        if (!nextEntrySelect) {
          return;
        }
        const candidates = libraryState.filtered.filter(
          (entry) => !playerState.currentEntry || entry.id !== playerState.currentEntry.id,
        );
        nextEntrySelect.innerHTML = '';
        candidates.slice(0, 20).forEach((entry) => {
          const option = document.createElement('option');
          option.value = entry.id;
          option.textContent = entry.title || entry.url;
          nextEntrySelect.appendChild(option);
        });
        if (!playerState.nextEntryId && candidates.length) {
          playerState.nextEntryId = candidates[0].id;
          nextEntrySelect.value = playerState.nextEntryId;
        } else if (playerState.nextEntryId) {
          nextEntrySelect.value = playerState.nextEntryId;
        }
        const shouldShow = playbackPreferences.autoNext && candidates.length > 0;
        if (nextPicker) {
          nextPicker.hidden = !shouldShow;
        }
      }

      function truncateText(value, limit = 20) {
        const text = (value || '').toString();
        if (text.length <= limit) {
          return text;
        }
        return `${text.slice(0, Math.max(0, limit - 1))}…`;
      }

      function escapeAttribute(value) {
        return (value || '')
          .toString()
          .replace(/&/g, '&amp;')
          .replace(/"/g, '&quot;');
      }

      function createVideoCard(entry) {
        const preferredFormat = entry.preferred_format || DEFAULT_FORMAT;
        const downloadUrl = buildDownloadUrl(entry, preferredFormat);
        const fullTitle = entry.title || 'Sin título';
        const displayTitle = truncateText(fullTitle);
        const uploaderName = entry.uploader || 'Autor desconocido';
        const displayUploader = truncateText(uploaderName);
        const categoryLabel = toTitle(entry.category || 'miscelánea');
        const displayCategory = truncateText(categoryLabel);
        const noteText = entry.notes || 'Sin notas adicionales.';
        const displayNotes = truncateText(noteText, 20);
        const titleAttr = escapeAttribute(fullTitle);
        const uploaderAttr = escapeAttribute(`${uploaderName} · ${categoryLabel}`);
        const notesAttr = escapeAttribute(noteText);
        const card = document.createElement('article');
        card.className = 'video-card';
        card.innerHTML = `
          <div class="video-header">
            <h3 title="${titleAttr}">${displayTitle}</h3>
            <p class="video-meta" title="${uploaderAttr}">${displayUploader} · ${displayCategory}</p>
            <p class="video-meta tech-meta">${buildTechSummary(entry)}</p>
          </div>
          <div class="video-preview">
            <div class="thumb">
              <img src="${entry.thumbnail || 'https://placehold.co/640x360?text=Videorama'}" alt="Miniatura" loading="lazy" />
              <button class="favorite-toggle ${libraryState.favorites.has(entry.id) ? 'active' : ''}" title="Marcar como favorito">★</button>
              <span class="duration-badge">${formatDuration(entry.duration)}</span>
            </div>
            <video class="card-player" playsinline controls preload="metadata" poster="${entry.thumbnail || ''}"></video>
          </div>
          <div class="video-body">
            <div class="tag-row">
              ${(entry.tags || []).slice(0, 4).map((tag) => `<span class="tag">${tag}</span>`).join('')}
            </div>
            <p class="notes" title="${notesAttr}">${displayNotes}</p>
            <div class="actions">
              <button class="primary-button play-button" type="button">Reproducir</button>
              <button class="info-button" type="button">Más información</button>
              <details class="download-menu">
                <summary>Descargas y recodificación</summary>
                <div class="download-menu-body">
                  <select class="format-select">
                    ${formatOptions(preferredFormat)
                      .map((option) => `<option value="${option.value}" ${option.selected ? 'selected' : ''}>${option.label}</option>`)
                      .join('')}
                  </select>
                  <div class="menu-actions">
                    <a class="ghost-link download-link" href="${downloadUrl}" target="_blank" rel="noreferrer">Descargar</a>
                    <a class="ghost-link" href="${entry.url}" target="_blank" rel="noreferrer">Ver origen</a>
                  </div>
                </div>
              </details>
            </div>
          </div>
        `;
        const favoriteButton = card.querySelector('.favorite-toggle');
        favoriteButton.addEventListener('click', () => toggleFavorite(entry.id, favoriteButton));
        const select = card.querySelector('.download-menu .format-select');
        const downloadLink = card.querySelector('.download-link');
        select.addEventListener('change', () => {
          downloadLink.href = buildDownloadUrl(entry, select.value);
        });
        const playButton = card.querySelector('.play-button');
        const infoButton = card.querySelector('.info-button');
        const thumb = card.querySelector('.thumb');
        playButton.addEventListener('click', () => startInlinePlayback(entry, card));
        thumb.addEventListener('click', () => startInlinePlayback(entry, card));
        if (infoButton) {
          infoButton.addEventListener('click', () => openPlayer(entry));
        }
        return card;
      }

      function toggleFavorite(id, button) {
        if (libraryState.favorites.has(id)) {
          libraryState.favorites.delete(id);
          button.classList.remove('active');
        } else {
          libraryState.favorites.add(id);
          button.classList.add('active');
        }
        persistFavorites();
        if (libraryState.activeCategory === 'favorites') {
          applyFilters();
        } else {
          updateFavoriteCounter();
        }
      }

      function buildDownloadUrl(entry, format) {
        if (!entry || !entry.id) {
          return '#';
        }
        const params = new URLSearchParams();
        if (format) {
          params.set('format', format);
        }
        const query = params.toString();
        return `/api/library/${entry.id}/download${query ? `?${query}` : ''}`;
      }

      function buildStreamUrl(entry, format) {
        if (!entry || !entry.id) {
          return '';
        }
        const params = new URLSearchParams();
        if (format) {
          params.set('format', format);
        }
        const query = params.toString();
        return `/api/library/${entry.id}/stream${query ? `?${query}` : ''}`;
      }

      function resetInlinePlayer(card) {
        if (!card) {
          return;
        }
        card.classList.remove('playing');
        const player = card.querySelector('.card-player');
        const thumb = card.querySelector('.thumb');
        if (player) {
          player.pause();
          delete player.dataset.fallbackTried;
          player.removeAttribute('src');
          player.load();
        }
        if (thumb) {
          thumb.removeAttribute('aria-hidden');
        }
      }

      function startInlinePlayback(entry, card) {
        if (!card) {
          openPlayer(entry);
          return;
        }
        document.querySelectorAll('.video-card.playing').forEach((activeCard) => {
          if (activeCard !== card) {
            resetInlinePlayer(activeCard);
          }
        });
        const player = card.querySelector('.card-player');
        if (!player) {
          openPlayer(entry);
          return;
        }
        const thumb = card.querySelector('.thumb');
        card.classList.add('playing');
        if (thumb) {
          thumb.setAttribute('aria-hidden', 'true');
        }
        const primaryFormat = entry.preferred_format || DEFAULT_FORMAT;
        const fallbackFormat = primaryFormat === DEFAULT_FORMAT ? null : DEFAULT_FORMAT;
        const attemptPlayback = (formatToUse, isFallback = false) => {
          const sourceUrl = buildStreamUrl(entry, formatToUse);
          if (!sourceUrl) {
            resetInlinePlayer(card);
            openPlayer(entry);
            return;
          }
          player.src = sourceUrl;
          player.poster = entry.thumbnail || '';
          player.load();
          player
            .play()
            .catch((error) => {
              console.warn('No se pudo iniciar la reproducción inline', error);
              if (!isFallback && fallbackFormat) {
                attemptPlayback(fallbackFormat, true);
              } else {
                resetInlinePlayer(card);
                openPlayer(entry);
              }
            });
        };

        player.onerror = () => {
          if (player.dataset.fallbackTried) {
            resetInlinePlayer(card);
            openPlayer(entry);
            return;
          }
          player.dataset.fallbackTried = '1';
          if (fallbackFormat) {
            attemptPlayback(fallbackFormat, true);
          } else {
            resetInlinePlayer(card);
            openPlayer(entry);
          }
        };
        player.onended = () => {
          resetInlinePlayer(card);
        };
        attemptPlayback(primaryFormat);
      }

      function formatDuration(seconds) {
        if (!seconds) {
          return '—';
        }
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        if (mins >= 60) {
          const hours = Math.floor(mins / 60);
          const remMins = mins % 60;
          return `${hours.toString().padStart(2, '0')}:${remMins.toString().padStart(2, '0')}:${secs
            .toString()
            .padStart(2, '0')}`;
        }
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
      }

      function formatFileSize(bytes) {
        if (!bytes || Number.isNaN(Number(bytes))) {
          return '';
        }
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        let size = Number(bytes);
        let unitIndex = 0;
        while (size >= 1024 && unitIndex < units.length - 1) {
          size /= 1024;
          unitIndex += 1;
        }
        const formatted = size >= 10 || size % 1 === 0 ? size.toFixed(0) : size.toFixed(1);
        return `${formatted} ${units[unitIndex]}`;
      }

      function inferSizeFromMetadata(metadata) {
        if (!metadata || typeof metadata !== 'object') {
          return null;
        }
        const candidates = ['file_size', 'filesize', 'filesize_approx', 'approx_filesize'];
        for (const key of candidates) {
          const value = metadata[key];
          if (Number.isFinite(value) && value > 0) {
            return Number(value);
          }
        }
        const formats = metadata.requested_formats || metadata.formats || [];
        for (const fmt of formats) {
          if (!fmt || typeof fmt !== 'object') continue;
          if (Number.isFinite(fmt.filesize) && fmt.filesize > 0) {
            return Number(fmt.filesize);
          }
          if (Number.isFinite(fmt.filesize_approx) && fmt.filesize_approx > 0) {
            return Number(fmt.filesize_approx);
          }
        }
        return null;
      }

      function inferResolutionFromMetadata(metadata) {
        if (!metadata || typeof metadata !== 'object') {
          return '';
        }
        if (Number.isFinite(metadata.width) && Number.isFinite(metadata.height) && metadata.width > 0 && metadata.height > 0) {
          return `${Number(metadata.width)}x${Number(metadata.height)}`;
        }
        const resolution = metadata.resolution || metadata.format_note;
        if (resolution) {
          return `${resolution}`;
        }
        const formats = metadata.requested_formats || metadata.formats || [];
        for (const fmt of formats) {
          if (!fmt || typeof fmt !== 'object') continue;
          if (fmt.resolution) {
            return `${fmt.resolution}`;
          }
          if (Number.isFinite(fmt.width) && Number.isFinite(fmt.height)) {
            return `${fmt.width}x${fmt.height}`;
          }
        }
        return '';
      }

      function inferCodecsFromMetadata(metadata) {
        if (!metadata || typeof metadata !== 'object') {
          return '';
        }
        const codecs = [];
        const vcodec = metadata.vcodec || metadata.video_codec;
        const acodec = metadata.acodec || metadata.audio_codec;
        [vcodec, acodec].forEach((codec) => {
          if (codec && `${codec}`.toLowerCase() !== 'none') {
            codecs.push(codec);
          }
        });
        if (!codecs.length) {
          const formats = metadata.requested_formats || metadata.formats || [];
          for (const fmt of formats) {
            if (fmt?.vcodec && `${fmt.vcodec}`.toLowerCase() !== 'none') {
              codecs.push(fmt.vcodec);
            }
            if (fmt?.acodec && `${fmt.acodec}`.toLowerCase() !== 'none') {
              codecs.push(fmt.acodec);
            }
            if (codecs.length) break;
          }
        }
        return codecs.join(' / ');
      }

      function buildTechSummary(entry) {
        const details = [];
        const size = inferSizeFromMetadata(entry.metadata);
        const resolution = inferResolutionFromMetadata(entry.metadata);
        const codecs = inferCodecsFromMetadata(entry.metadata);
        const duration = formatDuration(entry.duration);
        if (duration && duration !== '—') {
          details.push(`Duración ${duration}`);
        }
        if (resolution) {
          details.push(resolution);
        }
        if (codecs) {
          details.push(codecs);
        }
        if (size) {
          details.push(formatFileSize(size));
        }
        return details.join(' • ') || 'Metadatos en preparación';
      }

      function normalize(value) {
        return (value || '')
          .toString()
          .trim()
          .toLowerCase();
      }

      function toTitle(value) {
        const normalized = normalize(value);
        if (!normalized) {
          return '';
        }
        return normalized.replace(/\w/g, (match) => match.toUpperCase());
      }

      function shuffle(items) {
        const copy = items.slice();
        for (let i = copy.length - 1; i > 0; i -= 1) {
          const j = Math.floor(Math.random() * (i + 1));
          [copy[i], copy[j]] = [copy[j], copy[i]];
        }
        return copy;
      }

      function formatOptions(preferred) {
        const options = [
          { value: preferred, label: 'Formato original', selected: true },
          { value: 'video_high', label: 'Video alta calidad' },
          { value: 'video_med', label: 'Video 720p' },
          { value: 'video_low', label: 'Video ligero' },
          { value: 'audio_high', label: 'Audio alta calidad' },
          { value: 'audio_med', label: 'Audio 96 kbps' },
          { value: 'audio_low', label: 'Audio 48 kbps' },
          { value: 'transcript_json', label: 'Transcripción JSON' },
          { value: 'transcript_text', label: 'Transcripción TXT' },
          { value: 'transcript_srt', label: 'Subtítulos SRT' },
          { value: 'ffmpeg_1080p', label: 'ffmpeg_1080p' },
          { value: 'ffmpeg_720p', label: 'ffmpeg_720p' },
          { value: 'ffmpeg_480p', label: 'ffmpeg_480p' },
          { value: 'ffmpeg_mp3-192', label: 'ffmpeg_mp3-192' },
          { value: 'ffmpeg_wav', label: 'ffmpeg_wav' },
        ];
        const seen = new Set();
        return options.filter((option) => {
          if (!option.value || seen.has(option.value)) {
            return false;
          }
          seen.add(option.value);
          return true;
        });
      }

      function aggregateCounts(values) {
        const map = new Map();
        values.forEach((value) => {
          if (!value) return;
          map.set(value, (map.get(value) || 0) + 1);
        });
        return [...map.entries()]
          .map(([value, count]) => ({ value, count }))
          .sort((a, b) => b.count - a.count);
      }

      function updateCounters() {
        const counter = document.getElementById('results-counter');
        counter.textContent = `${libraryState.filtered.length} resultados`;
        const active = document.getElementById('active-playlist');
        if (libraryState.activePlaylistId) {
          const playlist = libraryState.playlists.find((pl) => pl.id === libraryState.activePlaylistId);
          active.textContent = playlist ? `Lista activa: ${playlist.name}` : 'Lista personalizada';
        } else if (libraryState.activeCategory === 'favorites') {
          active.textContent = 'Mostrando tus favoritos locales.';
        } else if (libraryState.activeCategory === 'all') {
          const libraryLabel = libraryState.activeLibrary === 'music' ? 'música' : 'video';
          active.textContent = `Mostrando la biblioteca de ${libraryLabel}.`;
        } else {
          active.textContent = `Categoría: ${toTitle(libraryState.activeCategory)}`;
        }
      }

      function renderPlaylistManager() {
        const container = document.getElementById('custom-playlists');
        container.innerHTML = '';
        if (!libraryState.customPlaylists.length) {
          container.innerHTML = '<li class="empty-state">Todavía no has creado playlists personalizadas.</li>';
          return;
        }
        libraryState.customPlaylists.forEach((playlist) => {
          const item = document.createElement('li');
          item.innerHTML = `
            <div>
              <strong>${playlist.name}</strong>
              <small>${playlist.mode === 'static' ? 'Lista estática' : 'Lista dinámica'}</small>
              <p>${playlist.description || 'Sin descripción'}</p>
            </div>
            <button type="button" data-delete-playlist="${playlist.id}">Eliminar</button>
          `;
          container.appendChild(item);
        });
        container.querySelectorAll('[data-delete-playlist]').forEach((button) => {
          button.addEventListener('click', () => deleteCustomPlaylist(button.getAttribute('data-delete-playlist')));
        });
      }

      function handleStaticPlaylistSubmit(event) {
        event.preventDefault();
        const name = document.getElementById('static-playlist-name').value.trim();
        const description = document.getElementById('static-playlist-description').value.trim();
        const entryIds = libraryState.filtered.map((entry) => entry.id);
        if (!entryIds.length) {
          updateStatus('static-playlist-status', 'Necesitas al menos un elemento visible para crear la lista.', true);
          return;
        }
        fetch('/api/playlists', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, description, mode: 'static', entry_ids: entryIds }),
        })
          .then((response) => {
            if (!response.ok) {
              return response.json().then((payload) => {
                throw new Error(payload.detail || 'No se pudo crear la lista estática.');
              });
            }
            return response.json();
          })
          .then(() => {
            updateStatus('static-playlist-status', 'Lista guardada correctamente.');
            event.target.reset();
            return fetchCustomPlaylists();
          })
          .then(() => {
            buildPlaylists();
            renderPlaylistManager();
          })
          .catch((error) => updateStatus('static-playlist-status', error.message, true));
      }

      function handleDynamicPlaylistSubmit(event) {
        event.preventDefault();
        const name = document.getElementById('dynamic-playlist-name').value.trim();
        const description = document.getElementById('dynamic-playlist-description').value.trim();
        const type = document.getElementById('dynamic-rule-type').value;
        const termField = document.getElementById('dynamic-rule-term');
        const minutesField = document.getElementById('dynamic-rule-minutes');
        let rules = { type };
        if (type === 'duration_min' || type === 'duration_max') {
          const minutes = Number.parseInt(minutesField.value, 10);
          if (!minutes) {
            updateStatus('dynamic-playlist-status', 'Indica la duración en minutos.', true);
            return;
          }
          rules.minutes = minutes;
          termField.value = '';
        } else {
          const term = termField.value.trim();
          if (!term) {
            updateStatus('dynamic-playlist-status', 'Indica un término para la regla.', true);
            return;
          }
          rules.term = term;
        }
        fetch('/api/playlists', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, description, mode: 'dynamic', rules }),
        })
          .then((response) => {
            if (!response.ok) {
              return response.json().then((payload) => {
                throw new Error(payload.detail || 'No se pudo crear la lista dinámica.');
              });
            }
            return response.json();
          })
          .then(() => {
            updateStatus('dynamic-playlist-status', 'Lista dinámica creada.');
            event.target.reset();
            return fetchCustomPlaylists();
          })
          .then(() => {
            buildPlaylists();
            renderPlaylistManager();
          })
          .catch((error) => updateStatus('dynamic-playlist-status', error.message, true));
      }

      function deleteCustomPlaylist(id) {
        fetch(`/api/playlists/${id}`, { method: 'DELETE' })
          .then((response) => {
            if (!response.ok) {
              return response.json().then((payload) => {
                throw new Error(payload.detail || 'No se pudo eliminar la lista.');
              });
            }
            return response.json();
          })
          .then(() => fetchCustomPlaylists())
          .then(() => {
            buildPlaylists();
            renderPlaylistManager();
          })
          .catch((error) => updateStatus('static-playlist-status', error.message, true));
      }

      function renderCategoryManager() {
        const container = document.getElementById('category-manager-list');
        container.innerHTML = '';
        if (!libraryState.categoryStats.length) {
          container.innerHTML = '<p class="hint">Añade algún vídeo para empezar a personalizar categorías.</p>';
          return;
        }
        const preferenceMap = new Map(libraryState.categorySettings.map((pref) => [pref.slug, pref]));
        const stats = libraryState.categoryStats.slice().sort((a, b) => a.slug.localeCompare(b.slug));
        stats.forEach(({ slug, count }) => {
          const pref = preferenceMap.get(slug) || {};
          const row = document.createElement('div');
          row.className = 'category-row';
          row.dataset.slug = slug;
          row.setAttribute('data-category-row', 'true');
          row.innerHTML = `
            <div>
              <strong>${toTitle(slug)}</strong>
              <small>${count} elementos</small>
            </div>
            <input type="text" value="${pref.label || ''}" placeholder="Etiqueta personalizada" />
            <label>
              <input type="checkbox" ${pref.hidden ? 'checked' : ''} />
              Ocultar
            </label>
          `;
          container.appendChild(row);
        });
      }

      function handleCategorySettingsSubmit(event) {
        event.preventDefault();
        const rows = document.querySelectorAll('[data-category-row]');
        const settings = [...rows].map((row) => {
          const slug = row.dataset.slug;
          const labelInput = row.querySelector('input[type="text"]');
          const hiddenInput = row.querySelector('input[type="checkbox"]');
          return {
            slug,
            label: labelInput.value.trim() || null,
            hidden: hiddenInput.checked,
          };
        });
        fetch('/api/category-settings', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ settings }),
        })
          .then((response) => {
            if (!response.ok) {
              return response.json().then((payload) => {
                throw new Error(payload.detail || 'No se pudieron guardar las categorías.');
              });
            }
            return response.json();
          })
          .then((payload) => {
            libraryState.categorySettings = Array.isArray(payload.settings) ? payload.settings : [];
            buildCategories();
            renderCategoryManager();
            updateStatus('category-manager-status', 'Preferencias guardadas.');
          })
          .catch((error) => updateStatus('category-manager-status', error.message, true));
      }

      function updateStatus(elementId, message, isError = false) {
        const element = document.getElementById(elementId);
        if (!element) {
          return;
        }
        element.textContent = message;
        element.style.color = isError ? '#f87171' : '#bbf7d0';
        if (message) {
          setTimeout(() => {
            element.textContent = '';
          }, 4000);
        }
      }
