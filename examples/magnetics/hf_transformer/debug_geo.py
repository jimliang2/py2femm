"""
診斷腳本：只建構幾何和 block labels，不求解。
用來在 FEMM 視窗中檢查區域分割情況。
"""
import femm
import os

CORE_W   = 6.0
CORE_H   = 20.0
CORE_T   = 4.0
CORE_TOP = 4.0
WIN_W    = 8.0
PRI_W    = 3.0
PRI_H    = 16.0
SEC_W    = 3.0
SEC_H    = 16.0
COIL_GAP = 1.0
BOUND    = 60.0

def add_rect(x0, y0, w, h):
    femm.mi_addnode(x0, y0)
    femm.mi_addnode(x0+w, y0)
    femm.mi_addnode(x0+w, y0+h)
    femm.mi_addnode(x0, y0+h)
    femm.mi_addsegment(x0, y0, x0+w, y0)
    femm.mi_addsegment(x0+w, y0, x0+w, y0+h)
    femm.mi_addsegment(x0+w, y0+h, x0, y0+h)
    femm.mi_addsegment(x0, y0+h, x0, y0)

try:
    femm.closefemm()
except:
    pass

femm.openfemm()
femm.newdocument(0)
femm.mi_probdef(100000, 'millimeters', 'planar', 1e-8, 1, 30, 0)

# 磁芯：用節點和線段畫 — 確保不重疊
x_left   = -6.0
x_mid_l  = 0.0
x_mid_r  = 8.0
x_right  = 12.0
y_bot    = -4.0
y_win_b  = 0.0
y_win_t  = 20.0
y_top    = 24.0

# 所有關鍵節點
for x in [x_left, x_mid_l, x_mid_r, x_right]:
    for y in [y_bot, y_win_b, y_win_t, y_top]:
        femm.mi_addnode(x, y)

# 外框 — 分段畫，使中間節點成為交叉點
# 底邊 (y_bot): x_left → x_mid_l → x_mid_r → x_right
femm.mi_addsegment(x_left, y_bot, x_mid_l, y_bot)
femm.mi_addsegment(x_mid_l, y_bot, x_mid_r, y_bot)
femm.mi_addsegment(x_mid_r, y_bot, x_right, y_bot)
# 頂邊 (y_top): x_left → x_mid_l → x_mid_r → x_right
femm.mi_addsegment(x_left, y_top, x_mid_l, y_top)
femm.mi_addsegment(x_mid_l, y_top, x_mid_r, y_top)
femm.mi_addsegment(x_mid_r, y_top, x_right, y_top)
# 左邊 (x_left): y_bot → y_win_b → y_win_t → y_top
femm.mi_addsegment(x_left, y_bot, x_left, y_win_b)
femm.mi_addsegment(x_left, y_win_b, x_left, y_win_t)
femm.mi_addsegment(x_left, y_win_t, x_left, y_top)
# 右邊 (x_right): y_bot → y_win_b → y_win_t → y_top
femm.mi_addsegment(x_right, y_bot, x_right, y_win_b)
femm.mi_addsegment(x_right, y_win_b, x_right, y_win_t)
femm.mi_addsegment(x_right, y_win_t, x_right, y_top)

# 窗口內水平線 (連接 x_mid_l 和 x_mid_r)
femm.mi_addsegment(x_mid_l, y_win_b, x_mid_r, y_win_b)
femm.mi_addsegment(x_mid_l, y_win_t, x_mid_r, y_win_t)
# 窗口內垂直線 (中柱右邊和外壁左邊)
femm.mi_addsegment(x_mid_l, y_win_b, x_mid_l, y_win_t)
femm.mi_addsegment(x_mid_r, y_win_b, x_mid_r, y_win_t)

# 連接窗口到外框的垂直線（讓區域封閉）
# 中柱右邊延伸到上下蓋
femm.mi_addsegment(x_mid_l, y_bot, x_mid_l, y_win_b)
femm.mi_addsegment(x_mid_l, y_win_t, x_mid_l, y_top)
# 外壁左邊延伸到上下蓋
femm.mi_addsegment(x_mid_r, y_bot, x_mid_r, y_win_b)
femm.mi_addsegment(x_mid_r, y_win_t, x_mid_r, y_top)

