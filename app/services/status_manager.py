import socket
import subprocess
import threading
import time
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
    """Background RustDesk status polling with staged UI-visible updates."""

    def __init__(
        self,
        server_host: str,
        api_port: int,
        *,
        timeout_s: float = 5,
        first_poll_timeout_s: float = 2.0,
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
        self.timeout_s = float(timeout_s)
        self.first_poll_timeout_s = float(first_poll_timeout_s)
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
        self._poll_count = 0
        self._http_session = None

    def _http(self):
        """Reuse one HTTPS connection so regular polls avoid TLS cold starts."""
        if self._http_session is None:
            session_factory = getattr(requests, "Session", None) if requests else None
            self._http_session = session_factory() if callable(session_factory) else requests
        return self._http_session

    @staticmethod
    def _coerce_online(peer: dict) -> bool | None:
        """Accept common RustDesk API online/status field variants."""
        for key in ("online", "is_online", "isOnline"):
            if key in peer:
                return bool(peer.get(key))

        for key in ("status", "state", "connection_status"):
            if key not in peer:
                continue
            value = peer.get(key)
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return int(value) > 0
            text = str(value or "").strip().lower()
            if text in ("online", "connected", "ready", "1", "true", "yes"):
                return True
            if text in ("offline", "disconnected", "0", "false", "no"):
                return False
        return None

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
                sleep_s = max(self.interval_s, 1)
                if not self._has_concrete_status():
                    sleep_s = 0.2
                time.sleep(sleep_s)

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        session = self._http_session
        self._http_session = None
        close = getattr(session, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass

    def get_cached_status(self, peer_id: str) -> bool | None:
        """Return True for online, False for offline, None for unknown/error."""
        pid = (str(peer_id).strip() if peer_id is not None else "").strip()
        if not pid:
            return None
        now = time.time()
        with self._lock:
            st = self._states.get(pid)
            if not st:
                return None
            if st.error_at is not None and st.online is not None:
                if now - st.updated_at <= self.cache_grace_s:
                    return st.online
                return None
            return st.online

    def _has_concrete_status(self) -> bool:
        with self._lock:
            return any(st.online is not None for st in self._states.values())

    def _request_timeout(self) -> float:
        if self._poll_count == 0 or not self._has_concrete_status():
            return max(0.5, self.first_poll_timeout_s)
        return max(0.5, self.timeout_s)

    def _get_token(self) -> str:
        if not self.api_username or requests is None:
            return ""
        now = time.time()
        if self._token and now < self._token_expires_at:
            return self._token
        url = f"https://{self.server_host}:{self.api_port}/api/login"
        try:
            resp = self._http().post(
                url,
                json={"username": self.api_username, "password": self.api_password},
                timeout=self._request_timeout(),
                verify=False,
            )
            if resp.status_code == 200:
                token = resp.json().get("access_token", "")
                if token:
                    self._token = token
                    self._token_expires_at = now + 3300
                    return self._token
        except Exception:
            pass
        self._token = ""
        self._token_expires_at = 0.0
        return ""

    def _get_admin_token(self) -> str:
        if not self.api_username or requests is None:
            return ""
        now = time.time()
        if self._admin_token and now < self._admin_token_expires_at:
            return self._admin_token

        url = f"https://{self.server_host}:{self.api_port}/api/admin/login"
        try:
            resp = self._http().post(
                url,
                json={"username": self.api_username, "password": self.api_password},
                timeout=self._request_timeout(),
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

    def _mark_poll_error(self):
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

    def _apply_status_snapshot(
        self,
        online_map: dict[str, bool],
        *,
        include_missing: bool,
    ):
        """Apply known states immediately; optionally mark missing peers unknown."""
        now = time.time()
        with self._lock:
            target_ids = list(self._peer_ids)
            if include_missing:
                apply_ids = target_ids
            else:
                target_set = set(target_ids)
                apply_ids = [pid for pid in online_map if pid in target_set]

            for pid in apply_ids:
                raw_online: bool | None = online_map.get(pid, None)
                prev = self._states.get(pid)

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
                    self._states[pid] = _PeerState(
                        online=stable_online,
                        updated_at=now,
                        error_at=None,
                    )
                    self._pending.pop(pid, None)
                    continue

                if stable_online is None and raw_online is not None:
                    self._states[pid] = _PeerState(
                        online=raw_online,
                        updated_at=now,
                        error_at=None,
                    )
                    self._last_switch_at[pid] = now
                    self._pending.pop(pid, None)
                    continue

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
                        self._states[pid] = _PeerState(
                            online=stable_online,
                            updated_at=now,
                            error_at=(now if raw_online is None else None),
                        )
                else:
                    self._states[pid] = _PeerState(
                        online=stable_online,
                        updated_at=now,
                        error_at=(now if raw_online is None else None),
                    )

    def _fetch_admin_missing(
        self,
        online_map: dict[str, bool],
        target_ids: list[str],
    ) -> bool:
        target_set = set(target_ids)
        if not target_set:
            return True
        admin_token = self._get_admin_token()
        if not admin_token:
            return False

        admin_headers = {"api-token": admin_token}
        admin_page = 1
        admin_page_size = 100
        admin_total = None

        while True:
            admin_resp = self._http().get(
                f"https://{self.server_host}:{self.api_port}/api/admin/peer/list",
                headers=admin_headers,
                params={"page": admin_page, "page_size": admin_page_size},
                timeout=self._request_timeout(),
                verify=False,
            )
            if admin_resp.status_code != 200:
                return False
            admin_data = admin_resp.json()
            if not isinstance(admin_data, dict) or int(admin_data.get("code", 1)) != 0:
                return False
            payload = admin_data.get("data", {})
            if not isinstance(payload, dict):
                return False
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
                if not pid or pid not in target_set:
                    continue
                try:
                    last_online = int(p.get("last_online_time", 0) or 0)
                except Exception:
                    last_online = 0
                is_online = bool(
                    last_online > 0
                    and (now_ts - last_online) <= self.admin_online_window_s
                )
                if online_map.get(pid) is True:
                    continue
                online_map[pid] = is_online

            self._apply_status_snapshot(online_map, include_missing=False)

            if not peer_list:
                return True
            if admin_total and admin_page * admin_page_size >= admin_total:
                return True
            admin_page += 1

    def _poll_once(self):
        if not self.server_host or self.api_port <= 0:
            return
        if requests is None:
            self._mark_poll_error()
            self._poll_count += 1
            return

        try:
            with self._lock:
                target_ids = list(self._peer_ids)

            online_map: dict[str, bool] = {}
            complete = self._fetch_admin_missing(online_map, target_ids)
            if complete:
                self._apply_status_snapshot(online_map, include_missing=True)
            else:
                self._mark_poll_error()
        except Exception:
            self._mark_poll_error()
        finally:
            self._poll_count += 1


def ping_host(host: str) -> bool:
    """Run one Windows ping as a small fallback."""
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
