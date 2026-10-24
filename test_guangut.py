"""Unit & Integration Tests for GuangutVPN (Regions, OpenVPN 2.6+ Patcher, Harvester)."""

from __future__ import annotations
import base64
import unittest

from guangut.harvester import filter_servers, parse_vpngate_csv
from guangut.patcher import extract_legacy_cipher, extract_proto_and_remote, patch_ovpn_config
from guangut.regions import classify_us_region, match_us_region, normalize_us_state


class TestGuangutVPN(unittest.TestCase):
    def test_us_state_and_region_classification(self) -> None:
        self.assertEqual(normalize_us_state("California"), "CA")
        self.assertEqual(normalize_us_state("NY"), "NY")
        self.assertEqual(normalize_us_state("Virginia"), "VA")
        self.assertEqual(normalize_us_state("Texas"), "TX")

        self.assertEqual(classify_us_region("NY"), "east")
        self.assertEqual(classify_us_region("VA"), "east")
        self.assertEqual(classify_us_region("TX"), "central")
        self.assertEqual(classify_us_region("IL"), "central")
        self.assertEqual(classify_us_region("CA"), "west")
        self.assertEqual(classify_us_region("WA"), "west")

    def test_match_us_region(self) -> None:
        srv_ny = {"cc": "US", "state_code": "NY", "region": "New York"}
        srv_tx = {"cc": "US", "state_code": "TX", "region": "Texas"}
        srv_ca = {"cc": "US", "state_code": "CA", "region": "California"}

        self.assertTrue(match_us_region(srv_ny, "east"))
        self.assertTrue(match_us_region(srv_ny, "northeast"))
        self.assertFalse(match_us_region(srv_ny, "west"))

        self.assertTrue(match_us_region(srv_tx, "central"))
        self.assertTrue(match_us_region(srv_tx, "south"))

        self.assertTrue(match_us_region(srv_ca, "west"))
        self.assertTrue(match_us_region(srv_ca, "all"))

    def test_openvpn_26_patcher(self) -> None:
        legacy_ovpn = """
client
dev tun
proto tcp-client
remote 198.51.100.42 443
cipher AES-128-CBC
auth SHA1
win-sys env
register-dns
route-delay 2
<ca>
FAKE_CERT
</ca>
"""
        proto, host, port = extract_proto_and_remote(legacy_ovpn)
        self.assertEqual(proto, "tcp")
        self.assertEqual(host, "198.51.100.42")
        self.assertEqual(port, 443)
        self.assertEqual(extract_legacy_cipher(legacy_ovpn), "AES-128-CBC")

        srv = {
            "host": "vpn-us-test",
            "ip": host,
            "port": port,
            "proto": proto,
            "country": "United States",
            "state_code": "VA",
            "city": "Ashburn",
            "cfg": legacy_ovpn,
        }
        patched = patch_ovpn_config(srv)
        # Verify Windows-only directives are stripped
        self.assertNotIn("win-sys", patched)
        self.assertNotIn("register-dns", patched)
        # Verify OpenVPN 2.6+ data-ciphers and fallback are injected
        self.assertIn("data-ciphers AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305:AES-256-CBC:AES-128-CBC", patched)
        self.assertIn("data-ciphers-fallback AES-128-CBC", patched)
        self.assertIn("redirect-gateway def1", patched)
        self.assertIn("block-ipv6", patched)

    def test_filter_servers_us_and_global(self) -> None:
        servers = [
            {"host": "us-va", "ip": "1.1.1.1", "cc": "US", "country": "United States", "state_code": "VA", "region": "Virginia", "us_region": "east", "city": "Ashburn", "proto": "udp", "ping": 15, "speed": 90000000, "score": 500, "live_ms": 18.0},
            {"host": "us-ca", "ip": "2.2.2.2", "cc": "US", "country": "United States", "state_code": "CA", "region": "California", "us_region": "west", "city": "Los Angeles", "proto": "tcp", "ping": 40, "speed": 80000000, "score": 400, "live_ms": 42.0},
            {"host": "jp-tyo", "ip": "3.3.3.3", "cc": "JP", "country": "Japan", "state_code": "", "region": "Tokyo", "us_region": "", "city": "Tokyo", "proto": "udp", "ping": 95, "speed": 120000000, "score": 800, "live_ms": 98.0},
        ]
        # Default US filter
        us_all, _ = filter_servers(servers, country="US")
        self.assertEqual(len(us_all), 2)

        # Part of US: US-West
        us_west, _ = filter_servers(servers, country="US", us_region="west")
        self.assertEqual(len(us_west), 1)
        self.assertEqual(us_west[0]["state_code"], "CA")

        # Part of US: Specific State VA
        us_va, _ = filter_servers(servers, country="US", state="VA")
        self.assertEqual(len(us_va), 1)
        self.assertEqual(us_va[0]["city"], "Ashburn")

        # Other country option: Japan
        jp, _ = filter_servers(servers, country="JP")
        self.assertEqual(len(jp), 1)
        self.assertEqual(jp[0]["cc"], "JP")


if __name__ == "__main__":
    unittest.main()

