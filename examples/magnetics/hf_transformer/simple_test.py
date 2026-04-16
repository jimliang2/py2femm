"""
最簡單的 pyfemm 測試：一個線圈在空氣中。
用來驗證 pyfemm 工作流程。
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

# 一個簡單的線圈矩形
femm.mi_addnode(0, 0)
femm.mi_addnode(10, 0)
femm.mi_addnode(10, 10)
femm.mi_addnode(0, 10)
femm.mi_addsegment(0, 0, 10, 0)
femm.mi_addsegment(10, 0, 10, 10)
femm.mi_addsegment(10, 10, 0, 10)
femm.mi_addsegment(0, 10, 0, 0)

# 空氣邊界
femm.mi_addnode(-50, -50)
femm.mi_addnode(60, -50)
femm.mi_addnode(60, 60)
femm.mi_addnode(-50, 60)
femm.mi_addsegment(-50, -50, 60, -50)
femm.mi_addsegment(60, -50, 60, 60)
femm.mi_addsegment(60, 60, -50, 60)
femm.mi_addsegment(-50, 60, -50, -50)

# 邊界
femm.mi_addboundprop('a0', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
for seg in [(5, -50), (60, 5), (5, 60), (-50, 5)]:
    femm.mi_selectsegment(seg[0], seg[1])
femm.mi_setsegmentprop('a0', 0, 1, 0, 0)
femm.mi_clearselected()

# 材料
femm.mi_addmaterial('air', 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
femm.mi_addmaterial('copper', 1, 1, 0, 0, 58, 0, 0, 0, 0, 0, 0, 0, 0)

# 電路
femm.mi_addcircprop('coil', 1, 1)

# 線圈 block
femm.mi_addblocklabel(5, 5)
femm.mi_selectlabel(5, 5)
femm.mi_setblockprop('copper', 1, 0, 'coil', 0, 0, 10)
femm.mi_clearselected()

# 外部空氣
femm.mi_addblocklabel(40, 40)
femm.mi_selectlabel(40, 40)
femm.mi_setblockprop('air', 1, 0, '<None>', 0, 0, 0)
femm.mi_clearselected()

femm.mi_saveas(os.path.join(script_dir, 'simple_test.fem'))
print("已保存 simple_test.fem")
print("正在求解...")
femm.mi_analyze(1)
print("mi_analyze OK!")
femm.mi_loadsolution()
print("mi_loadsolution OK!")

props = femm.mo_getcircuitproperties('coil')
print(f"Coil: I={props[0]}, V={props[1]}, Flux={props[2]}")

femm.mo_showdensityplot(1, 0, 0.01, 0, 'bmag')
print("DONE! FEMM window should show results.")
femm.closefemm()
