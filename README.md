# Alldesk

Alldesk 是一套 Windows 桌面端遠端支援啟動器。
它提供單一 GUI 介面，集中管理與連線以下工具：

- RustDesk
- AnyDesk
- TightVNC

本工具針對日常維運效率設計，提供一鍵連線、帳密保存、資料匯入匯出與狀態燈顯示。

---

## 主要功能

### 連線管理
- 依區段儲存客戶資料（`rustdesk`、`anydesk`、`tightvnc`）
- 透過按鈕網格快速連線
- 右鍵選單支援編輯、刪除、新增
- 標頭提供手動輸入 ID/密碼的快速連線欄位

### RustDesk 流程
- 支援伺服器設定（`server`、`key`、API 帳密與埠號）
- 連線前會先寫入必要的執行期設定檔
- 密碼輸入採多重策略：
	- UI Automation (pywinauto)
	- 剪貼簿加鍵盤備援
	- 可用時走 WM_COPYDATA / unilink 路徑
- 針對連線錯誤狀態（如無效 ID）有特別處理
- UI 回呼採非阻塞連線路徑

### AnyDesk 流程
- 啟動前會產生 AnyDesk 使用者設定
- 支援透過管線傳入密碼啟動
- 具備提權啟動失敗時的備援處理

### TightVNC 流程
- 由範本產生執行期 `.vnc` 連線設定
- 支援 TightVNC 所需的密碼加密格式

### 資料操作
- 使用 JSON 儲存（`Alldesk.json`）
- 各區段可獨立 CSV 匯入匯出
- 採原子寫入降低檔案損毀風險

### 狀態燈
- UI 顯示 RustDesk online/offline/unknown 三態顏色
- 由 `app/services/status_manager.py` 在背景輪詢
- 支援 API token 自動更新與多來源備援資料

---

## 專案結構（目前）

```text
Alldesk.py                    # 薄入口（僅啟動 app/bootstrap）
Alldesk.json                  # 執行期客戶資料與伺服器設定
app/
	bootstrap.py                # 啟動流程
	platform/                   # WinAPI/剪貼簿/程序啟動
	repositories/               # JSON/CSV 存取
	security/                   # TightVNC 密碼相容加密
	services/                   # 連線與狀態服務
	ui/                         # 主視窗、tabs、dialogs、common widgets
	utils/                      # 路徑/文字工具
tests/                        # 基礎自動化測試
exe/                          # 打包附帶的外部執行檔與資源
Alldesk-onefile.spec          # PyInstaller 單檔版規格
Alldesk-onedir.spec           # PyInstaller 目錄版規格
pyproject.toml                # 相依套件與建置中繼資料
uv.lock                       # 鎖定版相依套件清單
```

### 架構說明

目前已完成模組化重構：
- `Alldesk.py` 為薄入口
- UI/服務/資料/平台模組已拆分至 `app/`
- `tests/` 提供 repository 與文字正規化的基本自動化測試

---

## 環境需求

- Windows
- `uv`
- Python 3.12+

---

## 安裝與初始化

```powershell
uv sync --group dev
```

`uv` 會自動建立與管理 `.venv`。

---

## 開發模式執行

```powershell
uv run python Alldesk.py
```

---

## 設定與資料

主要執行期檔案：

- `Alldesk.json`

內容包含：

- 各區段客戶清單（`rustdesk`、`anydesk`、`tightvnc`）
- RustDesk 伺服器/API 設定（`server_config`）

`server_config` 欄位：

- `server`
- `key`
- `rustdesk_api_port`
- `api_username`
- `api_password`

---

## 相依套件管理

主要檔案：

- `pyproject.toml`
- `uv.lock`

變更相依套件後請執行：

```powershell
uv lock
uv sync --group dev
```

注意事項：

- 不要使用 `pip install -r requirements.txt`
- 不要手動建立或維護 `.venv`

---

## 建置

### 建置 Python 套件

```powershell
uv build
```

### 建置 EXE（PyInstaller）

單檔版：

```powershell
uv run pyinstaller Alldesk-onefile.spec
```

目錄版：

```powershell
uv run pyinstaller Alldesk-onedir.spec
```

建置完成後預期輸出：
- `dist/Alldesk-onefile.exe`
- `dist/Alldesk-onedir/`

---

## 執行行為與穩定性說明

- RustDesk 連線流程包含重試與備援路徑。
- 密碼輸入前會有短暫延遲，降低視窗剛開啟時的競態問題。
- 連線流程由 UI 回呼非同步啟動，避免阻塞 Tk 主執行緒。

---

## 疑難排解

### 關閉錯誤視窗後 UI 看起來仍忙碌
- 請確認使用的是已採非同步啟動 RustDesk 的最新程式版本。
- 請確認沒有從舊路徑誤啟動過期二進位檔。

### 密碼視窗有出現，但自動輸入偶發失敗
- 目前已內建短延遲輸入，降低焦點切換競態。
- 若仍失敗，請檢查視窗焦點行為與 UAC/權限層級是否不一致。

### 狀態燈長時間維持 unknown
- 檢查 `server_config` 的主機、API 埠與帳密。
- 確認 RustDesk Server API 端點可連通。

---

## 建議後續工作

1. 補強 GUI 互動流程的整合測試（例如匯入匯出與右鍵操作路徑）。
2. 針對打包產物（onefile/onedir）建立固定 smoke test 腳本。
3. 在不影響行為下，持續降低 `app/ui/main_window.py` 耦合度。