print("磁芯幾何完成")
print(f"中柱: x=[{x_left},{x_mid_l}], y=[{y_win_b},{y_win_t}]")
print(f"外壁: x=[{x_mid_r},{x_right}], y=[{y_win_b},{y_win_t}]")
print(f"上蓋: x=[{x_left},{x_right}], y=[{y_win_t},{y_top}]")
print(f"下蓋: x=[{x_left},{x_right}], y=[{y_bot},{y_win_b}]")
print(f"窗口: x=[{x_mid_l},{x_mid_r}], y=[{y_win_b},{y_win_t}]")

# 繞組
pri_x0 = COIL_GAP / 2
pri_y0 = (CORE_H - PRI_H) / 2
add_rect(pri_x0, pri_y0, PRI_W, PRI_H)
sec_x0 = pri_x0 + PRI_W + COIL_GAP
sec_y0 = (CORE_H - SEC_H) / 2
add_rect(sec_x0, sec_y0, SEC_W, SEC_H)

print(f"Pri: x=[{pri_x0},{pri_x0+PRI_W}], y=[{pri_y0},{pri_y0+PRI_H}]")
print(f"Sec: x=[{sec_x0},{sec_x0+SEC_W}], y=[{sec_y0},{sec_y0+SEC_H}]")

# 空氣邊界
add_rect(-BOUND, -BOUND, 2*BOUND, 2*BOUND)

# 材料
femm.mi_addmaterial('N87', 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0)
femm.mi_addmaterial('Cu_pri', 1, 1, 0, 0, 58, 0, 0, 0, 5, 0, 0, 50, 0.1)
femm.mi_addmaterial('Cu_sec', 1, 1, 0, 0, 58, 0, 0, 0, 5, 0, 0, 100, 0.15)
femm.mi_addmaterial('air', 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

# 電路
femm.mi_addcircprop('primary', 0.5, 1)
femm.mi_addcircprop('secondary', 0, 1)

# Block labels — 每個區域一個
# 磁芯被切割成 7 個區域（不是 4 個）：
# 中柱: x=[-6,0], y=[0,20]
# 外壁: x=[8,12], y=[0,20]
# 上蓋左: x=[-6,0], y=[20,24]
# 上蓋中: x=[0,8], y=[20,24]
# 上蓋右: x=[8,12], y=[20,24]
# 下蓋左: x=[-6,0], y=[-4,0]
# 下蓋中: x=[0,8], y=[-4,0]
# 下蓋右: x=[8,12], y=[-4,0]
labels = {
    '中柱':      (-3, 10, 'N87', '<None>', 0),
    '外壁':      (10, 10, 'N87', '<None>', 0),
    '上蓋左':    (-3, 22, 'N87', '<None>', 0),
    '上蓋中':    (4, 22, 'N87', '<None>', 0),
    '上蓋右':    (10, 22, 'N87', '<None>', 0),
    '下蓋左':    (-3, -2, 'N87', '<None>', 0),
    '下蓋中':    (4, -2, 'N87', '<None>', 0),
    '下蓋右':    (10, -2, 'N87', '<None>', 0),
    '窗口空氣':  (0.25, 10, 'air', '<None>', 0),
    'Pri 繞組':  (2, 10, 'Cu_pri', 'primary', 20),
    'Sec 繞組':  (6, 10, 'Cu_sec', 'secondary', 5),
    '外部空氣':  (30, 30, 'air', '<None>', 0),
}

for name, (x, y, mat, circ, turns) in labels.items():
    femm.mi_addblocklabel(x, y)
    femm.mi_selectlabel(x, y)
    femm.mi_setblockprop(mat, 1, 0, circ, 0, 0, turns)
    femm.mi_clearselected()
    print(f"  Label '{name}' at ({x}, {y}) -> {mat}")

# 邊界
femm.mi_addboundprop('a0', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
for seg in [(0, -BOUND), (BOUND, 0), (0, BOUND), (-BOUND, 0)]:
    femm.mi_selectsegment(seg[0], seg[1])
femm.mi_setsegmentprop('a0', 0, 1, 0, 0)
femm.mi_clearselected()

# 保存
femm.mi_saveas(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug.fem'))
print("\n已保存為 debug.fem")
print("請在 FEMM 視窗中檢查。嘗試求解...")

try:
    femm.mi_analyze(1)
    print("mi_analyze 成功！")
    femm.mi_loadsolution()
    print("mi_loadsolution 成功！")
    
    pri_p = femm.mo_getcircuitproperties('primary')
    print(f"Primary: I={pri_p[0]}, V={pri_p[1]}, Flux={pri_p[2]}")
except Exception as e:
    print(f"ERROR: {e}")

print("\nFEMM 保持開啟，請手動檢查。")
femm.closefemm()
