"""
高頻變壓器 FEMM 模擬 — 生成 Lua 腳本並啟動 FEMM 執行
100 kHz EE 磁芯 + Litz 繞組，可視化磁通密度分佈
"""
import os
import subprocess
import math

script_dir = os.path.dirname(os.path.abspath(__file__))
lua_path = os.path.join(script_dir, 'hf_transformer_v2.lua')
fem_path = os.path.join(script_dir, 'hf_transformer_v2.fem').replace('\\', '/')

# ── 參數 ─────────────────────────────────────────────────
FREQ        = 100000    # Hz
I_PRIMARY   = 0.5       # A (peak)
N_PRIMARY   = 20
N_SECONDARY = 5

# EE 磁芯幾何 (mm)
CORE_W  = 6     # 中柱 / 外壁寬度
CORE_H  = 20    # 窗口高度
CORE_T  = 4     # 上下蓋厚度
WIN_W   = 8     # 窗口寬度

# 繞組
PRI_W, PRI_H = 3, 16
SEC_W, SEC_H = 3, 16
COIL_GAP = 1

# 邊界
BOUND = 60

# ── 座標 ─────────────────────────────────────────────────
x_left  = -CORE_W          # -6
x_mid_l =  0.0
x_mid_r =  WIN_W           #  8
x_right =  WIN_W + CORE_W  # 14
y_bot   = -CORE_T          # -4
y_win_b =  0.0
y_win_t =  CORE_H          # 20
y_top   =  CORE_H + CORE_T # 24

pri_x0 = 0.5
pri_y0 = (CORE_H - PRI_H) / 2   # 2
sec_x0 = pri_x0 + PRI_W + COIL_GAP  # 4.5
sec_y0 = (CORE_H - SEC_H) / 2       # 2

half = BOUND

# N87 BH 曲線
bh_data = [
    (0, 0), (16, 0.05), (32, 0.10), (48, 0.15), (80, 0.20),
    (120, 0.25), (180, 0.30), (300, 0.35), (500, 0.38),
    (800, 0.40), (1500, 0.43), (3000, 0.46), (6000, 0.48),
    (10000, 0.50),
]

# ── 生成 Lua ─────────────────────────────────────────────
lua_lines = []
L = lua_lines.append

L('-- 高頻變壓器模擬 (自動產生)')
L('newdocument(0)')
L(f'mi_probdef({FREQ},"millimeters","planar",1e-8,1,30,0)')
L('')

# 1) 磁芯節點
L('-- EE 磁芯 16 節點')
xs = [x_left, x_mid_l, x_mid_r, x_right]
ys = [y_bot, y_win_b, y_win_t, y_top]
for x in xs:
    for y in ys:
        L(f'mi_addnode({x},{y})')

# 2) 水平線段
L('-- 水平線段')
for y in ys:
    for i in range(len(xs)-1):
        L(f'mi_addsegment({xs[i]},{y},{xs[i+1]},{y})')

# 3) 垂直線段
L('-- 垂直線段')
for x in xs:
    for j in range(len(ys)-1):
        L(f'mi_addsegment({x},{ys[j]},{x},{ys[j+1]})')

# 4) 空氣邊界
L('')
L('-- 空氣邊界')
corners = [(-half,-half), (half,-half), (half,half), (-half,half)]
for c in corners:
    L(f'mi_addnode({c[0]},{c[1]})')
for i in range(4):
    c1, c2 = corners[i], corners[(i+1)%4]
    L(f'mi_addsegment({c1[0]},{c1[1]},{c2[0]},{c2[1]})')

# 5) 繞組矩形
L('')
L('-- 繞組矩形')
for (x0, y0, w, h) in [(pri_x0, pri_y0, PRI_W, PRI_H), (sec_x0, sec_y0, SEC_W, SEC_H)]:
    L(f'mi_addnode({x0},{y0})')
    L(f'mi_addnode({x0+w},{y0})')
    L(f'mi_addnode({x0+w},{y0+h})')
    L(f'mi_addnode({x0},{y0+h})')
    L(f'mi_addsegment({x0},{y0},{x0+w},{y0})')
    L(f'mi_addsegment({x0+w},{y0},{x0+w},{y0+h})')
    L(f'mi_addsegment({x0+w},{y0+h},{x0},{y0+h})')
    L(f'mi_addsegment({x0},{y0+h},{x0},{y0})')

# 6) 材料
L('')
L('-- 材料')
L('mi_addmaterial("N87_ferrite",0,0,0,0,0.01,0,0,1,0,0,0,0,0)')
for H, B in bh_data:
    L(f'mi_addbhpoint("N87_ferrite",{B},{H})')
L('mi_addmaterial("copper_pri",1,1,0,0,58,0,0,0,0,0,0,0,0)')
L('mi_addmaterial("copper_sec",1,1,0,0,58,0,0,0,0,0,0,0,0)')
L('mi_addmaterial("air",1,1,0,0,0,0,0,0,0,0,0,0,0)')

# 7) 電路
L('')
L('-- 電路')
L(f'mi_addcircprop("primary",{I_PRIMARY},1)')
L('mi_addcircprop("secondary",0,1)')

# 8) 邊界條件
L('')
L('-- 邊界條件')
L('mi_addboundprop("a0",0,0,0,0,0,0,0,0,0,0,0)')
mid_segs = [(0, -half), (half, 0), (0, half), (-half, 0)]
for sx, sy in mid_segs:
    L(f'mi_selectsegment({sx},{sy})')
