"""
高頻變壓器 (High-Frequency Transformer) — py2femm 範例
=====================================================
模型：EE 磁芯鐵氧體變壓器 (planar 2D cross-section)
    - 磁芯：N87 鐵氧體 (含 BH 曲線)
    - 一次側：20 匝, 0.5 A (100 kHz)
    - 二次側：5 匝 (開路)
    - 可選氣隙

產出：
    - hf_transformer.lua  — 可直接在 FEMM 執行的 Lua 腳本
    - 一次側 / 二次側阻抗與磁通資訊
    - 磁通密度場圖
"""

import os
import subprocess
import femm  # pyfemm ActiveX interface
from py2femm.magnetics import (
    MagneticMaterial, MagneticDirichlet, BHCurve,
    MagneticVolumeIntegral, LamType,
)
from py2femm.femm_problem import FemmProblem
from py2femm.general import LengthUnit, AutoMeshOption
from py2femm.geometry import Geometry, Line, Node


# ── 幾何參數 (mm) ──────────────────────────────────────────
CORE_W   = 6.0    # 磁芯中柱半寬
CORE_H   = 20.0   # 磁芯窗口高度
CORE_T   = 4.0    # 磁芯壁厚
CORE_TOP = 4.0    # 上下蓋厚度

WIN_W    = 8.0    # 繞線窗口寬度
WIN_H    = CORE_H # 繞線窗口高度

PRI_W    = 3.0    # 一次側線圈寬度
PRI_H    = 16.0   # 一次側線圈高度
SEC_W    = 3.0    # 二次側線圈寬度
SEC_H    = 16.0   # 二次側線圈高度
COIL_GAP = 1.0    # 一二次側間絕緣間距

AIR_GAP  = 0.0    # 中柱氣隙 (mm), 設 0 = 無氣隙

BOUND    = 60.0   # 外部空氣邊界半徑 (足以衰減磁場)

# ── 電氣參數 ───────────────────────────────────────────────
FREQ        = 100_000   # 操作頻率 100 kHz
I_PRIMARY   = 0.5       # 一次側電流 (A, peak)
N_PRIMARY   = 20        # 一次側匝數
N_SECONDARY = 5         # 二次側匝數


# ── N87 鐵氧體 BH 曲線 (典型室溫值) ──────────────────────
N87_B = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
N87_H = [0.0, 15.0, 30.0, 45.0, 60.0, 80.0, 110.0, 170.0, 300.0, 800.0, 3000.0]


def rect_nodes(x0, y0, w, h):
    """建立矩形四角節點 (左下起逆時針)"""
    return [Node(x0, y0), Node(x0 + w, y0), Node(x0 + w, y0 + h), Node(x0, y0 + h)]


def rect_lines(nodes):
    """將四節點連成封閉矩形"""
    return [
        Line(nodes[0], nodes[1]),
        Line(nodes[1], nodes[2]),
        Line(nodes[2], nodes[3]),
        Line(nodes[3], nodes[0]),
    ]


