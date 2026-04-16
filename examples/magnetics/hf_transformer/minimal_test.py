"""
精簡測試：只有 EE 磁芯和空氣邊界，不加繞組。
用來找出 "more than one block label" 的根本原因。
"""
import femm
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

try:
    femm.closefemm()
except:
    pass

femm.openfemm()
femm.newdocument(0)
femm.mi_probdef(100000, 'millimeters', 'planar', 1e-8, 1, 30, 0)

# 磁芯座標
x_left, x_mid_l, x_mid_r, x_right = -6.0, 0.0, 8.0, 12.0  
y_bot, y_win_b, y_win_t, y_top = -4.0, 0.0, 20.0, 24.0

# 所有 16 個關鍵節點
for x in [x_left, x_mid_l, x_mid_r, x_right]:
    for y in [y_bot, y_win_b, y_win_t, y_top]:
        femm.mi_addnode(x, y)

# 畫所有線段 — 水平
for y in [y_bot, y_win_b, y_win_t, y_top]:
    if y in [y_win_b, y_win_t]:
        # 窗口水平線只在窗口範圍
        femm.mi_addsegment(x_mid_l, y, x_mid_r, y)
    # 外框水平線分段
    femm.mi_addsegment(x_left, y, x_mid_l, y)
    femm.mi_addsegment(x_mid_l, y, x_mid_r, y)
    femm.mi_addsegment(x_mid_r, y, x_right, y)

# 畫所有線段 — 垂直
for x in [x_left, x_mid_l, x_mid_r, x_right]:
    femm.mi_addsegment(x, y_bot, x, y_win_b)
    femm.mi_addsegment(x, y_win_b, x, y_win_t)
    femm.mi_addsegment(x, y_win_t, x, y_top)

# 空氣邊界
for pt in [(-50,-50), (50,-50), (50,50), (-50,50)]:
    femm.mi_addnode(pt[0], pt[1])
femm.mi_addsegment(-50,-50, 50,-50)
femm.mi_addsegment(50,-50, 50,50)
femm.mi_addsegment(50,50, -50,50)
femm.mi_addsegment(-50,50, -50,-50)

# 材料
femm.mi_addmaterial('ferrite', 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0)
femm.mi_addmaterial('air', 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

# 邊界
femm.mi_addboundprop('a0', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
for seg in [(0,-50), (50,0), (0,50), (-50,0)]:
    femm.mi_selectsegment(seg[0], seg[1])
femm.mi_setsegmentprop('a0', 0, 1, 0, 0)
femm.mi_clearselected()

# 加入繞組矩形
def add_rect(x0, y0, w, h):
    femm.mi_addnode(x0, y0)
    femm.mi_addnode(x0+w, y0)
    femm.mi_addnode(x0+w, y0+h)
    femm.mi_addnode(x0, y0+h)
    femm.mi_addsegment(x0, y0, x0+w, y0)
    femm.mi_addsegment(x0+w, y0, x0+w, y0+h)
    femm.mi_addsegment(x0+w, y0+h, x0, y0+h)
    femm.mi_addsegment(x0, y0+h, x0, y0)

add_rect(0.5, 2, 3, 16)   # pri
add_rect(4.5, 2, 3, 16)   # sec
print("Added windings")

femm.mi_addmaterial('copper', 1, 1, 0, 0, 58, 0, 0, 0, 0, 0, 0, 0, 0)
femm.mi_addcircprop('primary', 0.5, 1)
femm.mi_addcircprop('secondary', 0, 1)

# block labels
regions = [
    ('中柱',   -3, 10, 'ferrite', '<None>', 0),
    ('外壁',   10, 10, 'ferrite', '<None>', 0),
    ('上蓋左', -3, 22, 'ferrite', '<None>', 0),
    ('上蓋中',  4, 22, 'ferrite', '<None>', 0),
    ('上蓋右', 10, 22, 'ferrite', '<None>', 0),
    ('下蓋左', -3, -2, 'ferrite', '<None>', 0),
    ('下蓋中',  4, -2, 'ferrite', '<None>', 0),
    ('下蓋右', 10, -2, 'ferrite', '<None>', 0),
    ('pri',     2, 10, 'copper', 'primary', 20),
    ('sec',     6, 10, 'copper', 'secondary', 5),
    ('窗口空氣', 0.25, 10, 'air', '<None>', 0),
    ('外部',   30, 30, 'air', '<None>', 0),
]

for name, x, y, mat, circ, turns in regions:
    femm.mi_addblocklabel(x, y)
    femm.mi_selectlabel(x, y)
    femm.mi_setblockprop(mat, 1, 0, circ, 0, 0, turns)
    femm.mi_clearselected()
    print(f"  {name}: ({x}, {y}) -> {mat}")

femm.mi_saveas(os.path.join(script_dir, 'minimal_test.fem'))

print("\n嘗試求解...")
try:
    femm.mi_analyze(1)
    print("mi_analyze OK!")
except Exception as e:
    print(f"mi_analyze FAILED: {e}")

try:
    femm.mi_loadsolution()
    print("mi_loadsolution OK!")
except Exception as e:
    print(f"mi_loadsolution FAILED: {e}")

femm.closefemm()
print("Done")
