import os
import time
import unittest
from datetime import datetime, timedelta

from videorama.firewall import (
    FirewallBlock,
    InMemoryFirewall,
    OPNsenseFirewall,
    Rule,
    RuleManager,
)


def _opnsense_env() -> dict:
    url = os.getenv("OPNSENSE_API_URL")
    key = os.getenv("OPNSENSE_API_KEY")
    secret = os.getenv("OPNSENSE_API_SECRET")
    alias = os.getenv("OPNSENSE_BLOCK_ALIAS", "videorama_blocks")
    verify_ssl = os.getenv("OPNSENSE_VERIFY_SSL", "true").lower() not in {"0", "false", "no"}
    if url and key and secret:
        return {
            "api_url": url,
            "api_key": key,
            "api_secret": secret,
            "alias": alias,
            "verify_ssl": verify_ssl,
        }
    return {}


class RuleManagerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.firewall = InMemoryFirewall()
        self.catch_all = Rule(
            plugin="*",
            signature_id="*",
            severity="*",
            description="*",
            offenses_last_hour=2,
            offenses_total=2,
            block_seconds=120,
            block_reason="Bloqueo genérico",
        )
        self.specific = Rule(
            plugin="auth",
            signature_id="login_failed",
            severity="high",
            description="*",
            offenses_last_hour=3,
            offenses_total=3,
            block_seconds=300,
            block_reason="Demasiados fallos de login",
        )
        self.manager = RuleManager([self.specific, self.catch_all], firewall=self.firewall)

    def test_catch_all_rule_triggers_block(self) -> None:
        ip = "10.0.0.1"
        # Primer evento no bloquea aún
        block = self.manager.add_offense(ip, plugin="core", signature_id="x", severity="low", description="prueba")
        self.assertIsNone(block)
        self.assertIsNone(self.firewall.get_block(ip))

        # Segundo evento cumple con el umbral de la regla catch-all
        block = self.manager.add_offense(ip, plugin="core", signature_id="y", severity="low", description="prueba")
        self.assertIsInstance(block, FirewallBlock)
        self.assertTrue(self.firewall.get_block(ip))

    def test_specific_rule_needs_three_events_in_last_hour(self) -> None:
        ip = "10.0.0.99"
        timestamp_old = datetime.utcnow() - timedelta(hours=2)
        # Eventos antiguos no cuentan en la ventana de una hora
        self.manager.add_offense(
            ip,
            plugin="auth",
            signature_id="login_failed",
            severity="high",
            description="antiguo",
            timestamp=timestamp_old,
        )
        self.manager.add_offense(
            ip,
            plugin="auth",
            signature_id="login_failed",
            severity="high",
            description="antiguo",
            timestamp=timestamp_old,
        )
        self.assertIsNone(self.firewall.get_block(ip))

        # Tres eventos recientes disparan la regla específica
        for i in range(3):
            block = self.manager.add_offense(
                ip,
                plugin="auth",
                signature_id="login_failed",
                severity="high",
                description=f"intento {i}",
            )
        self.assertIsInstance(block, FirewallBlock)
        self.assertTrue(self.firewall.get_block(ip))

    def test_unblock_ip_removes_firewall_entry(self) -> None:
        ip = "192.168.1.10"
        self.manager.add_offense(ip, plugin="core", signature_id="a", severity="low", description="uno")
        self.manager.add_offense(ip, plugin="core", signature_id="b", severity="low", description="dos")
        self.assertTrue(self.firewall.get_block(ip))
        removed = self.manager.unblock_ip(ip)
        self.assertTrue(removed)
        self.assertIsNone(self.firewall.get_block(ip))
        self.assertEqual([], self.manager.list_blocks())


@unittest.skipUnless(_opnsense_env(), "Entorno OPNsense no configurado")
class OPNsenseFirewallIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = _opnsense_env()
        self.firewall = OPNsenseFirewall(**self.config)

    def test_block_and_unblock_alias(self) -> None:
        ip = "203.0.113.56"
        reason = "Prueba Videorama"

        # Limpia la IP antes de empezar
        self.firewall.unblock_ip(ip)

        block = self.firewall.block_ip(ip, seconds=60, reason=reason)
        self.assertIsInstance(block, FirewallBlock)
        fetched = self.firewall.get_block(ip)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.reason, f"Alias {self.config['alias']}")

        removed = self.firewall.unblock_ip(ip)
        self.assertTrue(removed)
        time.sleep(1)
        self.assertIsNone(self.firewall.get_block(ip))


if __name__ == "__main__":
    unittest.main()
