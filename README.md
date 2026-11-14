# Alldesk

Alldesk 是一套 Windows 桌面端遠端支援啟動器。
它提供單一 GUI 介面，集中管理與連線以下工具：

- RustDesk
- AnyDesk
- TightVNC

本工具針對日常維運效率設計，提供一鍵連線、帳密保存、資料匯入匯出與狀態燈顯示。

目前版本：**v1.0.3**。修正 RustDesk 1.5.3 連線視窗辨識，支援自動按「繼續」並接續輸入密碼；提供 onefile 與 onedir 兩種版本。

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
- 支援 RustDesk 1.5.3 的「非安全連線」提示：自動按「繼續」，接著填入密碼並按「確定」
- 只操作前景、視窗類別及完整目標 ID 均符合的 RustDesk 視窗；切換到其他程式或其他連線時暫停輸入
- 相容 RustDesk 1.5.3 的 `RustdeskMultiWindow` 連線視窗及舊版 `FLUTTER_RUNNER_WIN32_WINDOW`，避免把新版連線視窗錯誤略過
- 每 0.05 秒檢查連線提示，UI Automation 呼叫與 RustDesk 本身的反應時間另計
- 密碼輸入優先使用 UI Automation ValuePattern；不支援時改用確認焦點後的 Unicode 鍵盤輸入
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
- 密碼監看一啟動就檢查目標視窗，取消舊流程的 2 秒初始備援等待及全桌面掃描。
- 每次連線只自動按一次「繼續」，不連發 Enter、不盲貼密碼，也不因未出現密碼框而關閉已建立的連線。
- 連線流程由 UI 回呼非同步啟動，避免阻塞 Tk 主執行緒。

---

## 疑難排解

### 關閉錯誤視窗後 UI 看起來仍忙碌
- 請確認使用的是已採非同步啟動 RustDesk 的最新程式版本。
- 請確認沒有從舊路徑誤啟動過期二進位檔。

### 密碼視窗有出現，但自動輸入偶發失敗
- 請讓本次目標 RustDesk 視窗保持在前景，以便辨識及填入密碼。
- 若仍失敗，請檢查視窗焦點行為與 UAC/權限層級是否不一致。

### 更新 RustDesk 後出現「非安全連線」
- 官方已在 [PR #15514](https://github.com/rustdesk/rustdesk/pull/15514) 加入非 E2EE 連線確認；[1.5.3 連線原始碼](https://github.com/rustdesk/rustdesk/blob/1.5.3/src/client/io_loop.rs) 在無法驗證端到端加密的 ID 連線中會等待使用者繼續。
- 自動按「繼續」代表接受此次未驗證的連線，並不修復加密或信任問題。持續發生時，應檢查遠端服務就緒狀態及自架伺服器的公鑰設定。
- 內附 RustDesk 已更新為官方 1.5.3 x86-64，SHA-256：`523ba0efbf62a21739961b62c7daaffb44d3da86139c546b364fd4e1333ed249`。

### 狀態燈長時間維持 unknown
- 檢查 `server_config` 的主機、API 埠與帳密。
- 確認 RustDesk Server API 端點可連通。

---

## 建議後續工作

1. 補強 GUI 互動流程的整合測試（例如匯入匯出與右鍵操作路徑）。
2. 針對打包產物（onefile/onedir）建立固定 smoke test 腳本。
3. 在不影響行為下，持續降低 `app/ui/main_window.py` 耦合度。
