"""
讀取 FEMM 求解結果，顯示電路特性 + matplotlib 磁通密度分佈圖
"""
import femm
import matplotlib.pyplot as plt
import matplotlib
import matplotlib.tri as tri
import numpy as np
import os
import math

matplotlib.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'Arial']
matplotlib.rcParams['axes.unicode_minus'] = False

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
fem_path = os.path.join(script_dir, 'hf_transformer_v2.fem')

# ── 參數 (與模型一致) ───────────────────────────────────
FREQ = 100000
x_left, x_mid_l, x_mid_r, x_right = -6.0, 0.0, 8.0, 12.0
y_bot, y_win_b, y_win_t, y_top = -4.0, 0.0, 20.0, 24.0

# ── 開啟 FEMM 並載入結果 ────────────────────────────────
try:
    femm.closefemm()
except:
    pass

femm.openfemm(1)  # 1 = minimized / hidden
femm.opendocument(fem_path)
femm.mi_loadsolution()

# ── 電路特性 ─────────────────────────────────────────────
pri_I, pri_V, pri_Flux = femm.mo_getcircuitproperties('primary')
sec_I, sec_V, sec_Flux = femm.mo_getcircuitproperties('secondary')

print("=" * 60)
print("  高頻變壓器模擬結果 (100 kHz EE 磁芯)")
print("=" * 60)

print("\n【一次側 (Primary)】")
print(f"  電流 I       = {abs(pri_I):.4f} A  (peak)")
print(f"  電壓 V       = {pri_V}")
print(f"  |V|          = {abs(pri_V):.6f} V")
print(f"  磁通鏈 Φ     = {pri_Flux}")
print(f"  |Φ|          = {abs(pri_Flux):.6e} Wb")

print("\n【二次側 (Secondary, 開路)】")
print(f"  電流 I       = {abs(sec_I):.6f} A")
print(f"  電壓 V       = {sec_V}")
print(f"  |V|          = {abs(sec_V):.6f} V")
print(f"  磁通鏈 Φ     = {sec_Flux}")
print(f"  |Φ|          = {abs(sec_Flux):.6e} Wb")

# 阻抗 & 電感
if abs(pri_I) > 1e-12:
    Z_pri = pri_V / pri_I
    L_pri = Z_pri.imag / (2 * math.pi * FREQ)
    R_pri = Z_pri.real
    print(f"\n【阻抗分析】")
    print(f"  Z_pri        = {Z_pri}")
    print(f"  |Z_pri|      = {abs(Z_pri):.6f} Ω")
    print(f"  R_pri        = {R_pri:.6f} Ω")
    print(f"  L_pri        = {L_pri * 1e6:.4f} μH")

# 互感
if abs(pri_I) > 1e-12 and abs(pri_I.real) > 1e-12:
    M = sec_Flux.real / pri_I.real
    k = M / L_pri if L_pri != 0 else 0
    print(f"  M (互感)     = {M * 1e6:.4f} μH")
    print(f"  k (耦合係數) = {k:.4f}")

# 匝數比
print(f"\n【變壓器參數】")
print(f"  匝數比 N1:N2 = 20:5 = 4:1")
if abs(sec_V) > 1e-12 and abs(pri_V) > 1e-12:
    voltage_ratio = abs(pri_V) / abs(sec_V)
    print(f"  電壓比       = {voltage_ratio:.2f}")

# 損耗
femm.mo_groupselectblock(0)
total_loss = femm.mo_blockintegral(6)   # Ohmic loss (W/m)
femm.mo_clearblock()
print(f"\n【損耗】")
print(f"  總歐姆損耗   = {total_loss:.6e} W/m")

print("\n" + "=" * 60)

# ── 取樣磁通密度 ─────────────────────────────────────────
print("\n正在取樣磁通密度資料...")

# 定義取樣範圍 (稍微超出磁芯)
margin = 3
x_min, x_max = x_left - margin, x_right + margin
y_min, y_max = y_bot - margin, y_top + margin
nx, ny = 120, 120

xv = np.linspace(x_min, x_max, nx)
yv = np.linspace(y_min, y_max, ny)
X, Y = np.meshgrid(xv, yv)

