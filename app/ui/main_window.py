import tkinter as tk
import subprocess
import os
import stat
import sys
import shutil
import uuid
import threading

# 移除 Excel 相關套件以減少打包大小

from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk
from tkinter import messagebox

from app.platform.win_clipboard import (
    paste_via_keyboard_and_enter as _paste_via_keyboard_and_enter,
)
from app.platform.win_clipboard import set_clipboard_text as _set_clipboard_text
from app.platform.win_process import launch_process
from app.platform.win_window import build_unilink_for_id as _build_unilink_for_id
from app.platform.win_window import close_window as _close_window
from app.platform.win_window import find_window_for_id as _find_window_for_id
from app.platform.win_window import force_foreground as _force_foreground
from app.platform.win_window import is_rustdesk_connection_error_dialog_open as _is_rustdesk_connection_error_dialog_open
from app.platform.win_window import is_rustdesk_id_not_found_dialog_open as _is_rustdesk_id_not_found_dialog_open
from app.platform.win_window import send_unilink_to_flutter_runner as _send_unilink_to_flutter_runner
from app.platform.win_window import send_unilink_via_copydata as _send_unilink_via_copydata
from app.platform.win_window import try_uia_set_password as _try_uia_set_password
from app.platform.win_window import wait_and_input_password as _wait_and_input_password
from app.repositories import csv_repo, json_repo
from app.services import status_service
from app.security.des_compat import encrypt_tightvnc_password
from app.ui import common_widgets as ui_common
from app.ui import dialogs as ui_dialogs
from app.ui.tabs.anydesk_tab import AnyDesk
from app.ui.tabs.rustdesk_tab import RustDesk
from app.ui.tabs.tightvnc_tab import TightVNC
from app.utils.paths import BASE_DIR, EXE_DIR, get_app_path, get_writable_dir, resource_path
from app.utils.text import client_key as _client_key
from app.utils.text import format_client_label_text as _format_client_label_text
from app.utils.text import normalize_client_fields
from app.utils.text import sanitize_tag as _sanitize_tag
from app.services.status_manager import StatusManager, ping_host, tcp_check


STATUS_BUTTONS = {}

STATUS_COLORS = {
    "online": "#ff4444",
    "offline": "#00cc66",
    "error": "#666666",
}

PASSWORD_KEYIN_DELAY_S = 0.2
rustdesk_status_manager: StatusManager | None = None


def log_and_show(title: str, msg: str, level: str = "warning"):
    """簡單的 log + 顯示 helper。level 可以是 'info'/'warning'/'error'。"""
    # console logging removed to avoid terminal output
    try:
        if level == "error":
            messagebox.showerror(title, msg)
        elif level == "info":
            messagebox.showinfo(title, msg)
        else:
            messagebox.showwarning(title, msg)
    except Exception:
        pass


    # debug logging removed per user request: delete function and all call sites


# 預設值(可用環境變數覆寫)
# 將可執行檔統一放到專案內的 `exe` 資料夾,可由環境變數覆寫
# rustdesk 可執行檔路徑(相對或絕對)
RUSTDESK_APP = os.getenv("RUSTDESK_APP", str(EXE_DIR / "rustdesk.exe"))
# 用於產生 RustDesk2.toml 的 rendezvous server 與 key(從設定檔讀取)
RUSTDESK_HOST = ""
RUSTDESK_KEY = ""

# 是否在寫入 peers/{id}.toml 後把檔案設為唯讀(避免 RustDesk 立即覆寫)
RUSTDESK_SET_PEER_READONLY = False

# AnyDesk / TightVNC 可執行檔路徑
ANYDESK_APP = os.getenv("ANYDESK_APP", str(EXE_DIR / "AnyDesk.exe"))
TIGHTVNC_APP = os.getenv("TIGHTVNC_APP", str(EXE_DIR / "TightVNC.exe"))

# Password paste helper removed per request: automated paste/Enter actions
# The repository may still contain helper binaries/scripts, but this application
# no longer invokes any automated password pasting.


