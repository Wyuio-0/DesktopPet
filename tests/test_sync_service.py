"""测试罗德岛跨端协同网络服务与配对认证协议。"""

import time
import unittest
import urllib.request
import json

from pet.sync_service import RhodesSyncService, DataSyncEngine


class TestSyncService(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # 使用非默认端口进行测试
        cls.service = RhodesSyncService(
            device_name="Test-Rhodes-PC",
            http_port=29990,
            udp_port=29991
        )
        cls.service.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.service.stop()

    def test_01_api_info(self):
        """测试设备探测接口 /api/info。"""
        url = f"http://127.0.0.1:{self.service.http_port}/api/info"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data.get("device_type"), "pc")
            self.assertEqual(data.get("device_name"), "Test-Rhodes-PC")
            self.assertIn("device_id", data)

    def test_02_unauthorized_access(self):
        """测试未授权直接访问受保护接口被拦截 (401)。"""
        url = f"http://127.0.0.1:{self.service.http_port}/api/sync/pull"
        req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                self.fail("Should have raised HTTPError 401")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 401)

    def test_03_pairing_flow(self):
        """测试蓝牙式配对流程（发起 -> 确认 -> 授权 -> 获取 Token）。"""
        def auto_accept_callback(pair_req):
            self.assertEqual(pair_req.pin, "123456")
            self.assertEqual(pair_req.client_name, "Doctor-Android-Test")
            # 模拟用户在弹窗点击确认
            self.service.pair_manager.accept_request(pair_req.request_id)

        self.service.on_pair_request_callback = auto_accept_callback

        url = f"http://127.0.0.1:{self.service.http_port}/api/pair/request"
        payload = {
            "client_id": "test_android_001",
            "client_name": "Doctor-Android-Test",
            "pin": "123456",
            "client_port": 29992
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data.get("status"), "accepted")
            token = data.get("auth_token")
            self.assertTrue(token and token.startswith("rhodes_"))

            # 验证配对后可以成功调用受保护接口
            pull_url = f"http://127.0.0.1:{self.service.http_port}/api/sync/pull"
            pull_req = urllib.request.Request(
                pull_url,
                data=b"{}",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}"
                }
            )
            with urllib.request.urlopen(pull_req, timeout=2.0) as pull_resp:
                self.assertEqual(pull_resp.status, 200)
                sync_data = json.loads(pull_resp.read().decode("utf-8"))
                self.assertIn("schedule", sync_data)
                self.assertIn("exams", sync_data)
                self.assertIn("notes", sync_data)

    def test_04_data_packing(self):
        """测试本地数据打包引擎。"""
        pack = DataSyncEngine.pack_all_data()
        self.assertIn("schedule", pack)
        self.assertIn("exams", pack)
        self.assertIn("notes", pack)


if __name__ == "__main__":
    unittest.main()
