"""
Sistema de gestión de trabajos asíncronos.
Permite ejecutar operaciones largas sin bloquear la API.
"""
import asyncio
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Estados posibles de un job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    """Representa un trabajo asíncrono."""
    job_id: str
    job_type: str
    status: JobStatus = JobStatus.PENDING
    progress: int = 0  # 0-100
    message: str = ""
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el job a dict para serialización."""
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }


class JobManager:
    """
    Gestor de trabajos asíncronos en memoria.

    Para una solución de producción más robusta, considera usar
    Celery + Redis, pero esto funciona para casos de uso moderados.
    """

    def __init__(self, max_jobs: int = 1000, cleanup_after: int = 3600):
        """
        Args:
            max_jobs: Número máximo de jobs a mantener en memoria.
            cleanup_after: Segundos antes de eliminar jobs completados (1 hora por defecto).
        """
        self._jobs: Dict[str, Job] = {}
        self._max_jobs = max_jobs
        self._cleanup_after = cleanup_after
        self._lock = asyncio.Lock()

    def create_job(self, job_type: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Crea un nuevo job y retorna su ID.

        Args:
            job_type: Tipo de trabajo (add_entry, download, enrich, etc.)
            metadata: Metadatos adicionales del job.

        Returns:
            Job ID generado.
        """
        job_id = secrets.token_urlsafe(16)
        job = Job(
            job_id=job_id,
            job_type=job_type,
            metadata=metadata or {},
        )
        self._jobs[job_id] = job

        # Limpieza preventiva si hay demasiados jobs
        if len(self._jobs) > self._max_jobs:
            self._cleanup_old_jobs()

        return job_id

    def get_job(self, job_id: str) -> Optional[Job]:
        """Obtiene un job por su ID."""
        return self._jobs.get(job_id)

    def update_job(
        self,
        job_id: str,
        status: Optional[JobStatus] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        result: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Actualiza el estado de un job.

        Args:
            job_id: ID del job a actualizar.
            status: Nuevo estado.
            progress: Progreso 0-100.
            message: Mensaje descriptivo.
            result: Resultado del job (si completó exitosamente).
            error: Mensaje de error (si falló).
        """
        job = self._jobs.get(job_id)
        if not job:
            logger.warning(f"Intento de actualizar job inexistente: {job_id}")
            return

        if status is not None:
            job.status = status
            if status == JobStatus.RUNNING and job.started_at is None:
                job.started_at = time.time()
            elif status in (JobStatus.COMPLETED, JobStatus.FAILED):
                job.completed_at = time.time()

        if progress is not None:
            job.progress = max(0, min(100, progress))

        if message is not None:
            job.message = message

        if result is not None:
            job.result = result

        if error is not None:
            job.error = error

    async def run_job(
        self,
        job_id: str,
        func: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Ejecuta una función en background y actualiza el job.

        Args:
            job_id: ID del job a ejecutar.
            func: Función a ejecutar (puede ser sync o async).
            *args: Argumentos posicionales para la función.
            **kwargs: Argumentos nombrados para la función.

        Returns:
            Resultado de la función.

        Raises:
            Exception: Si la función falla.
        """
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} no encontrado")

        try:
            self.update_job(job_id, status=JobStatus.RUNNING, progress=0)

            # Ejecutar función (sync o async)
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = await asyncio.to_thread(func, *args, **kwargs)

            self.update_job(
                job_id,
                status=JobStatus.COMPLETED,
                progress=100,
                result=result,
            )
            return result

        except Exception as exc:
            logger.exception(f"Job {job_id} falló: {exc}")
            self.update_job(
                job_id,
                status=JobStatus.FAILED,
                error=str(exc),
            )
            raise

    def _cleanup_old_jobs(self) -> None:
        """Limpia jobs completados que superen el tiempo de retención."""
        now = time.time()
        to_delete = []

        for job_id, job in self._jobs.items():
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                if job.completed_at and (now - job.completed_at) > self._cleanup_after:
                    to_delete.append(job_id)

        for job_id in to_delete:
            del self._jobs[job_id]
            logger.debug(f"Job {job_id} eliminado por antigüedad")

        # Si aún hay demasiados, eliminar los más antiguos
        if len(self._jobs) > self._max_jobs:
            sorted_jobs = sorted(
                self._jobs.items(),
                key=lambda x: x[1].created_at,
            )
            for job_id, _ in sorted_jobs[: len(self._jobs) - self._max_jobs]:
                del self._jobs[job_id]

    def list_jobs(self, limit: int = 50) -> list[Dict[str, Any]]:
        """
        Lista los jobs más recientes.

        Args:
            limit: Número máximo de jobs a retornar.

        Returns:
            Lista de jobs en formato dict.
        """
        sorted_jobs = sorted(
            self._jobs.values(),
            key=lambda x: x.created_at,
            reverse=True,
        )
        return [job.to_dict() for job in sorted_jobs[:limit]]


# Instancia global del gestor de jobs
job_manager = JobManager()