def create_header_row(
    parent,
    on_connect,
    with_port=False,
    default_port="5900",
    section="",
    show_server_config=False,
):
    return ui_common.create_header_row(
        parent,
        on_connect=on_connect,
        with_port=with_port,
        default_port=default_port,
        section=section,
        show_server_config=show_server_config,
        on_export=export_to_csv,
        on_import=import_csv_with_refresh,
        on_show_server_config=show_server_config_dialog,
    )


def load_server_config() -> dict:
    return json_repo.load_server_config()


def get_default_server_config() -> dict:
    return json_repo.get_default_server_config()


def save_server_config(config: dict) -> bool:
    return json_repo.save_server_config(config)


def show_server_config_dialog():
    icon_filenames = ["lioil.icns"] if sys.platform == "darwin" else ["lioil.ico"]
    icon_candidates = []
    for icon_name in icon_filenames:
        icon_candidates.extend(
            [
                resource_path(icon_name),
                get_app_path(icon_name),
                os.path.join(str(BASE_DIR), icon_name),
            ]
        )

    def _on_config_saved(new_config: dict):
        global server_config, RUSTDESK_HOST, RUSTDESK_KEY
        server_config = dict(new_config)
        RUSTDESK_HOST = str(new_config.get("server", "") or "").strip()
        RUSTDESK_KEY = str(new_config.get("key", "") or "")

    ui_dialogs.show_server_config_dialog(
        gui=gui,
        load_server_config=load_server_config,
        save_server_config=save_server_config,
        log_and_show=log_and_show,
        on_config_saved=_on_config_saved,
        on_restart_status_manager=_restart_rustdesk_status_manager_from_config,
        icon_candidates=icon_candidates,
    )


def ensure_json_exists() -> bool:
    return json_repo.ensure_json_exists()


def read_clients_from_json(section: str) -> list[dict]:
    return json_repo.read_clients_from_json(section)


def _dump_json_server_first(data: dict) -> str:
    return json_repo.dump_json_server_first(data)


def write_clients_to_json(section: str, clients: list[dict]) -> bool:
    return json_repo.write_clients_to_json(section, clients)


def export_to_csv(section: str, file_path: str | None = None) -> bool:
    """將指定區段的資料匯出為 CSV 檔案。

    參數:
    - section: 區段名稱 ('rustdesk', 'anydesk', 'tightvnc')
    - file_path: 匯出檔案路徑，若為 None 則使用檔案對話框

    回傳: 匯出成功與否
    """
    if file_path is None:
        from tkinter import filedialog

        file_path = filedialog.asksaveasfilename(
            title=f"匯出 {section} 資料為 CSV",
            defaultextension=".csv",
            filetypes=[("CSV 檔案", "*.csv"), ("所有檔案", "*.*")],
        )
        if not file_path:
            return False

    if file_path is None:
        return False

    ok, detail = csv_repo.export_to_csv(section, file_path)
    if not ok and detail == "no_data":
        log_and_show("無資料", f"{section} 區段沒有資料可以匯出", "warning")
        return False

    if ok:
        count = int(detail)
        log_and_show(
            "匯出成功",
            f"已成功匯出 {count} 筆 {section} 資料到 {file_path}",
            "info",
        )
        return True

    log_and_show("匯出失敗", f"匯出 CSV 時發生錯誤：{detail}", "error")
    return False


def import_from_csv(section: str, file_path: str | None = None) -> bool:
    """從 CSV 檔案匯入資料到指定區段。

    參數:
    - section: 區段名稱 ('rustdesk', 'anydesk', 'tightvnc')
    - file_path: 匯入檔案路徑，若為 None 則使用檔案對話框

    回傳: 匯入成功與否
    """
    if file_path is None:
        from tkinter import filedialog

        file_path = filedialog.askopenfilename(
            title=f"匯入 {section} 資料從 CSV",
            filetypes=[("CSV 檔案", "*.csv"), ("所有檔案", "*.*")],
        )
        if not file_path:
            return False

    if file_path is None:
        return False

    ok, detail = csv_repo.import_from_csv(section, file_path)
    if ok:
        count = int(detail)
        log_and_show("匯入成功", f"已成功匯入 {count} 筆 {section} 資料", "info")
        return True
    if detail == "no_valid_data":
        log_and_show("無有效資料", "CSV 檔案中沒有找到有效的客戶資料", "warning")
        return False
    if detail == "write_failed":
        log_and_show("匯入失敗", "寫入 JSON 資料庫時發生錯誤", "error")
        return False

    log_and_show("匯入失敗", f"讀取 CSV 檔案時發生錯誤：{detail}", "error")
    return False


