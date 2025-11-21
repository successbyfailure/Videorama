"""Gestor de reglas y simulación de firewall para bloqueos por ofensas."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests


@dataclass
class OffenseEvent:
    """Evento de ofensa registrado para una dirección IP."""

    ip: str
    plugin: str
    signature_id: str
    severity: str
    description: str
    timestamp: datetime


@dataclass
class FirewallBlock:
    """Representa un bloqueo activo en el firewall simulado."""

    ip: str
    reason: str
    blocked_until: datetime

    @property
    def active(self) -> bool:
        return datetime.utcnow() < self.blocked_until


class InMemoryFirewall:
    """Implementación en memoria para simular altas y bajas en el firewall."""

    def __init__(self) -> None:
        self._blocks: Dict[str, FirewallBlock] = {}

    def block_ip(self, ip: str, seconds: int, reason: str) -> FirewallBlock:
        expiration = datetime.utcnow() + timedelta(seconds=max(1, seconds))
        block = FirewallBlock(ip=ip, reason=reason, blocked_until=expiration)
        self._blocks[ip] = block
        return block

    def unblock_ip(self, ip: str) -> bool:
        return self._blocks.pop(ip, None) is not None

    def get_block(self, ip: str) -> Optional[FirewallBlock]:
        block = self._blocks.get(ip)
        if block and not block.active:
            self._blocks.pop(ip, None)
            return None
        return block

    def list_blocks(self) -> List[FirewallBlock]:
        expired = [ip for ip, block in self._blocks.items() if not block.active]
        for ip in expired:
            self._blocks.pop(ip, None)
        return list(self._blocks.values())


class OPNsenseFirewall(InMemoryFirewall):
    """Cliente para gestionar bloqueos usando la API de OPNsense.

    Utiliza un alias definido en el firewall para añadir o eliminar direcciones IP.
    Además mantiene un pequeño caché local con la fecha de expiración para poder
    reutilizar la lógica del gestor de reglas.
    """

    def __init__(
        self,
        api_url: str,
        api_key: str,
        api_secret: str,
        alias: str = "videorama_blocks",
        verify_ssl: bool = True,
        timeout: int = 10,
    ) -> None:
        super().__init__()
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.alias = alias
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self._logger = logging.getLogger(__name__)
        self.refresh_blocks()

    def block_ip(self, ip: str, seconds: int, reason: str) -> FirewallBlock:
        block = super().block_ip(ip, seconds, reason)
        try:
            self._alias_add(ip)
        except Exception:
            self._blocks.pop(ip, None)
            self._logger.exception("No se pudo añadir la IP %s al alias OPNsense", ip)
            raise
        return block

    def unblock_ip(self, ip: str) -> bool:
        removed = super().unblock_ip(ip)
        try:
            self._alias_delete(ip)
        except Exception:
            self._logger.exception("No se pudo eliminar la IP %s del alias OPNsense", ip)
        return removed

    def get_block(self, ip: str) -> Optional[FirewallBlock]:
        self.refresh_blocks()
        return super().get_block(ip)

    def list_blocks(self) -> List[FirewallBlock]:
        self.refresh_blocks()
        return super().list_blocks()

    # ------------------------------------------------------------------
    # Alias helpers
    # ------------------------------------------------------------------

    def refresh_blocks(self) -> None:
        """Sincroniza el caché local con el alias remoto."""

        try:
            addresses = self._alias_addresses()
        except Exception:
            self._logger.exception("No se pudo refrescar el alias %s en OPNsense", self.alias)
            return

        horizon = datetime.utcnow() + timedelta(days=365)
        for address in addresses:
            if address not in self._blocks:
                self._blocks[address] = FirewallBlock(
                    ip=address, reason=f"Alias {self.alias}", blocked_until=horizon
                )

        # Limpia entradas que ya no estén en el alias
        for cached in list(self._blocks.keys()):
            if cached not in addresses:
                self._blocks.pop(cached, None)

    def _alias_add(self, ip: str) -> None:
        payload = {"address": ip}
        self._request("post", f"add/{self.alias}", json=payload)

    def _alias_delete(self, ip: str) -> None:
        payload = {"address": ip}
        self._request("post", f"del/{self.alias}", json=payload)

    def _alias_addresses(self) -> List[str]:
        data = self._request("get", f"get/{self.alias}") or {}
        addresses: List[str] = []
        if isinstance(data, dict):
            rows = data.get("rows") or data.get("items") or data.get("data")
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, str):
                        addresses.append(row)
                        continue
                    if isinstance(row, dict):
                        address = row.get("ip") or row.get("address") or row.get("content")
                        if isinstance(address, str):
                            addresses.append(address)
            # Algunas versiones devuelven los valores en "address" separados por comas
            if not addresses and isinstance(data.get("address"), str):
                addresses = [ip.strip() for ip in data["address"].split(",") if ip.strip()]
        return addresses

    def _request(self, method: str, path: str, **kwargs: Dict[str, object]) -> Dict[str, object]:
        url = f"{self.api_url}/api/firewall/alias_util/{path}"
        response = requests.request(
            method=method,
            url=url,
            auth=(self.api_key, self.api_secret),
            timeout=self.timeout,
            verify=self.verify_ssl,
            **kwargs,
        )
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return {}


@dataclass
class Rule:
    """Regla que determina cuándo se dispara un bloqueo."""

    plugin: str
    signature_id: str
    severity: str
    description: str
    offenses_last_hour: int
    offenses_total: int
    block_seconds: int
    block_reason: Optional[str] = None
    rule_id: Optional[str] = None

    def matches_event(self, event: OffenseEvent) -> bool:
        return all(
            [
                self._matches_field(event.plugin, self.plugin),
                self._matches_field(event.signature_id, self.signature_id),
                self._matches_field(event.severity, self.severity),
                self._matches_field(event.description, self.description),
            ]
        )

    @property
    def reason(self) -> str:
        if self.block_reason:
            return self.block_reason
        if self.description != "*":
            return self.description
        return "Bloqueo automático"

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "id": self.rule_id,
            "plugin": self.plugin,
            "signature_id": self.signature_id,
            "severity": self.severity,
            "description": self.description,
            "offenses_last_hour": self.offenses_last_hour,
            "offenses_total": self.offenses_total,
            "block_seconds": self.block_seconds,
            "block_reason": self.block_reason,
        }

    @staticmethod
    def _matches_field(value: str, pattern: str) -> bool:
        return pattern == "*" or value == pattern


class RuleManager:
    """Gestiona ofensas y aplica reglas que generan bloqueos en el firewall."""

    def __init__(self, rules: List[Rule], firewall: Optional[InMemoryFirewall] = None) -> None:
        self.rules = list(rules)
        self.firewall = firewall or InMemoryFirewall()
        self.offenses: Dict[str, List[OffenseEvent]] = {}

    def add_offense(
        self,
        ip: str,
        plugin: str,
        signature_id: str,
        severity: str,
        description: str,
        timestamp: Optional[datetime] = None,
    ) -> Optional[FirewallBlock]:
        event_time = timestamp or datetime.utcnow()
        event = OffenseEvent(
            ip=ip,
            plugin=plugin,
            signature_id=signature_id,
            severity=severity,
            description=description,
            timestamp=event_time,
        )
        registry = self.offenses.setdefault(ip, [])
        registry.append(event)
        self._prune_old_offenses(ip)

        for rule in self.rules:
            if not rule.matches_event(event):
                continue
            last_hour, total = self._counts_for_rule(ip, rule)
            if last_hour >= rule.offenses_last_hour and total >= rule.offenses_total:
                return self.firewall.block_ip(ip, rule.block_seconds, rule.reason)
        return None

    def unblock_ip(self, ip: str) -> bool:
        return self.firewall.unblock_ip(ip)

    def get_block(self, ip: str) -> Optional[FirewallBlock]:
        return self.firewall.get_block(ip)

    def _counts_for_rule(self, ip: str, rule: Rule) -> tuple[int, int]:
        now = datetime.utcnow()
        last_hour_threshold = now - timedelta(hours=1)
        last_hour = 0
        total = 0
        for event in self.offenses.get(ip, []):
            if not rule.matches_event(event):
                continue
            total += 1
            if event.timestamp >= last_hour_threshold:
                last_hour += 1
        return last_hour, total

    def _prune_old_offenses(self, ip: str) -> None:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        events = self.offenses.get(ip, [])
        self.offenses[ip] = [event for event in events if event.timestamp >= cutoff]

    def list_blocks(self) -> List[FirewallBlock]:
        return self.firewall.list_blocks()
