# pyfemm GUI 原型

簡要原型，用於在 Windows 上搭配 FEMM（透過 `pyfemm` COM）進行互動式操作、取樣與匯出場圖。

需求
- Windows
- FEMM 安裝（例如 C:\\femm42\\bin\\femm.exe）
- Python 3.8+ 環境

安裝
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

執行
```powershell
python -m pyfemm_gui.main
```

注意事項
- 若遇到 COM 連線問題，請先關閉所有 femm.exe 實例，再重試。
- 這是原型；商用排程、例外與多實例管理需要額外強化。