# Excel 遷移功能已移除，現在使用純 JSON 架構


# Excel 讀取功能已移除，現在使用純 JSON 架構


# Excel 相關功能已移除以減少打包大小


# `extra` field removed from client dicts; helper not needed anymore.


def create_client_buttons(
    container,
    clients: list[dict],
    on_connect,
    section: str,
    cols: int = 10,
    btn_font=("微軟正黑體", 10),
):
    return ui_common.create_client_buttons(
        container,
        clients,
        on_connect,
        section=section,
        status_buttons=STATUS_BUTTONS,
        show_context_menu=show_context_menu,
        normalize_client_fields=normalize_client_fields,
        sanitize_tag=_sanitize_tag,
        format_client_label_text=_format_client_label_text,
        client_key=_client_key,
        cols=cols,
        btn_font=btn_font,
    )


def show_context_menu(event, section: str, client: dict | None, container, on_connect):
    """顯示右鍵選單"""
    ui_dialogs.show_client_context_menu(
        event,
        container=container,
        client=client,
        on_edit=lambda: edit_client(section, client, container, on_connect),
        on_delete=lambda: delete_client(section, client, container, on_connect),
        on_add=lambda: add_client(section, container, on_connect),
    )


def edit_client(section: str, client: dict, container, on_connect):
    """編輯客戶資料"""
    ui_dialogs.edit_client_dialog(
        gui=gui,
        section=section,
        client=client,
        container=container,
        on_connect=on_connect,
        read_clients_from_json=read_clients_from_json,
        write_clients_to_json=write_clients_to_json,
        refresh_section_buttons=refresh_section_buttons,
        delete_client=delete_client,
        log_and_show=log_and_show,
    )


def add_client(section: str, container, on_connect):
    """新增客戶"""
    new_client = {"tag": "", "id": "", "pwd": "", "port": ""}
    edit_client(section, new_client, container, on_connect)


def delete_client(section: str, client: dict, container, on_connect):
    """刪除客戶"""
    if not messagebox.askyesno(
        "確認刪除", f"確定要刪除客戶 '{client.get('tag', '')}' 嗎？"
    ):
        return

    # 讀取現有資料
    clients = read_clients_from_json(section)

    # 找到並移除客戶
    original_length = len(clients)
    clients = [
        c
        for c in clients
        if not (
            c.get("tag") == client.get("tag")
            and c.get("id") == client.get("id")
            and c.get("pwd") == client.get("pwd")
        )
    ]

    if len(clients) < original_length:
        # 儲存到 JSON
        if write_clients_to_json(section, clients):
            # 重新建立按鈕
            refresh_section_buttons(section, container, on_connect)
            log_and_show("刪除成功", f"{section} 客戶已刪除", "info")
        else:
            log_and_show("刪除失敗", "刪除資料時發生錯誤", "error")
    else:
        log_and_show("找不到客戶", "無法找到要刪除的客戶", "warning")


def refresh_section_buttons(section: str, container, on_connect):
    ui_common.refresh_section_buttons(
        section=section,
        read_clients_from_json=read_clients_from_json,
        create_client_buttons=create_client_buttons,
        rustdesk=globals().get("rustdesk"),
        anydesk=globals().get("anydesk"),
        tightvnc=globals().get("tightvnc"),
    )


gui = tk.Tk()
gui.title("Alldesk")
# 先隱藏視窗，避免在左上角閃現
gui.withdraw()
# 嘗試載入應用程式圖示（Windows: lioil.ico，macOS: lioil.icns）
try:
    # 根據平台選擇圖示檔案
    if sys.platform == 'darwin':  # macOS
        icon_filenames = ['lioil.icns']
    else:  # Windows and others
        icon_filenames = ['lioil.ico']
    
    icon_candidates = []
    for icon_name in icon_filenames:
        icon_candidates.extend([
            resource_path(icon_name),
            get_app_path(icon_name),
            os.path.join(str(BASE_DIR), icon_name),
        ])
    
    icon_path = next((p for p in icon_candidates if p and os.path.exists(p)), None)

    if icon_path:
        try:
            gui.iconbitmap(icon_path)
        except Exception:
            try:
                img = tk.PhotoImage(file=icon_path)
                gui.iconphoto(False, img)
            except Exception:
                pass
