"""
高頻變壓器 FEMM 模擬 (100 kHz EE 磁芯 + Litz 繞組)
基於 minimal_test.py 的成功幾何架構，搭配完整材料與後處理。
"""
import femm
import os
import math

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# ── 參數 ─────────────────────────────────────────────────
FREQ       = 100_000   # Hz
I_PRIMARY  = 0.5       # A (peak)
N_PRIMARY  = 20
N_SECONDARY= 5

# EE 磁芯幾何 (mm) — 以原點為窗口左下角
CORE_W  = 6    # 中柱 / 外壁 寬度
CORE_H  = 20   # 窗口高度
CORE_T  = 4    # 上下蓋厚度
WIN_W   = 8    # 窗口寬度

# 繞組
PRI_W, PRI_H   = 3, 16
SEC_W, SEC_H   = 3, 16
COIL_GAP        = 1     # 一次側與二次側間距

# 空氣邊界 (半邊長)
BOUND = 60

# ── 座標計算 ──────────────────────────────────────────────
x_left  = -CORE_W          # -6
x_mid_l =  0.0
x_mid_r =  WIN_W           #  8
x_right =  WIN_W + CORE_W  # 14  <-- 注意: 外壁也是 CORE_W 寬
y_bot   = -CORE_T          # -4
y_win_b =  0.0
y_win_t =  CORE_H          # 20
y_top   =  CORE_H + CORE_T # 24

# 繞組位置 (浮動在窗口內)
pri_x0 = 0.5
pri_y0 = (CORE_H - PRI_H) / 2  # 2
sec_x0 = pri_x0 + PRI_W + COIL_GAP  # 4.5
sec_y0 = (CORE_H - SEC_H) / 2       # 2

# ── 開啟 FEMM ──────────────────────────────────────────────
try:
    femm.closefemm()
except:
    pass

femm.openfemm()
femm.newdocument(0)
femm.mi_probdef(FREQ, 'millimeters', 'planar', 1e-8, 1, 30, 0)

# ── 幾何建構 ──────────────────────────────────────────────

# 1) EE 磁芯 — 4×4 = 16 節點
xs = [x_left, x_mid_l, x_mid_r, x_right]
ys = [y_bot,  y_win_b, y_win_t, y_top]
for x in xs:
    for y in ys:
        femm.mi_addnode(x, y)

# 水平線段
for y in ys:
    for i in range(len(xs) - 1):
        femm.mi_addsegment(xs[i], y, xs[i+1], y)
    # 窗口內的水平邊界線 (y_win_b, y_win_t) 已在上面覆蓋

# 垂直線段
for x in xs:
    for j in range(len(ys) - 1):
        femm.mi_addsegment(x, ys[j], x, ys[j+1])

# 2) 空氣邊界
half = BOUND
corners = [(-half, -half), (half, -half), (half, half), (-half, half)]
for c in corners:
    femm.mi_addnode(c[0], c[1])
for i in range(4):
    c1, c2 = corners[i], corners[(i+1) % 4]
    femm.mi_addsegment(c1[0], c1[1], c2[0], c2[1])

# 3) 繞組矩形 (浮動)
def add_rect(x0, y0, w, h):
    femm.mi_addnode(x0, y0)
    femm.mi_addnode(x0+w, y0)
    femm.mi_addnode(x0+w, y0+h)
    femm.mi_addnode(x0, y0+h)
    femm.mi_addsegment(x0, y0, x0+w, y0)
    femm.mi_addsegment(x0+w, y0, x0+w, y0+h)
    femm.mi_addsegment(x0+w, y0+h, x0, y0+h)
    femm.mi_addsegment(x0, y0+h, x0, y0)

add_rect(pri_x0, pri_y0, PRI_W, PRI_H)
add_rect(sec_x0, sec_y0, SEC_W, SEC_H)

# ── 材料定義 ─────────────────────────────────────────────

# N87 鐵氧體 — 用 BH 曲線
femm.mi_addmaterial('N87_ferrite', 0, 0, 0, 0, 0.01, 0, 0, 1, 0, 0, 0, 0, 0)
bh_points = [
    (0, 0), (16, 0.05), (32, 0.10), (48, 0.15), (80, 0.20),
    (120, 0.25), (180, 0.30), (300, 0.35), (500, 0.38),
    (800, 0.40), (1500, 0.43), (3000, 0.46), (6000, 0.48),
    (10000, 0.50),
]
for H, B in bh_points:
    femm.mi_addbhpoint('N87_ferrite', B, H)

# 一次側銅 (Litz: 50 股 × 0.10 mm)
femm.mi_addmaterial('copper_pri', 1, 1, 0, 0, 58, 0, 0, 0, 0, 0, 0, 0, 0)
femm.mi_addmaterial('copper_sec', 1, 1, 0, 0, 58, 0, 0, 0, 0, 0, 0, 0, 0)