Bmag = np.zeros_like(X)
Bx_arr = np.zeros_like(X)
By_arr = np.zeros_like(X)

for i in range(ny):
    for j in range(nx):
        try:
            px, py = float(X[i, j]), float(Y[i, j])
            vals = femm.mo_getpointvalues(px, py)
            if vals is not None and len(vals) >= 8:
                bx = vals[1] if vals[1] is not None else 0
                by = vals[2] if vals[2] is not None else 0
                if isinstance(bx, complex):
                    bx = abs(bx)
                if isinstance(by, complex):
                    by = abs(by)
                Bx_arr[i, j] = bx
                By_arr[i, j] = by
                Bmag[i, j] = math.sqrt(bx**2 + by**2)
        except:
            pass

femm.closefemm()
print(f"取樣完成: {nx}×{ny} = {nx*ny} 點")
print(f"  B_max = {np.max(Bmag):.4f} T")
print(f"  B_mean(非零) = {np.mean(Bmag[Bmag > 0]):.4f} T")

# ── 繪圖 ─────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(16, 8))

# --- 左圖: 磁通密度分佈 ---
ax1 = axes[0]
levels = np.linspace(0, min(np.max(Bmag), 0.5), 50)
if np.max(Bmag) < 0.001:
    levels = np.linspace(0, np.max(Bmag) * 1.1, 50)

cs = ax1.contourf(X, Y, Bmag, levels=levels, cmap='jet', extend='max')
cb = fig.colorbar(cs, ax=ax1, label='|B| (T)')

# 畫磁芯輪廓
core_lines = [
    # 外框
    ([x_left, x_right, x_right, x_left, x_left],
     [y_bot, y_bot, y_top, y_top, y_bot]),
    # 窗口
    ([x_mid_l, x_mid_r, x_mid_r, x_mid_l, x_mid_l],
     [y_win_b, y_win_b, y_win_t, y_win_t, y_win_b]),
]
for lx, ly in core_lines:
    ax1.plot(lx, ly, 'k-', linewidth=1.5)

# 繞組
pri_x0, pri_y0, pri_w, pri_h = 0.5, 2, 3, 16
sec_x0, sec_y0, sec_w, sec_h = 4.5, 2, 3, 16
from matplotlib.patches import Rectangle
ax1.add_patch(Rectangle((pri_x0, pri_y0), pri_w, pri_h,
              fill=False, edgecolor='red', linewidth=1.5, linestyle='--', label='一次側'))
ax1.add_patch(Rectangle((sec_x0, sec_y0), sec_w, sec_h,
              fill=False, edgecolor='blue', linewidth=1.5, linestyle='--', label='二次側'))

ax1.set_xlabel('x (mm)')
ax1.set_ylabel('y (mm)')
ax1.set_title('磁通密度 |B| 分佈')
ax1.set_aspect('equal')
ax1.legend(loc='upper right')

# --- 右圖: 中柱磁通密度沿 y 方向 ---
ax2 = axes[1]
mid_x = (x_left + x_mid_l) / 2  # 中柱中心 x = -3
y_line = np.linspace(y_bot, y_top, 200)
b_line = []
for yp in y_line:
    j_idx = np.argmin(np.abs(xv - mid_x))
    i_idx = np.argmin(np.abs(yv - yp))
    b_line.append(Bmag[i_idx, j_idx])

ax2.plot(y_line, b_line, 'b-', linewidth=2)
ax2.axvline(x=y_win_b, color='gray', linestyle=':', alpha=0.5, label='窗口邊界')
ax2.axvline(x=y_win_t, color='gray', linestyle=':', alpha=0.5)
ax2.set_xlabel('y (mm)')
ax2.set_ylabel('|B| (T)')
ax2.set_title(f'中柱磁通密度 (x = {mid_x:.1f} mm)')
ax2.legend()
ax2.grid(True, alpha=0.3)

plt.suptitle('高頻變壓器 FEMM 模擬結果 (100 kHz, EE 磁芯, N87)', fontsize=14, fontweight='bold')
plt.tight_layout()

out_png = os.path.join(script_dir, 'hf_transformer_results.png')
plt.savefig(out_png, dpi=150, bbox_inches='tight')
print(f"\n圖表已儲存: {out_png}")
plt.show()
