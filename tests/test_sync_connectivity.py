"""An unreachable LAN peer must preserve trust and permit retry without re-pairing."""
from unittest.mock import Mock

import pytest

from pet import sync_service as sync


@pytest.fixture
def peers(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    client = sync.RhodesSyncService("client", http_port=0, udp_port=0)
    receiver = sync.RhodesSyncService("receiver", http_port=0, udp_port=0)
    client.device_id, receiver.device_id = "client", "receiver"
    client.pair_manager = sync.PairManager(str(tmp_path / "client.json"))
    receiver.pair_manager = sync.PairManager(str(tmp_path / "receiver.json"))
    client.start()
    receiver.start()
    receiver.on_pair_request_callback = lambda request: receiver.pair_manager.accept_request(request.request_id)
    try:
        yield client, receiver
    finally:
        client.stop()
        receiver.stop()


def test_offline_peer_preserves_trust_and_retry_uses_original_credentials(peers, monkeypatch):
    client, receiver = peers
    invitation = receiver.create_pairing_invite()
    ok, _, result = client.request_pair("127.0.0.1", receiver.http_port, pairing_secret=invitation)
    assert ok
    token = result["auth_token"]
    trusted = client.pair_manager.get_trusted_devices()
    apply = Mock(return_value={"schedule": True})
    monkeypatch.setattr(sync.DataSyncEngine, "apply_data", apply)
    receiver.stop()
    ok, message = client.sync_pull("127.0.0.1", receiver.http_port, token)
    assert not ok and "无法连接" in message and "重新配对" not in message
    assert client.pair_manager.get_trusted_devices() == trusted
    apply.assert_not_called()
    receiver.start()
    assert client.sync_pull("127.0.0.1", receiver.http_port, token)[0]
    apply.assert_called_once()


def test_unreachable_pair_target_is_not_reported_as_wrong_secret(peers):
    client, receiver = peers
    invitation = receiver.create_pairing_invite()
    receiver.stop()
    ok, message, result = client.request_pair("127.0.0.1", receiver.http_port, pairing_secret=invitation)
    assert not ok and result is None and "无法连接" in message
    assert "重新配对" not in message and not client.pair_manager.get_trusted_devices()