# 空氣
femm.mi_addmaterial('air', 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

# ── 電路 ─────────────────────────────────────────────────
femm.mi_addcircprop('primary',   I_PRIMARY, 1)   # series
femm.mi_addcircprop('secondary', 0,         1)   # series, open

# ── 邊界條件 ─────────────────────────────────────────────
femm.mi_addboundprop('a0', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
mid_segs = [
    (0,        -half),  # bottom
    (half,      0),     # right
    (0,         half),  # top
    (-half,     0),     # left
]
for sx, sy in mid_segs:
    femm.mi_selectsegment(sx, sy)
femm.mi_setsegmentprop('a0', 0, 1, 0, 0)
femm.mi_clearselected()

# ── Block Labels ─────────────────────────────────────────
regions = [
    # 磁芯 8 區
    ('中柱',    (x_left + x_mid_l) / 2, (y_win_b + y_win_t) / 2,
     'N87_ferrite', '<None>', 0),
    ('外壁',    (x_mid_r + x_right) / 2, (y_win_b + y_win_t) / 2,
     'N87_ferrite', '<None>', 0),
    ('上蓋左',  (x_left + x_mid_l) / 2, (y_win_t + y_top) / 2,
     'N87_ferrite', '<None>', 0),
    ('上蓋中',  (x_mid_l + x_mid_r) / 2, (y_win_t + y_top) / 2,
     'N87_ferrite', '<None>', 0),
    ('上蓋右',  (x_mid_r + x_right) / 2, (y_win_t + y_top) / 2,
     'N87_ferrite', '<None>', 0),
    ('下蓋左',  (x_left + x_mid_l) / 2, (y_bot + y_win_b) / 2,
     'N87_ferrite', '<None>', 0),
    ('下蓋中',  (x_mid_l + x_mid_r) / 2, (y_bot + y_win_b) / 2,
     'N87_ferrite', '<None>', 0),
    ('下蓋右',  (x_mid_r + x_right) / 2, (y_bot + y_win_b) / 2,
     'N87_ferrite', '<None>', 0),
    # 繞組
    ('pri', pri_x0 + PRI_W/2, pri_y0 + PRI_H/2,
     'copper_pri', 'primary', N_PRIMARY),
    ('sec', sec_x0 + SEC_W/2, sec_y0 + SEC_H/2,
     'copper_sec', 'secondary', N_SECONDARY),
    # 窗口空氣 (在左邊間隙中)
    ('窗口空氣', 0.25, (y_win_b + y_win_t) / 2,
     'air', '<None>', 0),
    # 外部空氣
    ('外部', half / 2, half / 2,
     'air', '<None>', 0),
]

for name, x, y, mat, circ, turns in regions:
    femm.mi_addblocklabel(x, y)
    femm.mi_selectlabel(x, y)
    femm.mi_setblockprop(mat, 1, 0, circ, 0, 0, turns)
    femm.mi_clearselected()
    print(f"  {name}: ({x:.2f}, {y:.2f}) -> {mat}")

# ── 儲存 & 求解 ─────────────────────────────────────────
fem_path = os.path.join(script_dir, 'hf_transformer_full.fem')
femm.mi_saveas(fem_path)
print(f"\n模型已儲存: {fem_path}")

print("求解中 (mi_analyze)...")
femm.mi_analyze(1)
print("mi_analyze OK!")

femm.mi_loadsolution()
print("mi_loadsolution OK!")

# ── 後處理 ───────────────────────────────────────────────####
# 電路特性
pri_I, pri_V, pri_Flux = femm.mo_getcircuitproperties('primary')
sec_I, sec_V, sec_Flux = femm.mo_getcircuitproperties('secondary')

print("\n═══ 電路特性 ═══")
print(f"  一次側: I = {pri_I:.4f} A")
print(f"          V = {pri_V}")
print(f"          Φ = {pri_Flux}")
print(f"  二次側: I = {sec_I:.4f} A")
print(f"          V = {sec_V}")
print(f"          Φ = {sec_Flux}")

# 計算阻抗和電感
if abs(pri_I) > 1e-12:
    Z_pri = pri_V / pri_I
    L_pri = Z_pri.imag / (2 * math.pi * FREQ)
    print(f"\n  Z_pri = {Z_pri}")
    print(f"  L_pri = {L_pri * 1e6:.3f} uH")

# 互感
if abs(pri_I) > 1e-12:
    M = sec_Flux.real / pri_I.real if abs(pri_I.real) > 1e-12 else 0
    print(f"  M     = {M * 1e6:.3f} uH")

# 磁芯損耗
femm.mo_groupselectblock(0)  # select all
total_losses = femm.mo_blockintegral(6)  # Ohmic losses
femm.mo_clearblock()
print(f"\n  總損耗 (Ohmic) = {total_losses}")

# 在 FEMM 後處理視窗顯示磁通密度分佈
femm.mo_showdensityplot(1, 0, 0.5, 0, 'bmag')
femm.mo_zoom(x_left - 5, y_bot - 5, x_right + 5, y_top + 5)

print("\n✓ 模擬完成！FEMM 視窗已顯示磁通密度分佈圖。")
print("  請在 FEMM 視窗中查看結果，完成後手動關閉 FEMM。")