def build_transformer():
    """建立並返回 FemmProblem"""

    problem = FemmProblem(out_file="hf_transformer.csv")
    problem.magnetic_problem(
        freq=FREQ,
        unit=LengthUnit.MILLIMETERS,
        type="planar",
        precision=1e-8,
        depth=1,         # 1 mm 深度 (2D 截面)
        minangle=30,
    )

    geo = Geometry()

    # ── 磁芯幾何 ──────────────────────────────────────────
    # 座標原點 = 磁芯窗口左下角
    # 中柱 (左側)
    core_left = rect_nodes(-CORE_W, -CORE_TOP, CORE_W, CORE_H + 2 * CORE_TOP)
    # 外壁 (右側)
    core_right_x = WIN_W
    core_right = rect_nodes(core_right_x, -CORE_TOP, CORE_T, CORE_H + 2 * CORE_TOP)
    # 上蓋
    core_top = rect_nodes(-CORE_W, CORE_H, CORE_W + WIN_W + CORE_T, CORE_TOP)
    # 下蓋
    core_bot = rect_nodes(-CORE_W, -CORE_TOP, CORE_W + WIN_W + CORE_T, CORE_TOP)

    for nodes in [core_left, core_right, core_top, core_bot]:
        geo.nodes += nodes
        geo.lines += rect_lines(nodes)

    # 氣隙 (在中柱中間開一條水平切口)
    if AIR_GAP > 0:
        gap_y = CORE_H / 2 - AIR_GAP / 2
        gap_top_y = CORE_H / 2 + AIR_GAP / 2
        gap_nodes = [
            Node(-CORE_W, gap_y), Node(0, gap_y),
            Node(-CORE_W, gap_top_y), Node(0, gap_top_y),
        ]
        geo.nodes += gap_nodes
        geo.lines += [
            Line(gap_nodes[0], gap_nodes[1]),
            Line(gap_nodes[2], gap_nodes[3]),
        ]

    # ── 繞線幾何 ────────────────────────────────────────
    pri_x0 = COIL_GAP / 2
    pri_y0 = (CORE_H - PRI_H) / 2
    pri_nodes = rect_nodes(pri_x0, pri_y0, PRI_W, PRI_H)

    sec_x0 = pri_x0 + PRI_W + COIL_GAP
    sec_y0 = (CORE_H - SEC_H) / 2
    sec_nodes = rect_nodes(sec_x0, sec_y0, SEC_W, SEC_H)

    for nodes in [pri_nodes, sec_nodes]:
        geo.nodes += nodes
        geo.lines += rect_lines(nodes)

    # ── 空氣邊界 (大矩形) ──────────────────────────────
    bnd_nodes = rect_nodes(-BOUND, -BOUND, 2 * BOUND, 2 * BOUND)
    geo.nodes += bnd_nodes
    bnd_lines = rect_lines(bnd_nodes)
    geo.lines += bnd_lines

    # 寫入幾何
    problem.create_geometry(geo)

    # ── 邊界條件 ────────────────────────────────────────
    a0 = MagneticDirichlet(name="a0", a_0=0, a_1=0, a_2=0, phi=0)
    problem.add_boundary(a0)
    for line in bnd_lines:
        problem.set_boundary_definition_segment(line.selection_point(), a0)

    # ── 電路定義 ────────────────────────────────────────
    problem.add_circuit_property("primary", I_PRIMARY, 1)   # 串聯
    problem.add_circuit_property("secondary", 0, 1)         # 開路

    # ── 材料定義 ────────────────────────────────────────
    # 1) N87 鐵氧體磁芯
    ferrite = MagneticMaterial(
        material_name="N87_ferrite",
        mu_x=1,       # BH 曲線會覆蓋
        mu_y=1,
        Sigma=0.01,   # 鐵氧體電導率極低 (S/m)
        Lam_d=0,
        lam_fill=1,
        LamType=LamType.NOT_LAMINATED,
    )
    problem.add_material(ferrite)
    # 加入 BH 曲線
    bh = BHCurve(M="N87_ferrite", B=N87_B, H=N87_H)
    problem.lua_script.append(str(bh))

    # 2) 銅 — 一次側 (利茲線，降低趨膚效應)
    copper_pri = MagneticMaterial(
        material_name="copper_pri",
        mu_x=1,
        mu_y=1,
        Sigma=58.0,           # 銅電導率 MS/m
        LamType=LamType.LITZ_WIRE,
        NStrands=50,          # 50 股
        WireD=0.1,            # 單股 0.1mm
    )
    problem.add_material(copper_pri)

    # 3) 銅 — 二次側
    copper_sec = MagneticMaterial(
        material_name="copper_sec",
        mu_x=1,
        mu_y=1,
        Sigma=58.0,
        LamType=LamType.LITZ_WIRE,
        NStrands=100,
        WireD=0.15,
    )
    problem.add_material(copper_sec)

    # 4) 空氣
    air = MagneticMaterial(material_name="air")
    problem.add_material(air)

    # 5) 氣隙材料 (若有)
    if AIR_GAP > 0:
        air_gap_mat = MagneticMaterial(material_name="air_gap")
        problem.add_material(air_gap_mat)

    # ── 區域賦值 ────────────────────────────────────────
    # 磁芯 — 中柱
    core_center = Node(-CORE_W / 2, CORE_H / 2)
    problem.add_blocklabel(core_center)
    problem.select_label(core_center)
    problem.set_blockprop("N87_ferrite", automesh=AutoMeshOption.AUTOMESH, meshsize=0)
    problem.clear_selected()

    # 磁芯 — 上蓋
    top_center = Node(WIN_W / 2, CORE_H + CORE_TOP / 2)
    problem.add_blocklabel(top_center)
    problem.select_label(top_center)
    problem.set_blockprop("N87_ferrite", automesh=AutoMeshOption.AUTOMESH, meshsize=0)
    problem.clear_selected()

    # 磁芯 — 下蓋
    bot_center = Node(WIN_W / 2, -CORE_TOP / 2)
    problem.add_blocklabel(bot_center)
    problem.select_label(bot_center)
    problem.set_blockprop("N87_ferrite", automesh=AutoMeshOption.AUTOMESH, meshsize=0)
    problem.clear_selected()

    # 磁芯 — 外壁
    right_center = Node(core_right_x + CORE_T / 2, CORE_H / 2)
    problem.add_blocklabel(right_center)
    problem.select_label(right_center)
    problem.set_blockprop("N87_ferrite", automesh=AutoMeshOption.AUTOMESH, meshsize=0)
    problem.clear_selected()

    # 一次側繞組
    pri_center = Node(pri_x0 + PRI_W / 2, CORE_H / 2)
    problem.add_blocklabel(pri_center)
    problem.select_label(pri_center)
    problem.set_blockprop(
        "copper_pri",
        automesh=AutoMeshOption.AUTOMESH,
        meshsize=0,
        circuit_name="primary",
        turns=N_PRIMARY,
    )
    problem.clear_selected()

    # 二次側繞組
    sec_center = Node(sec_x0 + SEC_W / 2, CORE_H / 2)
    problem.add_blocklabel(sec_center)
    problem.select_label(sec_center)
    problem.set_blockprop(
        "copper_sec",
        automesh=AutoMeshOption.AUTOMESH,
        meshsize=0,
        circuit_name="secondary",
        turns=N_SECONDARY,
    )
    problem.clear_selected()

    # 窗口內空氣 (繞線區域外)
    air_win = Node(pri_x0 + PRI_W + COIL_GAP / 2, 1.0)
    problem.define_block_label(air_win, air)

    # 氣隙 (若有)
    if AIR_GAP > 0:
        gap_center = Node(-CORE_W / 2, CORE_H / 2)
        problem.add_blocklabel(gap_center)
        problem.select_label(gap_center)
        problem.set_blockprop("air_gap", automesh=AutoMeshOption.AUTOMESH, meshsize=0)
        problem.clear_selected()

    # 外部空氣
    air_outer = Node(BOUND / 2, BOUND / 2)
    problem.define_block_label(air_outer, air)

    # ── 求解 ────────────────────────────────────────────
    problem.make_analysis("hf_transformer")

    # ── 後處理 ────────────────────────────────────────
    # 取得一次側電路阻抗資訊
    problem.get_circuit_properties("primary", result="pri")
    problem.get_circuit_properties("secondary", result="sec")

    # 取樣點磁通密度 (沿中柱軸線)
    for i in range(21):
        y = i * CORE_H / 20
        problem.get_point_values(Node(-CORE_W / 2, y))

    # 繞組損耗 (渦流+銅損)
    problem.get_integral_values(
        [pri_center], save_image=False,
        variable_name=MagneticVolumeIntegral.ResistiveLoss,
    )

    problem.get_integral_values(
        [sec_center], save_image=False,
        variable_name=MagneticVolumeIntegral.ResistiveLoss,
    )

    # 磁芯鐵損
    problem.get_integral_values(
        [core_center], save_image=False,
        variable_name=MagneticVolumeIntegral.HysteresysLoss,
    )

    # 儲存磁場圖
    problem.get_integral_values(
        [core_center], save_image=True,
        variable_name=MagneticVolumeIntegral.A,
    )

    # 產生 Lua 腳本
    lua_name = "hf_transformer.lua"
    problem.write(lua_name)
    print(f"Lua script generated: {lua_name}")

    return problem, lua_name


if __name__ == "__main__":
    problem, lua_name = build_transformer()

    # 用 pyfemm (ActiveX) 直接驅動 FEMM 執行 Lua 腳本
    lua_path = os.path.join(os.getcwd(), lua_name)
    print(f"Lua script at: {lua_path}")
    print("Opening FEMM via ActiveX (pyfemm)...")
    femm.openfemm()
    femm.opendocument(lua_path.replace("\\", "/"))  # 嘗試直接開 lua
    # 實際上 pyfemm 的 callfemm 可執行任意 lua 指令
    femm.callfemm(f'dofile("{lua_path.replace(chr(92), "/")}")')
    print("Done! FEMM should now display the transformer model and results.")
