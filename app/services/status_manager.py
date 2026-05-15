import socket
import subprocess
import threading
import time
import json
from dataclasses import dataclass

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None

try:
    import urllib3  # type: ignore

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:  # pragma: no cover
    pass


@dataclass
class _PeerState:
    online: bool | None
    updated_at: float
    error_at: float | None = None


class StatusManager:
    """RustDesk 狀態管理器（只管 RustDesk peers）。

    - 使用 background polling thread 呼叫 `https://SERVER:PORT/api/peers`
    - 先透過 /api/login 取得 Bearer token，自動 renew
    - 將結果快取在記憶體，供 UI thread 透過 `get_cached_status()` 查詢
    - 永遠不在 tkinter 主線程做網路 IO
    """

    def __init__(
        self,
        server_host: str,
        api_port: int,
        *,
        timeout_s: int = 5,
        interval_s: int = 15,
        cache_grace_s: int = 60,
        admin_online_window_s: int = 60,
        status_change_confirm_polls: int = 4,
        unknown_confirm_polls: int = 20,
        min_state_hold_s: int = 8,
        headers: dict[str, str] | None = None,
        api_username: str = "",
        api_password: str = "",
    ):
        self.server_host = (server_host or "").strip()
        self.api_port = int(api_port) if api_port else 5014
        self.timeout_s = int(timeout_s)
        self.interval_s = int(interval_s)
        self.cache_grace_s = int(cache_grace_s)
        self.admin_online_window_s = max(5, int(admin_online_window_s))
        self.status_change_confirm_polls = max(1, int(status_change_confirm_polls))
        self.unknown_confirm_polls = max(1, int(unknown_confirm_polls))
        self.min_state_hold_s = max(0, int(min_state_hold_s))
        self.headers = dict(headers or {})
        self.api_username = (api_username or "").strip()
        self.api_password = api_password or ""
        self._token: str = ""
        self._token_expires_at: float = 0.0
        self._admin_token: str = ""
        self._admin_token_expires_at: float = 0.0

        self._lock = threading.Lock()
        self._states: dict[str, _PeerState] = {}
        self._pending: dict[str, tuple[bool | None, int]] = {}
        self._last_switch_at: dict[str, float] = {}
        self._peer_ids: list[str] = []
        self._running = False
        self._thread: threading.Thread | None = None

    def set_peer_ids(self, peer_ids: list[str]):
        cleaned: list[str] = []
        for pid in peer_ids or []:
            try:
                s = str(pid).strip()
            except Exception:
                s = ""
            if s:
                cleaned.append(s)
        with self._lock:
            self._peer_ids = cleaned
            alive = set(cleaned)
            self._states = {k: v for k, v in self._states.items() if k in alive}
            self._pending = {k: v for k, v in self._pending.items() if k in alive}
            self._last_switch_at = {
                k: v for k, v in self._last_switch_at.items() if k in alive
            }

    def start(self):
        if self._running:
            return
        self._running = True

        def _loop():
            while self._running:
                try:
                    self._poll_once()
                except Exception:
                    pass
                time.sleep(max(self.interval_s, 1))

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def get_cached_status(self, peer_id: str) -> bool | None:
        """回傳:
        - True: online
        - False: offline
        - None: unknown/error（由 UI 決定顏色）
        """
        pid = (str(peer_id).strip() if peer_id is not None else "").strip()
        if not pid:
            return None
        now = time.time()
        with self._lock:
            st = self._states.get(pid)
            if not st:
                return None
            # 若最近一次是 error，但在 grace 期間內，回傳上次 online/offline 避免 UI 閃爍
            if st.error_at is not None and st.online is not None:
                if now - st.updated_at <= self.cache_grace_s:
                    return st.online
                return None
            return st.online

    def _get_token(self) -> str:
        """登入取得 Bearer token，失效時自動 renew。"""
        if not self.api_username:
            return ""
        now = time.time()
        if self._token and now < self._token_expires_at:
            return self._token
        host = self.server_host
        port = self.api_port
        url = f"https://{host}:{port}/api/login"
        try:
            resp = requests.post(
                url,
                json={"username": self.api_username, "password": self.api_password},
                timeout=self.timeout_s,
                verify=False,
            )
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("access_token", "")
                if token:
                    self._token = token
                    # token 預設 1 小時有效，提前 5 分鐘 renew
                    self._token_expires_at = now + 3300
                    return self._token
        except Exception:
            pass
        self._token = ""
        self._token_expires_at = 0.0
        return ""

    def _get_admin_token(self) -> str:
        """後台登入取得 api-token，用於 /api/admin/* 查詢。"""
        if not self.api_username:
            return ""
        now = time.time()
        if self._admin_token and now < self._admin_token_expires_at:
            return self._admin_token

        host = self.server_host
        port = self.api_port
        url = f"https://{host}:{port}/api/admin/login"
        try:
            resp = requests.post(
                url,
                json={"username": self.api_username, "password": self.api_password},
                timeout=self.timeout_s,
                verify=False,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    payload = data.get("data", {})
                    if isinstance(payload, dict):
                        token = str(payload.get("token", "") or "")
                        if token:
                            self._admin_token = token
                            self._admin_token_expires_at = now + 3300
                            return self._admin_token
        except Exception:
            pass

        self._admin_token = ""
        self._admin_token_expires_at = 0.0
        return ""

    def _poll_once(self):
        host = self.server_host
        port = self.api_port
        if not host or port <= 0:
            return
        if requests is None:
            # 依賴缺失時不要崩潰，維持 unknown
            now = time.time()
            with self._lock:
                for pid in self._peer_ids:
                    prev = self._states.get(pid)
                    if prev:
                        prev.error_at = now
                        self._states[pid] = prev
                    else:
                        self._states[pid] = _PeerState(
                            online=None, updated_at=now, error_at=now
                        )
            return

        # 取得認證 token
        token = self._get_token()
        req_headers = dict(self.headers)
        if token:
            req_headers["Authorization"] = f"Bearer {token}"
        with self._lock:
            target_ids = list(self._peer_ids)

        # 分頁抓取所有 peers
        url = f"https://{host}:{port}/api/peers"
        online_map: dict[str, bool] = {}
        current_page = 1
        page_size = 100
        fetched_total = False
        try:
            while True:
                resp = requests.get(
                    url,
                    headers=req_headers,
                    params={"current": current_page, "pageSize": page_size},
                    timeout=self.timeout_s,
                    verify=False,
                )
                if resp.status_code == 401:
                    # token 過期，強制 renew 後重試一次
                    self._token = ""
                    self._token_expires_at = 0.0
                    token = self._get_token()
                    if token:
                        req_headers["Authorization"] = f"Bearer {token}"
                        resp = requests.get(
                            url,
                            headers=req_headers,
                            params={"current": current_page, "pageSize": page_size},
                            timeout=self.timeout_s,
                            verify=False,
                        )
                if resp.status_code != 200:
                    raise RuntimeError(f"bad status: {resp.status_code}")

                data = resp.json()
                # 支援兩種格式：純 list 或 {"total": N, "data": [...]}
                if isinstance(data, list):
                    peer_list = data
                    fetched_total = True
                elif isinstance(data, dict):
                    peer_list = data.get("data", [])
                    total = data.get("total", 0)
                    fetched_total = (current_page * page_size >= total)
                else:
                    break

                for p in peer_list:
                    if not isinstance(p, dict):
                        continue
                    pid = str(p.get("id", "")).strip()
                    if not pid:
                        continue
                    # 某些 RustDesk 版本的 /api/peers 只回 status, 不含 online。
                    if "online" in p:
                        online_map[pid] = bool(p.get("online", False))

                if fetched_total or not peer_list:
                    break
                current_page += 1

            # 某些部署下 /api/peers 可能只回局部資料，改查 admin 裝置列表補齊
            missing_targets = [pid for pid in target_ids if pid not in online_map]
            if missing_targets:
                admin_token = self._get_admin_token()
                if admin_token:
                    admin_headers = {"api-token": admin_token}
                    admin_page = 1
                    admin_page_size = 200
                    admin_total = None
                    while True:
                        admin_resp = requests.get(
                            f"https://{host}:{port}/api/admin/peer/list",
                            headers=admin_headers,
                            params={"page": admin_page, "page_size": admin_page_size},
                            timeout=self.timeout_s,
                            verify=False,
                        )
                        if admin_resp.status_code != 200:
                            break
                        admin_data = admin_resp.json()
                        if not isinstance(admin_data, dict) or int(admin_data.get("code", 1)) != 0:
                            break
                        payload = admin_data.get("data", {})
                        if not isinstance(payload, dict):
                            break
                        peer_list = payload.get("list", [])
                        if admin_total is None:
                            try:
                                admin_total = int(payload.get("total", 0) or 0)
                            except Exception:
                                admin_total = 0

                        now_ts = int(time.time())
                        for p in peer_list:
                            if not isinstance(p, dict):
                                continue
                            pid = str(p.get("id", "")).strip()
                            if not pid:
                                continue
                            try:
                                last_online = int(p.get("last_online_time", 0) or 0)
                            except Exception:
                                last_online = 0
                            # 後台列表沒有直接 online 欄位，使用最近心跳時間判定
                            if pid not in online_map:
                                online_map[pid] = bool(
                                    last_online > 0
                                    and (now_ts - last_online) <= self.admin_online_window_s
                                )

                        if not peer_list:
                            break
                        if admin_total and admin_page * admin_page_size >= admin_total:
                            break
                        admin_page += 1

            # 再次 fallback：讀 /api/ab 的 peers（僅在仍有未覆蓋目標時）
            missing_targets = [pid for pid in target_ids if pid not in online_map]
            if missing_targets:
                ab_resp = requests.get(
                    f"https://{host}:{port}/api/ab",
                    headers=req_headers,
                    timeout=self.timeout_s,
                    verify=False,
                )
                if ab_resp.status_code == 200:
                    ab_data = ab_resp.json()
                    raw = ab_data.get("data", "") if isinstance(ab_data, dict) else ""
                    parsed = {}
                    if isinstance(raw, str) and raw.strip():
                        parsed = json.loads(raw)
                    elif isinstance(raw, dict):
                        parsed = raw
                    peers = parsed.get("peers", []) if isinstance(parsed, dict) else []
                    for p in peers:
                        if not isinstance(p, dict):
                            continue
                        pid = str(p.get("id", "")).strip()
                        if not pid:
                            continue
                        if pid not in online_map:
                            online_map[pid] = bool(p.get("online", False))

        except Exception:
            # 記錄 error（但不清掉舊 cache）
            now = time.time()
            with self._lock:
                for pid in self._peer_ids:
                    prev = self._states.get(pid)
                    if prev:
                        prev.error_at = now
                        self._states[pid] = prev
                    else:
                        self._states[pid] = _PeerState(
                            online=None, updated_at=now, error_at=now
                        )
            return

        now = time.time()
        with self._lock:
            target_ids = list(self._peer_ids)
            for pid in target_ids:
                raw_online: bool | None = online_map.get(pid, None)
                prev = self._states.get(pid)

                # 初次建立狀態：直接採用目前觀測值
                if prev is None:
                    self._states[pid] = _PeerState(
                        online=raw_online,
                        updated_at=now,
                        error_at=(now if raw_online is None else None),
                    )
                    self._last_switch_at[pid] = now
                    self._pending.pop(pid, None)
                    continue

                stable_online = prev.online
                if raw_online == stable_online:
                    # 與目前穩定狀態一致：清除 pending，直接更新時間
                    self._states[pid] = _PeerState(
                        online=stable_online,
                        updated_at=now,
                        error_at=None,
                    )
                    self._pending.pop(pid, None)
                    continue

                # 防抖：需連續 N 次觀測到相同新狀態才切換
                pend_value, pend_count = self._pending.get(pid, (None, 0))
                if pend_value == raw_online:
                    pend_count += 1
                else:
                    pend_value = raw_online
                    pend_count = 1
                self._pending[pid] = (pend_value, pend_count)

                confirm_needed = (
                    self.unknown_confirm_polls
                    if raw_online is None
                    else self.status_change_confirm_polls
                )

                if pend_count >= confirm_needed:
                    last_switched = self._last_switch_at.get(pid, 0.0)
                    if (now - last_switched) >= self.min_state_hold_s:
                        self._states[pid] = _PeerState(
                            online=raw_online,
                            updated_at=now,
                            error_at=(now if raw_online is None else None),
                        )
                        self._last_switch_at[pid] = now
                        self._pending.pop(pid, None)
                    else:
                        # 距離上次切換太近：維持穩定狀態，避免瞬時反向抖動
                        self._states[pid] = _PeerState(
                            online=stable_online,
                            updated_at=now,
                            error_at=(now if raw_online is None else None),
                        )
                else:
                    # 尚未達到切換門檻：維持目前穩定狀態
                    self._states[pid] = _PeerState(
                        online=stable_online,
                        updated_at=now,
                        error_at=(now if raw_online is None else None),
                    )


def ping_host(host: str) -> bool:
    """Windows ping 一次作為最小 fallback。"""
    try:
        host = (host or "").strip()
        if not host:
            return False
        result = subprocess.run(
            ["ping", "-n", "1", "-w", "800", host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def tcp_check(host: str, port: int) -> bool:
    try:
        host = (host or "").strip()
        if not host:
            return False
        if not isinstance(port, int) or port <= 0:
            return False
        with socket.create_connection((host, port), timeout=1):
            return True
    except Exception:
        return False

