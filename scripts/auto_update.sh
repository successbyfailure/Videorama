#!/usr/bin/env bash
set -euo pipefail

# Configuration
INTERVAL_SECONDS=${INTERVAL_SECONDS:-300}
REPO_DIR=${REPO_DIR:-"$(cd "$(dirname "$0")/.." && pwd)"}
UPSTREAM_REF=${UPSTREAM_REF:-}

log() {
  printf '[%s] %s\n' "$(date --iso-8601=seconds)" "$*"
}

ensure_env() {
  local example_env="${REPO_DIR}/example.env"
  local env_file="${REPO_DIR}/.env"

  if [[ ! -f "${example_env}" ]]; then
    log "example.env no encontrado en ${example_env}."
    return
  fi

  touch "${env_file}"

  while IFS= read -r line || [[ -n "$line" ]]; do
    # Preserve comments and blank lines from example.env when syncing defaults
    if [[ -z "${line}" || "${line}" =~ ^[[:space:]]*# ]]; then
      continue
    fi

    if [[ "$line" != *"="* ]]; then
      continue
    fi

    local key=${line%%=*}
    # Skip if the variable is already present in .env
    if grep -qE "^${key}=" "${env_file}"; then
      continue
    fi

    log "Añadiendo nueva variable de entorno '${key}' con su valor por defecto a .env"
    echo "$line" >> "${env_file}"
  done < "${example_env}"
}

update_repo() {
  cd "${REPO_DIR}"
  git fetch --all --quiet

  local branch
  branch=$(git rev-parse --abbrev-ref HEAD)

  local upstream
  if [[ -n "${UPSTREAM_REF}" ]]; then
    upstream=${UPSTREAM_REF}
  else
    upstream=$(git rev-parse --abbrev-ref --symbolic-full-name @{upstream} 2>/dev/null || true)
    if [[ -z "${upstream}" ]]; then
      upstream="origin/${branch}"
    fi
  fi

  local local_ref remote_ref
  local_ref=$(git rev-parse HEAD)
  remote_ref=$(git rev-parse "${upstream}" 2>/dev/null || echo "")

  if [[ -z "${remote_ref}" ]]; then
    log "No se pudo determinar la referencia remota (${upstream})."
    return
  fi

  if [[ "${local_ref}" != "${remote_ref}" ]]; then
    log "Detectados cambios en ${upstream}. Aplicando actualización..."
    if ! git diff --quiet || ! git diff --cached --quiet; then
      log "El árbol de trabajo tiene cambios locales. Omite la actualización para evitar sobreescribir cambios."
      return
    fi

    if ! git merge-base --is-ancestor "${local_ref}" "${remote_ref}"; then
      log "La rama local contiene commits que no están en ${upstream}. Se requiere intervención manual."
      return
    fi

    docker compose stop
    if ! git pull --ff-only; then
      log "git pull falló. Reiniciando los servicios para evitar tiempo de inactividad."
      docker compose up -d
      return
    fi
    ensure_env
    docker compose build
    docker compose up -d
    log "Servicios actualizados correctamente."
  else
    log "Sin cambios en ${upstream}."
  fi
}

main() {
  log "Iniciando monitorización en ${REPO_DIR} (intervalo: ${INTERVAL_SECONDS}s)"
  while true; do
    update_repo
    sleep "${INTERVAL_SECONDS}"
  done
}

main "$@"