L('mi_setsegmentprop("a0",0,1,0,0)')
L('mi_clearselected()')

# 9) Block Labels
L('')
L('-- Block Labels')

core_mid_x_left  = (x_left + x_mid_l) / 2
core_mid_x_right = (x_mid_r + x_right) / 2
core_mid_x_win   = (x_mid_l + x_mid_r) / 2
core_mid_y       = (y_win_b + y_win_t) / 2
core_mid_y_top   = (y_win_t + y_top) / 2
core_mid_y_bot   = (y_bot + y_win_b) / 2

core_labels = [
    (core_mid_x_left,  core_mid_y,     'N87_ferrite'),  # 中柱
    (core_mid_x_right, core_mid_y,     'N87_ferrite'),  # 外壁
    (core_mid_x_left,  core_mid_y_top, 'N87_ferrite'),  # 上蓋左
    (core_mid_x_win,   core_mid_y_top, 'N87_ferrite'),  # 上蓋中
    (core_mid_x_right, core_mid_y_top, 'N87_ferrite'),  # 上蓋右
    (core_mid_x_left,  core_mid_y_bot, 'N87_ferrite'),  # 下蓋左
    (core_mid_x_win,   core_mid_y_bot, 'N87_ferrite'),  # 下蓋中
    (core_mid_x_right, core_mid_y_bot, 'N87_ferrite'),  # 下蓋右
]
for x, y, mat in core_labels:
    L(f'mi_addblocklabel({x},{y})')
    L(f'mi_selectlabel({x},{y})')
    L(f'mi_setblockprop("{mat}",1,0,"<None>",0,0,0)')
    L('mi_clearselected()')

# 繞組
pri_cx = pri_x0 + PRI_W / 2
pri_cy = pri_y0 + PRI_H / 2
sec_cx = sec_x0 + SEC_W / 2
sec_cy = sec_y0 + SEC_H / 2

L(f'mi_addblocklabel({pri_cx},{pri_cy})')
L(f'mi_selectlabel({pri_cx},{pri_cy})')
L(f'mi_setblockprop("copper_pri",1,0,"primary",0,0,{N_PRIMARY})')
L('mi_clearselected()')

L(f'mi_addblocklabel({sec_cx},{sec_cy})')
L(f'mi_selectlabel({sec_cx},{sec_cy})')
L(f'mi_setblockprop("copper_sec",1,0,"secondary",0,0,{N_SECONDARY})')
L('mi_clearselected()')

# 窗口空氣 (在一次側左邊間隙)
L(f'mi_addblocklabel(0.25,{core_mid_y})')
L(f'mi_selectlabel(0.25,{core_mid_y})')
L('mi_setblockprop("air",1,0,"<None>",0,0,0)')
L('mi_clearselected()')

# 外部空氣
L(f'mi_addblocklabel({half/2},{half/2})')
L(f'mi_selectlabel({half/2},{half/2})')
L('mi_setblockprop("air",1,0,"<None>",0,0,0)')
L('mi_clearselected()')

# 10) 儲存、求解
L('')
L('-- 儲存與求解')
L(f'mi_saveas("{fem_path}")')
L('mi_analyze()')
L('mi_loadsolution()')

# 11) 後處理 — 顯示磁通密度
L('')
L('-- 顯示磁通密度分佈')
L('mo_showdensityplot(1,0,0.5,0,"bmag")')
L(f'mo_zoom({x_left-5},{y_bot-5},{x_right+5},{y_top+5})')

# 12) 讀取電路數據
L('')
L('-- 電路數據')
L('pri_I, pri_V, pri_Flux = mo_getcircuitproperties("primary")')
L('sec_I, sec_V, sec_Flux = mo_getcircuitproperties("secondary")')
L('print("═══ 電路特性 ═══")')
L('print("一次側: I =", pri_I, " V =", pri_V, " Flux =", pri_Flux)')
L('print("二次側: I =", sec_I, " V =", sec_V, " Flux =", sec_Flux)')

# 不呼叫 quit()，讓 FEMM 保持開啟
L('')
L('-- FEMM 保持開啟，使用者可檢視結果')

# ── 寫入 Lua ─────────────────────────────────────────────
with open(lua_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lua_lines) + '\n')

print(f"Lua 腳本已生成: {lua_path}")

# ── 啟動 FEMM ────────────────────────────────────────────
femm_exe = r'C:\femm42\bin\femm.exe'
if not os.path.exists(femm_exe):
    print(f"錯誤: 找不到 FEMM: {femm_exe}")
    print("請確認 FEMM 4.2 已安裝到 C:\\femm42")
    exit(1)

# 先用 -lua-script 求解 (FEMM 會自動退出)
print("啟動 FEMM 求解中...")
result = subprocess.run([femm_exe, f'-lua-script={lua_path}'], timeout=120)
print(f"求解完成 (exit code: {result.returncode})")

# 再啟動 FEMM 開啟結果檔讓使用者查看
ans_path = fem_path.replace('.fem', '.ans')
print(f"\n重新開啟 FEMM 顯示結果...")
subprocess.Popen([femm_exe, fem_path.replace('/', '\\')])
print("FEMM 已開啟！")
print(f"  模型檔: {fem_path}")
print(f"  結果檔: {ans_path}")
print("\n提示: 在 FEMM 中點擊 Analysis > View Results (或按 Ctrl+R) 查看磁通密度分佈。")