except Exception:
    pass

# 移除主選單


def import_csv_with_refresh(section: str):
    ui_common.import_csv_with_refresh(
        section=section,
        import_from_csv=import_from_csv,
        refresh_section_data=refresh_section_data,
        log_and_show=log_and_show,
    )


# 調整 Notebook 標籤字型:加大並改為粗體以便與 UI 一致
style = ttk.Style()
# 為了讓 tab 的背景/前景 mapping 生效,嘗試使用 'clam' 主題(較支援 element 顏色客製化)
try:
    if "clam" in style.theme_names():
        style.theme_use("clam")
except Exception:
    pass
tab_font = tkfont.Font(family="微軟正黑體", size=11, weight="bold")
style.configure(
    "Big.TNotebook.Tab",
    font=tab_font,
    padding=[12, 6],
    background="#f0f0f0",
    foreground="black",
)
# 確保 Notebook 本體與 tab 的預設背景一致
try:
    style.configure("TNotebook", background="#f0f0f0")
    style.configure("TNotebook.Tab", background="#f0f0f0")
except Exception:
    pass
# 當 tab 被選取時顯示黑底白字;未選取則為淺灰底黑字
style.map(
    "Big.TNotebook.Tab",
    background=[("selected", "black"), ("!selected", "#f0f0f0")],
    foreground=[("selected", "white"), ("!selected", "black")],
)

# 使用一個容器,將 `Notebook` 放左邊,右邊放一個 `EXCEL` 按鈕


# Notebook（含分頁與內容）
notebook = ttk.Notebook(gui, style="Big.TNotebook")
notebook.pack(fill="both", expand=True)

# 狀態圖例（放在主選單右上方，不參與版面寬度計算）
legend_frame = tk.Frame(gui)
legend_items = [
    ("#ff4444", "online"),
    ("#00cc66", "offline"),
    ("#666666", "unknow")
]
for color, text in legend_items:
    lbl = tk.Label(legend_frame, text="  ", bg=color, width=2, height=1)
    lbl.pack(side="left", padx=(0,2))
    tk.Label(legend_frame, text=text, font=("微軟正黑體", 9)).pack(side="left", padx=(0,8))
legend_frame.place(relx=1.0, x=-8, y=8, anchor="ne")

rustdesk = RustDesk(
    notebook,
    rustdesk_app=RUSTDESK_APP,
    base_dir=BASE_DIR,
    exe_dir=EXE_DIR,
    get_app_path=get_app_path,
    resource_path=resource_path,
    read_clients_from_json=read_clients_from_json,
    load_server_config=load_server_config,
    atomic_write_text=json_repo.atomic_write_text,
    launch_process=launch_process,
    create_header_row=create_header_row,
    create_client_buttons=create_client_buttons,
    build_unilink_for_id=_build_unilink_for_id,
    send_unilink_to_flutter_runner=_send_unilink_to_flutter_runner,
    find_window_for_id=_find_window_for_id,
    is_rustdesk_id_not_found_dialog_open=_is_rustdesk_id_not_found_dialog_open,
    is_rustdesk_connection_error_dialog_open=_is_rustdesk_connection_error_dialog_open,
    wait_and_input_password=_wait_and_input_password,
    close_window=_close_window,
    send_unilink_via_copydata=_send_unilink_via_copydata,
    try_uia_set_password=_try_uia_set_password,
    set_clipboard_text=_set_clipboard_text,
    paste_via_keyboard_and_enter=_paste_via_keyboard_and_enter,
    force_foreground=_force_foreground,
)
rustdesk.set_elements_rustdesk()

anydesk = AnyDesk(
    notebook,
    anydesk_app=ANYDESK_APP,
    read_clients_from_json=read_clients_from_json,
    create_header_row=create_header_row,
    create_client_buttons=create_client_buttons,
)
anydesk.set_elements_anydesk()

