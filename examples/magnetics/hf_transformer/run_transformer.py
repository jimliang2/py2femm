"""
高頻變壓器 (High-Frequency Transformer) — 純 pyfemm 範例
========================================================
直接使用 pyfemm (ActiveX/COM) 驅動 FEMM 建模、求解、顯示。
不需要 Lua 中間腳本，避免路徑與 dofile 問題。

模型：EE 磁芯鐵氧體變壓器 (planar 2D cross-section)
    - 磁芯：N87 鐵氧體 (含 BH 曲線)
    - 一次側：20 匝, 0.5 A (100 kHz), Litz wire
    - 二次側：5 匝 (開路), Litz wire
"""

import femm
import os

# ── 幾何參數 (mm) ──────────────────────────────────────────
CORE_W   = 6.0    # 磁芯中柱半寬
CORE_H   = 20.0   # 磁芯窗口高度
CORE_T   = 4.0    # 磁芯壁厚
CORE_TOP = 4.0    # 上下蓋厚度
WIN_W    = 8.0    # 繞線窗口寬度

PRI_W    = 3.0    # 一次側線圈寬度
PRI_H    = 16.0   # 一次側線圈高度
SEC_W    = 3.0    # 二次側線圈寬度
SEC_H    = 16.0   # 二次側線圈高度
COIL_GAP = 1.0    # 一二次側間絕緣間距

BOUND    = 60.0   # 外部空氣邊界半徑

# ── 電氣參數 ───────────────────────────────────────────────
FREQ        = 100_000   # 100 kHz
I_PRIMARY   = 0.5       # 一次側電流 (A, peak)
N_PRIMARY   = 20
N_SECONDARY = 5

# ── N87 BH 曲線 ───────────────────────────────────────────
N87_B = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
N87_H = [0.0, 15.0, 30.0, 45.0, 60.0, 80.0, 110.0, 170.0, 300.0, 800.0, 3000.0]


def add_rect(x0, y0, w, h):
    """畫一個矩形 (四個節點 + 四條邊)"""
    femm.mi_addnode(x0,     y0)
    femm.mi_addnode(x0 + w, y0)
    femm.mi_addnode(x0 + w, y0 + h)
    femm.mi_addnode(x0,     y0 + h)
    femm.mi_addsegment(x0,     y0,     x0 + w, y0)
    femm.mi_addsegment(x0 + w, y0,     x0 + w, y0 + h)
    femm.mi_addsegment(x0 + w, y0 + h, x0,     y0 + h)
    femm.mi_addsegment(x0,     y0 + h, x0,     y0)


def set_block(x, y, mat, circuit='<None>', turns=0):
    """在 (x, y) 放置 block label 並賦予材料"""
    femm.mi_addblocklabel(x, y)
    femm.mi_selectlabel(x, y)
    femm.mi_setblockprop(mat, 1, 0, circuit, 0, 0, turns)
    femm.mi_clearselected()


