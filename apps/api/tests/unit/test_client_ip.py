"""IP del cliente tras los proxies propios, y origen para limitar los SMS."""

import pytest
from starlette.requests import Request

from app.infrastructure.api.middlewares.request_context import client_ip, rate_limit_origin


def request(forwarded: str | None, peer: str = "10.0.0.1") -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded is not None else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


class TestClientIp:
    def test_behind_cloud_run_the_client_is_the_last_hop(self) -> None:
        assert client_ip(request("83.45.12.9"), 1) == "83.45.12.9"

    def test_a_forged_header_does_not_replace_the_real_ip(self) -> None:
        # El cliente manda su propia cabecera; Cloud Run anade la IP real al final.
        assert client_ip(request("1.2.3.4, 83.45.12.9"), 1) == "83.45.12.9"

    def test_with_a_load_balancer_in_front_it_is_second_from_the_right(self) -> None:
        assert client_ip(request("1.2.3.4, 83.45.12.9, 34.1.1.1"), 2) == "83.45.12.9"

    def test_without_the_header_it_is_the_peer(self) -> None:
        assert client_ip(request(None, peer="127.0.0.1"), 1) == "127.0.0.1"

    def test_with_fewer_hops_than_expected_the_header_is_not_trusted(self) -> None:
        assert client_ip(request("1.2.3.4"), 2) == "10.0.0.1"

    def test_with_no_trusted_proxy_the_header_is_ignored(self) -> None:
        assert client_ip(request("1.2.3.4"), 0) == "10.0.0.1"


class TestRateLimitOrigin:
    def test_ipv4_is_the_address(self) -> None:
        assert rate_limit_origin("83.45.12.9") == "83.45.12.9"

    def test_ipv6_is_grouped_by_its_64_network(self) -> None:
        # Un cliente IPv6 tiene un /64 entero: rotar la direccion no abre cupo.
        a = rate_limit_origin("2a01:4f8:1:2::1")
        b = rate_limit_origin("2a01:4f8:1:2:ffff:ffff:ffff:ffff")
        assert a == b == "2a01:4f8:1:2::/64"

    @pytest.mark.parametrize("value", [None, "no-es-una-ip"])
    def test_an_unreadable_origin_shares_one_quota(self, value: str | None) -> None:
        # Si no se limitara, mandar basura en la cabecera saltaria el limite.
        assert rate_limit_origin(value) == "unknown"