tightvnc = TightVNC(
    notebook,
    tightvnc_app=TIGHTVNC_APP,
    exe_dir=EXE_DIR,
    read_clients_from_json=read_clients_from_json,
    create_header_row=create_header_row,
    create_client_buttons=create_client_buttons,
    resource_path=resource_path,
    encrypt_tightvnc_password=encrypt_tightvnc_password,
    get_writable_dir=get_writable_dir,
)
tightvnc.set_elements_tightvnc()


def refresh_section_data(section: str):
    ui_common.refresh_section_data(
        section=section,
        read_clients_from_json=read_clients_from_json,
        create_client_buttons=create_client_buttons,
        rustdesk=globals().get("rustdesk"),
        anydesk=globals().get("anydesk"),
        tightvnc=globals().get("tightvnc"),
        rustdesk_status_manager=rustdesk_status_manager,
        get_rustdesk_peer_ids=_get_rustdesk_peer_ids,
    )


def _get_rustdesk_peer_ids() -> list[str]:
    return status_service.get_rustdesk_peer_ids(
        read_clients_from_json,
        normalize_client_fields,
    )


def _restart_rustdesk_status_manager_from_config():
    """依目前 server_config 重啟 RustDesk 狀態輪詢。"""
    global rustdesk_status_manager
    rustdesk_status_manager = status_service.restart_rustdesk_status_manager_from_config(
        rustdesk_status_manager,
        load_server_config,
        _get_rustdesk_peer_ids,
    )


def _compute_client_status(section: str, client: dict) -> str:
    return status_service.compute_client_status(
        section,
        client,
        normalize_client_fields,
        rustdesk_status_manager,
        ping_host,
        tcp_check,
    )


def _refresh_status_once():
    status_service.refresh_status_once(
        gui,
        STATUS_BUTTONS,
        STATUS_COLORS,
        read_clients_from_json,
        normalize_client_fields,
        rustdesk_status_manager,
        ping_host,
        tcp_check,
    )


def start_status_refresh_loop():
    status_service.start_status_refresh_loop(_refresh_status_once, interval=1)


# 移除編輯器功能，改為按鈕右鍵編輯


# 確保 JSON 檔案存在
if not ensure_json_exists():
    log_and_show("初始化錯誤", "無法建立 Alldesk.json 檔案", "error")

# 載入伺服器設定到全域變數
server_config = load_server_config()
RUSTDESK_HOST = server_config.get("server", "")
RUSTDESK_KEY = server_config.get("key", "")

# RustDesk 狀態：background polling thread（每 15 秒打 /api/peers），結果只放記憶體快取
_restart_rustdesk_status_manager_from_config()

# 背景刷新客戶端上線狀態燈號（不阻塞 UI）
start_status_refresh_loop()

# 設定主視窗預設大小並置中於螢幕 (預設寬度較寬以容納右側按鈕)
try:
    gui.update_idletasks()
    # 先取得元件要求尺寸，再決定最終視窗大小以便精準置中
    desired_w = 1300
    try:
        gui.minsize(desired_w, 200)
    except Exception:
        pass
    try:
        gui.update_idletasks()
    except Exception:
        pass

    try:
        req_w = gui.winfo_reqwidth()
        req_h = gui.winfo_reqheight()
    except Exception:
        req_w = desired_w
        req_h = 200

    final_w = max(req_w, desired_w)
    final_h = max(req_h, 200)

    try:
        sw = gui.winfo_screenwidth()
        sh = gui.winfo_screenheight()
    except Exception:
        sw = 800
        sh = 600

    x = max((sw - final_w) // 2, 0)
    y = max((sh - final_h) // 2, 0)

    # 使用包含寬高的 geometry 來設定位置，確保置中精準
    try:
        gui.geometry(f"{final_w}x{final_h}+{x}+{y}")
        try:
            gui.minsize(final_w, 200)
        except Exception:
            pass
    except Exception:
        try:
            gui.geometry(f"+{x}+{y}")
        except Exception:
            pass

    # 顯示視窗
    gui.deiconify()
    gui.lift()
    gui.focus_force()
except Exception:
    # 如果設定失敗，至少要顯示視窗
    try:
        gui.deiconify()
    except Exception:
        pass

gui.mainloop()
