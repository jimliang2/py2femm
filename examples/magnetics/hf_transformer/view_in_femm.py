"""
在 FEMM 4.2 視窗中直接顯示高頻變壓器求解結果與磁通密度分佈

使用方式 (在終端手動執行):
  cd C:/Users/jimli/py2femm_src/py2femm-main
  .venv/Scripts/python.exe examples/magnetics/hf_transformer/view_in_femm.py
"""
import femm
import os
import math
import time
import subprocess
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
fem_path = os.path.join(script_dir, 'hf_transformer_v2.fem')

FREQ = 100000

# ── 先確認 .fem 和 .ans 檔案存在 ──
if not os.path.exists(fem_path):
    print(f"ERROR: {fem_path} not found!")
    print("Please run run_hf_transformer.py first to generate the model.")
    sys.exit(1)

ans_path = fem_path.replace('.fem', '.ans')
if not os.path.exists(ans_path):
    print(f"ERROR: {ans_path} not found! Model has not been solved yet.")
    sys.exit(1)

print("Found model and solution files.")
print(f"  FEM: {fem_path}")
print(f"  ANS: {ans_path}")

# ── 關閉舊的 FEMM COM 連線 ──
try:
    femm.closefemm()
except:
    pass

# ── 開啟 FEMM (可見視窗模式，不要用 openfemm(1) 隱藏模式!) ──
print("\nStarting FEMM 4.2...")
femm.openfemm()          # <-- 無參數 = 可見視窗
print("FEMM started. Loading model...")
femm.opendocument(fem_path)
print("Model loaded. Loading solution...")
femm.mi_loadsolution()
print("Solution loaded.")

# 讀取電路特性
pri_I, pri_V, pri_Flux = femm.mo_getcircuitproperties('primary')
sec_I, sec_V, sec_Flux = femm.mo_getcircuitproperties('secondary')

print("=" * 60)
print("  High-Freq Transformer Results (100 kHz EE Core)")
print("=" * 60)
print(f"\n  Primary:   I={abs(pri_I):.4f}A  |V|={abs(pri_V):.6f}V  |Flux|={abs(pri_Flux):.4e} Wb")
print(f"  Secondary: I={abs(sec_I):.6f}A  |V|={abs(sec_V):.6f}V  |Flux|={abs(sec_Flux):.4e} Wb")

if abs(pri_I) > 1e-12:
    Z = pri_V / pri_I
    L = Z.imag / (2 * math.pi * FREQ)
    print(f"\n  Z_pri = {abs(Z):.6f} ohm")
    print(f"  L_pri = {L*1e6:.4f} uH")
    if abs(pri_I.real) > 1e-12:
        M = sec_Flux.real / pri_I.real
        k = M / L if L != 0 else 0
        print(f"  M     = {M*1e6:.4f} uH")
        print(f"  k     = {k:.4f}")

# 在 FEMM 後處理視窗顯示磁通密度
print("\nSetting up density plot in FEMM...")
femm.mo_showdensityplot(1, 0, 0.5, 0, 'bmag')
femm.mo_zoom(-11, -9, 17, 29)
femm.mo_refreshview()

print("\n" + "=" * 60)
print("  FEMM 4.2 is now showing the flux density plot!")
print("")
print("  Look for the FEMM window in your taskbar.")
print("  You should see TWO FEMM windows:")
print("    - Pre-processor (model geometry)")
print("    - Post-processor (flux density color map)")
print("")
print("  This script will keep FEMM alive for 30 minutes.")
print("  Press Ctrl+C in this terminal to close earlier.")
print("=" * 60)

# 保持 Python 運行，維持 COM 連線讓 FEMM 視窗不會關閉
try:
    time.sleep(1800)  # 30 minutes
except KeyboardInterrupt:
    pass
femm.closefemm()
print("FEMM closed.")