def main():
    # 切換工作目錄到腳本所在資料夾
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"Working directory: {script_dir}")

    # ── 啟動 FEMM ──
    print("啟動 FEMM...")
    # 先關閉可能已開啟的 FEMM instance
    try:
        femm.closefemm()
    except Exception:
        pass
    femm.openfemm()
    femm.newdocument(0)  # 0 = magnetics problem

    # ── 問題定義 ──
    femm.mi_probdef(FREQ, 'millimeters', 'planar', 1e-8, 1, 30, 0)
    print("已設定問題定義: 100 kHz, planar, mm")

    # ── 繪製幾何 (不重疊的磁芯佈局) ──
    # 座標系統：原點 = 磁芯窗口左下角
    #
    #  磁芯佈局 (截面)：
    #  ┌────────────────────────────┐  y = CORE_H + CORE_TOP = 24
    #  │       上蓋 (N87)           │
    #  ├──────┬────────────┬────────┤  y = CORE_H = 20
    #  │中柱  │  窗口      │ 外壁  │
    #  │(N87) │ [pri][sec] │ (N87) │
    #  │      │            │       │
    #  ├──────┴────────────┴────────┤  y = 0
    #  │       下蓋 (N87)           │
    #  └────────────────────────────┘  y = -CORE_TOP = -4
    # x=-6    x=0         x=8    x=12

    # 整個磁芯外輪廓
    x_left   = -CORE_W          # -6
    x_mid_l  = 0.0              # 中柱右邊/窗口左邊
    x_mid_r  = WIN_W            # 8, 窗口右邊/外壁左邊
    x_right  = WIN_W + CORE_T   # 12
    y_bot    = -CORE_TOP        # -4
    y_win_b  = 0.0              # 窗口底
    y_win_t  = CORE_H           # 20, 窗口頂
    y_top    = CORE_H + CORE_TOP  # 24

    # 加入所有關鍵節點
    for x in [x_left, x_mid_l, x_mid_r, x_right]:
        for y in [y_bot, y_win_b, y_win_t, y_top]:
            femm.mi_addnode(x, y)

    # 外框 — 分段畫，確保中間節點成為交叉點
    # 底邊 (y_bot): 分 3 段
    femm.mi_addsegment(x_left, y_bot, x_mid_l, y_bot)
    femm.mi_addsegment(x_mid_l, y_bot, x_mid_r, y_bot)
    femm.mi_addsegment(x_mid_r, y_bot, x_right, y_bot)
    # 頂邊 (y_top): 分 3 段
    femm.mi_addsegment(x_left, y_top, x_mid_l, y_top)
    femm.mi_addsegment(x_mid_l, y_top, x_mid_r, y_top)
    femm.mi_addsegment(x_mid_r, y_top, x_right, y_top)
    # 左邊 (x_left): 分 3 段
    femm.mi_addsegment(x_left, y_bot, x_left, y_win_b)
    femm.mi_addsegment(x_left, y_win_b, x_left, y_win_t)
    femm.mi_addsegment(x_left, y_win_t, x_left, y_top)
    # 右邊 (x_right): 分 3 段
    femm.mi_addsegment(x_right, y_bot, x_right, y_win_b)
    femm.mi_addsegment(x_right, y_win_b, x_right, y_win_t)
    femm.mi_addsegment(x_right, y_win_t, x_right, y_top)
    # 窗口內水平線
    femm.mi_addsegment(x_mid_l, y_win_b, x_mid_r, y_win_b)
    femm.mi_addsegment(x_mid_l, y_win_t, x_mid_r, y_win_t)
    # 窗口內垂直線
    femm.mi_addsegment(x_mid_l, y_win_b, x_mid_l, y_win_t)
    femm.mi_addsegment(x_mid_r, y_win_b, x_mid_r, y_win_t)
    # 連接窗口到上下蓋的垂直線
    femm.mi_addsegment(x_mid_l, y_bot, x_mid_l, y_win_b)
    femm.mi_addsegment(x_mid_l, y_win_t, x_mid_l, y_top)
    femm.mi_addsegment(x_mid_r, y_bot, x_mid_r, y_win_b)
    femm.mi_addsegment(x_mid_r, y_win_t, x_mid_r, y_top)
    print("已繪製磁芯幾何")

    # 一次側繞組
    pri_x0 = COIL_GAP / 2     # 0.5
    pri_y0 = (CORE_H - PRI_H) / 2  # 2
    add_rect(pri_x0, pri_y0, PRI_W, PRI_H)
    # 二次側繞組
    sec_x0 = pri_x0 + PRI_W + COIL_GAP  # 4.5
    sec_y0 = (CORE_H - SEC_H) / 2       # 2
    add_rect(sec_x0, sec_y0, SEC_W, SEC_H)
    print("已繪製繞組幾何")

    # 空氣邊界
    add_rect(-BOUND, -BOUND, 2 * BOUND, 2 * BOUND)

    # ── 邊界條件 ──
    femm.mi_addboundprop('a0', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    for seg in [(0, -BOUND), (BOUND, 0), (0, BOUND), (-BOUND, 0)]:
        femm.mi_selectsegment(seg[0], seg[1])
    femm.mi_setsegmentprop('a0', 0, 1, 0, 0)
    femm.mi_clearselected()
    print("已設定邊界條件")

    # ── 電路 ──
    femm.mi_addcircprop('primary', I_PRIMARY, 1)
    femm.mi_addcircprop('secondary', 0, 1)
    print("已定義電路: primary 0.5A, secondary 開路")

    # ── 材料 ──
    femm.mi_addmaterial('N87_ferrite', 1, 1, 0, 0, 0.01, 0, 0, 1, 0, 0, 0, 0, 0)
    for b, h in zip(N87_B, N87_H):
        femm.mi_addbhpoint('N87_ferrite', b, h)
    femm.mi_addmaterial('copper_pri', 1, 1, 0, 0, 58, 0, 0, 0, 5, 0, 0, 50, 0.1)
    femm.mi_addmaterial('copper_sec', 1, 1, 0, 0, 58, 0, 0, 0, 5, 0, 0, 100, 0.15)
    femm.mi_addmaterial('air', 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    print("已定義材料: N87, copper_pri, copper_sec, air")

    # ── 區域賦值 ──
    # 磁芯中柱 (x_left~x_mid_l, y_win_b~y_win_t)
    set_block(-CORE_W / 2, CORE_H / 2, 'N87_ferrite')
    # 磁芯外壁 (x_mid_r~x_right, y_win_b~y_win_t)
    set_block((x_mid_r + x_right) / 2, CORE_H / 2, 'N87_ferrite')
    # 磁芯上蓋 — 被 x_mid_l, x_mid_r 切成 3 段
    set_block((x_left + x_mid_l) / 2, (y_win_t + y_top) / 2, 'N87_ferrite')   # 上蓋左
    set_block((x_mid_l + x_mid_r) / 2, (y_win_t + y_top) / 2, 'N87_ferrite')  # 上蓋中
    set_block((x_mid_r + x_right) / 2, (y_win_t + y_top) / 2, 'N87_ferrite')  # 上蓋右
    # 磁芯下蓋 — 被 x_mid_l, x_mid_r 切成 3 段
    set_block((x_left + x_mid_l) / 2, (y_bot + y_win_b) / 2, 'N87_ferrite')   # 下蓋左
    set_block((x_mid_l + x_mid_r) / 2, (y_bot + y_win_b) / 2, 'N87_ferrite')  # 下蓋中
    set_block((x_mid_r + x_right) / 2, (y_bot + y_win_b) / 2, 'N87_ferrite')  # 下蓋右

    # 一次側繞組
    set_block(pri_x0 + PRI_W / 2, CORE_H / 2, 'copper_pri', 'primary', N_PRIMARY)
    # 二次側繞組
    set_block(sec_x0 + SEC_W / 2, CORE_H / 2, 'copper_sec', 'secondary', N_SECONDARY)

    # 窗口內空氣 — 繞組矩形漂浮在窗口內，周圍空氣是連通的，只需一個 label
    set_block(pri_x0 / 2, CORE_H / 2, 'air')

    # 外部空氣 (邊界矩形與磁芯之間)
    set_block(BOUND / 2, BOUND / 2, 'air')
    print("已完成區域賦值")

    # ── 儲存 .fem 並求解 ──
    fem_path = os.path.join(script_dir, 'hf_transformer.fem')
    femm.mi_saveas(fem_path)
    print(f"已儲存模型: {fem_path}")

    print("正在進行網格劃分與求解...")
    femm.mi_analyze(1)
    print("分析完成，正在載入結果...")
    try:
        femm.mi_loadsolution()
    except Exception as e:
        print(f"警告: {e}")
        print("嘗試繼續載入結果...")
        # mi_loadsolution 有時對 multi-label 報 warning 但模型已求解
        # 重新開啟 .ans 檔案手動載入
        ans_path = os.path.join(script_dir, 'hf_transformer.ans')
        if os.path.exists(ans_path):
            femm.callfemm('mi_loadsolution()')
    print("求解完成！")

    # ── 後處理：擷取電路資訊 ──
    pri_props = femm.mo_getcircuitproperties('primary')
    sec_props = femm.mo_getcircuitproperties('secondary')
    print("\n" + "=" * 50)
    print("高頻變壓器模擬結果")
    print("=" * 50)
    print(f"一次側 (primary):   I={pri_props[0]:.4f} A,  V={pri_props[1]:.4f} V,  Flux={pri_props[2]:.6e} Wb")
    print(f"二次側 (secondary): I={sec_props[0]:.4f} A,  V={sec_props[1]:.4f} V,  Flux={sec_props[2]:.6e} Wb")

    # 計算阻抗
    if abs(pri_props[0]) > 1e-12:
        Z_pri = pri_props[1] / pri_props[0]
        print(f"\n一次側阻抗: Z = {abs(Z_pri):.4f} Ω  (|Z| = {abs(Z_pri):.4f})")
        L_pri = Z_pri.imag / (2 * 3.14159265 * FREQ) if hasattr(Z_pri, 'imag') else 0
        print(f"一次側電感:  L ≈ {L_pri * 1e6:.2f} µH") if L_pri else None

    # 匝比
    if abs(sec_props[2]) > 1e-20 and abs(pri_props[2]) > 1e-20:
        ratio = abs(pri_props[2]) / abs(sec_props[2])
        print(f"磁通比 (≈匝比): {ratio:.2f}  (理論 N1/N2 = {N_PRIMARY/N_SECONDARY:.1f})")

    # ── 磁通密度密度圖 ──
    print("\n正在顯示磁通密度分布圖...")
    femm.mo_showdensityplot(1, 0, 0.5, 0, 'bmag')
    femm.mo_zoom(-10, -8, 16, 28)  # 放大到變壓器區域

    print("\n模擬完成！FEMM 視窗已開啟，您可以查看磁通密度分布。")
    print("FEMM 會保持開啟，請手動關閉。")
    # 不呼叫 closefemm，讓使用者檢視結果


if __name__ == "__main__":
    main()
