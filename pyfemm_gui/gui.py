"""
PyFEMM Studio - Professional FEMM pre/post-processing GUI (PySide6).
功能 Features: COM / Lua CLI 雙模式 dual-mode, 材料庫 material library,
電路 circuits, 求解器 solver, 磁場取樣 field sampling, 專案 I/O,
變壓器參數 transformer parameter extraction, 材質更換 material editing.
"""
import json, math, os, sys

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction, QImage, QPixmap, QPainter
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QGraphicsPixmapItem, QGraphicsScene,
    QGraphicsView, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMainWindow, QMenu, QMenuBar, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QSpinBox, QSplitter, QStatusBar, QTabWidget,
    QTextEdit, QToolBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from pyfemm_gui.femm_backend import FemmBackend


class ZoomableGraphicsView(QGraphicsView):
    """QGraphicsView with mouse-wheel zoom + drag-to-pan for density plot."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = None
        self._zoom = 0
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setStyleSheet("background: #fafafa; border: 1px solid #ccc;")
        self.setMinimumHeight(200)

    def set_pixmap(self, pm: QPixmap):
        """Display a new pixmap, replacing any previous one."""
        self._scene.clear()
        self._pixmap_item = self._scene.addPixmap(pm)
        self.setSceneRect(pm.rect().adjusted(-20, -20, 20, 20))
        self.fit_view()

    def fit_view(self):
        """Fit the pixmap to the viewport."""
        if self._pixmap_item:
            self.fitInView(self._pixmap_item, Qt.KeepAspectRatio)
            self._zoom = 0

    def wheelEvent(self, event):
        """Zoom in/out with mouse wheel."""
        factor = 1.25
        if event.angleDelta().y() > 0:
            self._zoom += 1
            self.scale(factor, factor)
        elif event.angleDelta().y() < 0:
            self._zoom -= 1
            self.scale(1 / factor, 1 / factor)

    def zoom_in(self):
        self._zoom += 1
        self.scale(1.25, 1.25)

    def zoom_out(self):
        self._zoom -= 1
        self.scale(1 / 1.25, 1 / 1.25)

APP_NAME = "PyFEMM Studio"
APP_VERSION = "1.0.0"

QSS = """
QMainWindow { background: #f5f5f5; }
QMenuBar { background: #2b579a; color: white; font-size: 13px; }
QMenuBar::item:selected { background: #3a6bc5; }
QMenu { background: white; }
QMenu::item:selected { background: #d0e0ff; }
QToolBar { background: #e8eef7; spacing: 6px; padding: 4px;
           border-bottom: 1px solid #b0b0b0; }
QStatusBar { background: #2b579a; color: white; font-size: 12px; }
QGroupBox { font-weight: bold; border: 1px solid #c0c0c0;
            border-radius: 4px; margin-top: 10px; padding-top: 14px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; }
QPushButton { background: #2b579a; color: white; border: none;
              border-radius: 4px; padding: 7px 18px; font-size: 13px; }
QPushButton:hover { background: #3a6bc5; }
QPushButton:pressed { background: #1e3d70; }
QPushButton:disabled { background: #aaa; }
QTreeWidget { font-size: 12px; }
QTextEdit { font-family: Consolas, monospace; font-size: 12px; }
QTabWidget::pane { border: 1px solid #c0c0c0; }
QLabel { font-size: 12px; }
"""


class AnalyzeWorker(QThread):
    finished = Signal(bool, str)
    def __init__(self, backend):
        super().__init__()
        self.backend = backend
    def run(self):
        try:
            self.backend.analyze()
            self.finished.emit(True, "分析完成 Analysis completed successfully.")
        except Exception as e:
            self.finished.emit(False, str(e))


class SampleDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("取樣設定 Sampling Settings")
        self.setMinimumWidth(400)
        form = QFormLayout()
        # FEMM model coordinates are in mm
        self.xmin = QDoubleSpinBox(); self.xmin.setRange(-1000, 1000); self.xmin.setValue(-8); self.xmin.setDecimals(2); self.xmin.setSuffix(" mm")
        self.xmax = QDoubleSpinBox(); self.xmax.setRange(-1000, 1000); self.xmax.setValue(16); self.xmax.setDecimals(2); self.xmax.setSuffix(" mm")
        self.ymin = QDoubleSpinBox(); self.ymin.setRange(-1000, 1000); self.ymin.setValue(-6); self.ymin.setDecimals(2); self.ymin.setSuffix(" mm")
        self.ymax = QDoubleSpinBox(); self.ymax.setRange(-1000, 1000); self.ymax.setValue(26); self.ymax.setDecimals(2); self.ymax.setSuffix(" mm")
        self.nx = QSpinBox(); self.nx.setRange(4, 2000); self.nx.setValue(200)
        self.ny = QSpinBox(); self.ny.setRange(4, 2000); self.ny.setValue(200)
        form.addRow("X 最小值 X min:", self.xmin)
        form.addRow("X 最大值 X max:", self.xmax)
        form.addRow("Y 最小值 Y min:", self.ymin)
        form.addRow("Y 最大值 Y max:", self.ymax)
        form.addRow("X 取樣點數 X points:", self.nx)
        form.addRow("Y 取樣點數 Y points:", self.ny)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay = QVBoxLayout()
        lay.addLayout(form)
        lay.addWidget(btns)
        self.setLayout(lay)


class CircuitDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新增電路 Add Circuit")
        form = QFormLayout()
        self.name_edit = QLineEdit("Primary")
        self.current_spin = QDoubleSpinBox()
        self.current_spin.setRange(-1e9, 1e9)
        self.current_spin.setDecimals(6)
        self.current_spin.setValue(0.5)
        self.series_combo = QComboBox()
        self.series_combo.addItems(["串聯 Series (1)", "並聯 Parallel (0)"])
        form.addRow("電路名稱 Circuit name:", self.name_edit)
        form.addRow("電流 Current (A):", self.current_spin)
        form.addRow("連接方式 Connection:", self.series_combo)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay = QVBoxLayout()
        lay.addLayout(form)
        lay.addWidget(btns)
        self.setLayout(lay)


class TransformerParamDialog(QDialog):
    """Dialog for configuring transformer parameter extraction settings."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("變壓器參數設定 Transformer Parameter Settings")
        self.setMinimumWidth(380)
        form = QFormLayout()
        self.pri_edit = QLineEdit("primary")
        self.sec_edit = QLineEdit("secondary")
        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(0, 1e9)
        self.freq_spin.setDecimals(0)
        self.freq_spin.setValue(100000)
        self.freq_spin.setSuffix(" Hz")
        form.addRow("一次側電路名稱 Primary circuit:", self.pri_edit)
        form.addRow("二次側電路名稱 Secondary circuit:", self.sec_edit)
        form.addRow("頻率 Frequency:", self.freq_spin)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay = QVBoxLayout(); lay.addLayout(form); lay.addWidget(btns)
        self.setLayout(lay)


class ChangeMaterialDialog(QDialog):
    """Dialog to change a material assignment in the model."""
    def __init__(self, old_name, material_names, parent=None):
        super().__init__(parent)
        self.setWindowTitle("更換材質 Change Material")
        self.setMinimumWidth(400)
        lay = QVBoxLayout()
        lay.addWidget(QLabel(f"現有材質 Current material:  <b>{old_name}</b>"))
        form = QFormLayout()
        self.combo = QComboBox()
        self.combo.addItems(material_names)
        # Try to preselect old_name
        idx = self.combo.findText(old_name)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)
        form.addRow("新材質 New material:", self.combo)
        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)
        self.setLayout(lay)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1280, 800)

        self.backend = FemmBackend()
        self.materials = {}
        self._load_material_db()

        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._update_status()
        self._load_demo_example()
        # Deferred log for material loading (log widget now exists)
        om_count = getattr(self, "_om_count", 0)
        if om_count:
            self._log(f"[INFO] 已載入 OpenMagnetics 材料庫 ({om_count} 種材料)")
            self._log(f"       Source: github.com/OpenMagnetics/MAS")

    # ---- 選單 Menu ----
    def _build_menu(self):
        bar = self.menuBar()
        # 檔案 File
        fm = bar.addMenu("檔案 File(&F)")
        fm.addAction(self._act("開啟模型 Open .fem...", self.open_fem, "Ctrl+O"))
        fm.addAction(self._act("載入解答 Load .ans...", self.open_ans))
        fm.addSeparator()
        fm.addAction(self._act("儲存專案 Save Project...", self.save_project, "Ctrl+S"))
        fm.addAction(self._act("載入專案 Load Project...", self.load_project, "Ctrl+Shift+O"))
        fm.addSeparator()
        fm.addAction(self._act("載入範例 Load Demo Example", self._load_demo_and_notify))
        fm.addSeparator()
        fm.addAction(self._act("結束 Exit", self.close, "Ctrl+Q"))
        # FEMM 連線
        mm = bar.addMenu("FEMM 連線(&M)")
        mm.addAction(self._act("啟動 FEMM (COM) Start FEMM", self.start_femm_com))
        mm.addAction(self._act("使用 Lua CLI 模式 Use Lua CLI", self.start_femm_lua))
        mm.addSeparator()
        mm.addAction(self._act("關閉 FEMM Close FEMM", self.stop_femm))
        # 模型 Model
        dm = bar.addMenu("模型 Model(&D)")
        dm.addAction(self._act("新增電路 Add Circuit...", self.add_circuit))
        dm.addAction(self._act("從材料庫新增 Add Material...", self.add_material_from_lib))
        dm.addAction(self._act("查看模型材質 View Model Materials", self.view_model_materials))
        dm.addAction(self._act("更換模型材質 Change Material...", self.change_model_material))
        dm.addSeparator()
        dm.addAction(self._act("執行分析 Run Analysis", self.run_analyze, "F5"))
        # 後處理 Post
        pm = bar.addMenu("後處理 Post(&P)")
        pm.addAction(self._act("密度圖(APP內) Density Plot (F7)", self._sample_and_show_inline, "F7"))
        pm.addAction(self._act("密度圖(FEMM) Density in FEMM", self.show_density))
        pm.addAction(self._act("變壓器參數 Transformer Params...", self.extract_transformer_params, "F6"))
        pm.addAction(self._act("匯出密度圖 PNG Export Density PNG", self.sample_and_export))
        # 說明 Help
        hm = bar.addMenu("說明 Help(&H)")
        hm.addAction(self._act("關於 About", self.show_about))

    def _act(self, text, slot, shortcut=None):
        a = QAction(text, self)
        a.triggered.connect(slot)
        if shortcut:
            a.setShortcut(shortcut)
        return a

    # ---- 工具列 Toolbar ----
    def _build_toolbar(self):
        tb = QToolBar("Main"); tb.setMovable(False); self.addToolBar(tb)
        tb.addAction(self._act("COM 連線 Connect", self.start_femm_com))
        tb.addAction(self._act("Lua 模式 Mode", self.start_femm_lua))
        tb.addSeparator()
        tb.addAction(self._act("開啟 .fem Open", self.open_fem))
        tb.addAction(self._act("載入 .ans Load", self.open_ans))
        tb.addSeparator()
        tb.addAction(self._act("分析 Analyze (F5)", self.run_analyze))
        tb.addAction(self._act("變壓器參數 Xfmr (F6)", self.extract_transformer_params))
        tb.addAction(self._act("密度圖 Density (F7)", self._sample_and_show_inline))
        tb.addAction(self._act("匯出 PNG Export", self.sample_and_export))

    # ---- 中央面板 Central Panel ----
    def _build_central(self):
        sp = QSplitter(Qt.Horizontal)
        # 左側：專案瀏覽器 Left: Project Browser
        left = QWidget(); ll = QVBoxLayout(); ll.setContentsMargins(4,4,4,4)
        lbl = QLabel("專案瀏覽器 Project Browser")
        lbl.setStyleSheet("font-weight:bold; font-size:13px;")
        ll.addWidget(lbl)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["項目 Item", "值 Value"])
        self.tree.setColumnWidth(0, 210)
        self._tr_conn = QTreeWidgetItem(self.tree, ["連線狀態 Connection", "未連線 not connected"])
        self._tr_fem  = QTreeWidgetItem(self.tree, ["模型檔案 FEM File", "(無 none)"])
        self._tr_mat  = QTreeWidgetItem(self.tree, ["材料庫 Materials", f"{self._mat_count()} 項 items"])
        ll.addWidget(self.tree)
        left.setLayout(ll)
        # 右側：頁籤 Right: Tabs
        self.tabs = QTabWidget()
        # 日誌 Log
        self.log = QTextEdit(); self.log.setReadOnly(True)
        self.tabs.addTab(self.log, "日誌 Log")
        # 材料庫 Materials Library
        mp = QWidget(); ml = QVBoxLayout()
        self.mat_tree = QTreeWidget()
        self.mat_tree.setHeaderLabels([
            "材料 Material", "μx", "μy", "Hc (A/m)",
            "σ (MS/m)", "LamType", "Lam_d(mm)", "備註 Note"])
        self.mat_tree.setColumnWidth(0, 240)
        for ci in range(1, 7): self.mat_tree.setColumnWidth(ci, 75)
        self.mat_tree.setColumnWidth(7, 200)
        self._fill_mat_tree()
        ml.addWidget(self.mat_tree); mp.setLayout(ml)
        self.tabs.addTab(mp, f"材料庫 Materials ({self._mat_count()})")
        # 模型材質 Model Materials (view/edit assigned materials)
        mmp = QWidget(); mml = QVBoxLayout()
        mml.setContentsMargins(6, 6, 6, 6)
        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("重新讀取 Refresh")
        btn_refresh.clicked.connect(self.view_model_materials)
        btn_change = QPushButton("更換選取材質 Change Selected")
        btn_change.clicked.connect(self._change_selected_model_material)
        btn_row.addWidget(btn_refresh); btn_row.addWidget(btn_change)
        btn_row.addStretch()
        mml.addLayout(btn_row)
        self.model_mat_tree = QTreeWidget()
        self.model_mat_tree.setHeaderLabels(["#", "模型中的材質 Material in Model"])
        self.model_mat_tree.setColumnWidth(0, 40)
        self.model_mat_tree.setColumnWidth(1, 350)
        mml.addWidget(self.model_mat_tree); mmp.setLayout(mml)
        self.tabs.addTab(mmp, "模型材質 Model Materials")
        # 變壓器參數 Transformer Parameters
        tp = QWidget(); tl = QVBoxLayout()
        tl.setContentsMargins(6, 6, 6, 6)
        tp_btn_row = QHBoxLayout()
        btn_extract = QPushButton("提取參數 Extract Params (F6)")
        btn_extract.clicked.connect(self.extract_transformer_params)
        tp_btn_row.addWidget(btn_extract); tp_btn_row.addStretch()
        tl.addLayout(tp_btn_row)
        self.xfmr_text = QTextEdit(); self.xfmr_text.setReadOnly(True)
        self.xfmr_text.setPlaceholderText(
            "先執行分析 (F5)，再按「提取參數 (F6)」顯示完整變壓器參數。\n"
            "Run analysis (F5) first, then click 'Extract Params (F6)' for full transformer parameters.")
        tl.addWidget(self.xfmr_text); tp.setLayout(tl)
        self.tabs.addTab(tp, "變壓器參數 Transformer")
        # 變壓器設計 Transformer Design
        tdp = QWidget(); tdl = QVBoxLayout()
        tdl.setContentsMargins(6, 6, 6, 6)
        td_title = QLabel("變壓器設計 Transformer Design")
        td_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #2b579a;")
        tdl.addWidget(td_title)
        # --- 鐵芯 Core parameters ---
        core_grp = QGroupBox("鐵芯參數 Core Parameters")
        core_form = QFormLayout()
        self.td_core_type = QComboBox()
        self.td_core_type.addItems(["EE", "EI", "ER", "PQ", "RM", "Toroid"])
        self.td_core_w = QDoubleSpinBox(); self.td_core_w.setRange(1, 200); self.td_core_w.setValue(6); self.td_core_w.setSuffix(" mm"); self.td_core_w.setDecimals(2)
        self.td_core_h = QDoubleSpinBox(); self.td_core_h.setRange(1, 200); self.td_core_h.setValue(8); self.td_core_h.setSuffix(" mm"); self.td_core_h.setDecimals(2)
        self.td_core_d = QDoubleSpinBox(); self.td_core_d.setRange(0.1, 200); self.td_core_d.setValue(4); self.td_core_d.setSuffix(" mm"); self.td_core_d.setDecimals(2)
        self.td_window_w = QDoubleSpinBox(); self.td_window_w.setRange(0.5, 100); self.td_window_w.setValue(4); self.td_window_w.setSuffix(" mm"); self.td_window_w.setDecimals(2)
        self.td_window_h = QDoubleSpinBox(); self.td_window_h.setRange(0.5, 200); self.td_window_h.setValue(20); self.td_window_h.setSuffix(" mm"); self.td_window_h.setDecimals(2)
        self.td_core_mat = QComboBox()
        self.td_core_mat.addItems([n for mats in self.materials.values() for n in mats])
        idx = self.td_core_mat.findText("3C90 Ferrite", Qt.MatchContains)
        if idx >= 0: self.td_core_mat.setCurrentIndex(idx)
        core_form.addRow("鐵芯型式 Core type:", self.td_core_type)
        core_form.addRow("中柱寬 Center leg W:", self.td_core_w)
        core_form.addRow("中柱高 Center leg H:", self.td_core_h)
        core_form.addRow("鐵芯深度 Core depth:", self.td_core_d)
        core_form.addRow("窗口寬 Window W:", self.td_window_w)
        core_form.addRow("窗口高 Window H:", self.td_window_h)
        core_form.addRow("鐵芯材料 Core material:", self.td_core_mat)
        core_grp.setLayout(core_form)
        # --- 繞組 Winding parameters ---
        wind_grp = QGroupBox("繞組參數 Winding Parameters")
        wind_form = QFormLayout()
        self.td_n_pri = QSpinBox(); self.td_n_pri.setRange(1, 10000); self.td_n_pri.setValue(10)
        self.td_n_sec = QSpinBox(); self.td_n_sec.setRange(1, 10000); self.td_n_sec.setValue(10)
        self.td_wire_d_pri = QDoubleSpinBox(); self.td_wire_d_pri.setRange(0.01, 10); self.td_wire_d_pri.setValue(0.3); self.td_wire_d_pri.setSuffix(" mm"); self.td_wire_d_pri.setDecimals(3)
        self.td_wire_d_sec = QDoubleSpinBox(); self.td_wire_d_sec.setRange(0.01, 10); self.td_wire_d_sec.setValue(0.3); self.td_wire_d_sec.setSuffix(" mm"); self.td_wire_d_sec.setDecimals(3)
        self.td_i_pri = QDoubleSpinBox(); self.td_i_pri.setRange(0, 1e6); self.td_i_pri.setValue(0.5); self.td_i_pri.setSuffix(" A"); self.td_i_pri.setDecimals(4)
        self.td_i_sec = QDoubleSpinBox(); self.td_i_sec.setRange(0, 1e6); self.td_i_sec.setValue(0); self.td_i_sec.setSuffix(" A"); self.td_i_sec.setDecimals(4)
        self.td_freq = QDoubleSpinBox(); self.td_freq.setRange(0, 1e9); self.td_freq.setValue(100000); self.td_freq.setSuffix(" Hz"); self.td_freq.setDecimals(0)
        self.td_insul = QDoubleSpinBox(); self.td_insul.setRange(0, 10); self.td_insul.setValue(0.5); self.td_insul.setSuffix(" mm"); self.td_insul.setDecimals(2)
        self.td_wind_mat = QComboBox()
        self.td_wind_mat.addItems([n for mats in self.materials.values() for n in mats])
        idx = self.td_wind_mat.findText("Copper", Qt.MatchContains)
        if idx < 0: idx = self.td_wind_mat.findText("Magnet Wire", Qt.MatchContains)
        if idx >= 0: self.td_wind_mat.setCurrentIndex(idx)
        wind_form.addRow("一次側匝數 N_pri:", self.td_n_pri)
        wind_form.addRow("二次側匝數 N_sec:", self.td_n_sec)
        wind_form.addRow("一次側線徑 Wire Ø pri:", self.td_wire_d_pri)
        wind_form.addRow("二次側線徑 Wire Ø sec:", self.td_wire_d_sec)
        wind_form.addRow("一次側電流 I_pri:", self.td_i_pri)
        wind_form.addRow("二次側電流 I_sec:", self.td_i_sec)
        wind_form.addRow("頻率 Frequency:", self.td_freq)
        wind_form.addRow("繞組間距 Insulation gap:", self.td_insul)
        wind_form.addRow("導線材料 Wire material:", self.td_wind_mat)
        wind_grp.setLayout(wind_form)
        # --- Buttons ---
        td_btn_row = QHBoxLayout()
        btn_gen = QPushButton("▶ 產生模型 Generate Model")
        btn_gen.clicked.connect(self._generate_transformer_model)
        btn_gen_run = QPushButton("▶▶ 產生+分析 Generate && Analyze")
        btn_gen_run.clicked.connect(self._generate_and_analyze)
        td_btn_row.addWidget(btn_gen); td_btn_row.addWidget(btn_gen_run)
        td_btn_row.addStretch()
        # Layout: two groups side-by-side + buttons + output
        td_groups = QHBoxLayout()
        td_groups.addWidget(core_grp); td_groups.addWidget(wind_grp)
        tdl.addLayout(td_groups)
        tdl.addLayout(td_btn_row)
        self.td_output = QTextEdit(); self.td_output.setReadOnly(True)
        self.td_output.setPlaceholderText(
            "設定參數後按「產生模型」\nSet parameters then click 'Generate Model'")
        tdl.addWidget(self.td_output)
        tdp.setLayout(tdl)
        self.tabs.addTab(tdp, "變壓器設計 Design")
        # 結果 Results
        rp = QWidget(); rl = QVBoxLayout()
        self.result_text = QTextEdit(); self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("分析結果將在此顯示 Analysis results will appear here...")
        rl.addWidget(self.result_text); rp.setLayout(rl)
        self.tabs.addTab(rp, "結果 Results")
        # 密度圖 Density Plot — use a vertical splitter for image vs report
        dp = QWidget(); dl = QVBoxLayout()
        dl.setContentsMargins(4, 4, 4, 4); dl.setSpacing(4)
        dp_btn_row = QHBoxLayout()
        dp_btn_row.setSpacing(6)
        btn_sample_show = QPushButton("▶ 取樣顯示 Sample")
        btn_sample_show.clicked.connect(self._sample_and_show_inline)
        btn_export_png = QPushButton("💾 匯出 PNG")
        btn_export_png.clicked.connect(self.sample_and_export)
        btn_femm_density = QPushButton("🔍 FEMM 密度圖")
        btn_femm_density.clicked.connect(self.show_density)
        btn_zoom_in = QPushButton("🔍+ 放大 Zoom In")
        btn_zoom_out = QPushButton("🔍- 縮小 Zoom Out")
        btn_zoom_fit = QPushButton("⊞ 適合視窗 Fit")
        for btn in (btn_sample_show, btn_export_png, btn_femm_density,
                    btn_zoom_in, btn_zoom_out, btn_zoom_fit):
            btn.setFixedHeight(30)
        dp_btn_row.addWidget(btn_sample_show)
        dp_btn_row.addWidget(btn_export_png)
        dp_btn_row.addWidget(btn_femm_density)
        dp_btn_row.addWidget(btn_zoom_in)
        dp_btn_row.addWidget(btn_zoom_out)
        dp_btn_row.addWidget(btn_zoom_fit)
        dp_btn_row.addStretch()
        dl.addLayout(dp_btn_row)
        # Splitter: image (top) + report (bottom), user can drag divider
        self._density_splitter = QSplitter(Qt.Vertical)
        self.density_view = ZoomableGraphicsView()
        btn_zoom_in.clicked.connect(self.density_view.zoom_in)
        btn_zoom_out.clicked.connect(self.density_view.zoom_out)
        btn_zoom_fit.clicked.connect(self.density_view.fit_view)
        self._density_splitter.addWidget(self.density_view)
        self.density_report = QTextEdit()
        self.density_report.setReadOnly(True)
        self.density_report.setPlaceholderText(
            "分析報告將在此顯示 Analysis report will appear here...")
        self._density_splitter.addWidget(self.density_report)
        # 圖片佔 80%, 報告佔 20%
        self._density_splitter.setStretchFactor(0, 4)
        self._density_splitter.setStretchFactor(1, 1)
        dl.addWidget(self._density_splitter)
        dp.setLayout(dl)
        self.tabs.addTab(dp, "密度圖 Density Plot")
        sp.addWidget(left); sp.addWidget(self.tabs)
        sp.setStretchFactor(0, 1); sp.setStretchFactor(1, 3)
        self.setCentralWidget(sp)

    def _build_statusbar(self):
        self.status = QStatusBar(); self.setStatusBar(self.status)
        self.progress = QProgressBar(); self.progress.setMaximumWidth(200)
        self.progress.setVisible(False)
        self.status.addPermanentWidget(self.progress)

    def _update_status(self):
        mode_map = {"COM": "COM 模式", "Lua CLI": "Lua CLI 模式", "not connected": "未連線"}
        mode_zh = mode_map.get(self.backend.mode, self.backend.mode)
        self.status.showMessage(f"模式 Mode: {mode_zh}  |  {APP_NAME} v{APP_VERSION}")
        self._tr_conn.setText(1, mode_zh)

    def _log(self, msg):
        self.log.append(msg)

    # ---- 材料 Materials ----
    _LAM_NAMES = {0:"無",1:"X/R層",2:"Y/Z層",3:"漆包線",4:"絞線",5:"利茲線",6:"方線"}

    def _load_material_db(self):
        mf = os.path.join(os.path.dirname(__file__), "materials.json")
        if not os.path.isfile(mf):
            return
        with open(mf, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # V2 format: {"categories": {cat_name: {mat_name: {props}}}} 
        if "categories" in raw:
            self.materials = raw["categories"]
        else:
            # V1 flat fallback
            self.materials = {"All": raw}
        # Load OpenMagnetics materials if available
        om_path = os.path.join(os.path.dirname(__file__), "openmagnetics_materials.json")
        if os.path.isfile(om_path):
            with open(om_path, "r", encoding="utf-8") as f:
                om = json.load(f)
            om_cats = om.get("categories", {})
            for cat, mats in om_cats.items():
                if cat in self.materials:
                    self.materials[cat].update(mats)
                else:
                    self.materials[cat] = mats
            self._om_count = sum(len(v) for v in om_cats.values())

    def _mat_count(self):
        return sum(len(mats) for mats in self.materials.values())

    def _flat_materials(self):
        """Flatten categories into {name: props} for quick lookup."""
        flat = {}
        for mats in self.materials.values():
            flat.update(mats)
        return flat

    def _fill_mat_tree(self):
        from PySide6.QtGui import QColor, QFont
        self.mat_tree.clear()
        bold = QFont(); bold.setBold(True)
        for cat_name, mats in self.materials.items():
            # 分類標題 Category header
            hdr = QTreeWidgetItem(self.mat_tree, [f"▸ {cat_name}"] + [""] * 7)
            hdr.setFont(0, bold)
            hdr.setForeground(0, QColor("#2b579a"))
            hdr.setExpanded(True)
            for name, p in mats.items():
                lt = p.get("LamType", 0)
                lt_str = self._LAM_NAMES.get(lt, str(lt))
                item = QTreeWidgetItem(hdr, [
                    name,
                    str(p.get("mu_x", "-")),
                    str(p.get("mu_y", "-")),
                    str(p.get("H_c", 0)),
                    str(p.get("Sigma", "-")),
                    lt_str,
                    str(p.get("Lam_d", 0)),
                    p.get("note", ""),
                ])

    # ---- FEMM 連線 Connection ----
    def start_femm_com(self):
        try:
            self.backend.connect_com()
            self._log("[OK] 已透過 COM 啟動 FEMM  FEMM started via COM.")
            self._update_status()
            # 自動載入範例模型 Auto-load demo model if available
            self._auto_load_demo_fem()
        except ImportError:
            QMessageBox.critical(self, "錯誤 Error",
                "無法匯入 femm 模組。\nCannot import femm.\n\n"
                "請安裝 Please install:\n  pip install pyfemm pywin32\n\n"
                "或改用 Lua CLI 模式 Or use Lua CLI mode.")
        except Exception as e:
            QMessageBox.critical(self, "COM 連線失敗 Connection Failed", str(e))
            self._log(f"[ERR] COM 失敗 failed: {e}")

    def start_femm_lua(self):
        try:
            self.backend.connect_lua()
            self._log("[OK] 已切換至 Lua CLI 模式  Switched to Lua CLI mode.")
            self._update_status()
        except FileNotFoundError as e:
            QMessageBox.critical(self, "找不到 FEMM  FEMM Not Found", str(e))

    def stop_femm(self):
        self.backend.disconnect()
        self._log("[OK] 已中斷 FEMM 連線  FEMM disconnected.")
        self._update_status()

    # ---- 檔案操作 File Operations ----
    def open_fem(self):
        if not self._need_conn(): return
        p, _ = QFileDialog.getOpenFileName(self, "開啟模型 Open FEM", "", "FEMM 模型 (*.fem);;所有檔案 All (*)")
        if not p: return
        try:
            self.backend.load_fem(p)
            self._tr_fem.setText(1, os.path.basename(p))
            self._log(f"[OK] 已載入 Loaded: {p}")
        except Exception as e:
            QMessageBox.critical(self, "載入失敗 Load Failed", str(e))

    def open_ans(self):
        if not self._need_conn(): return
        p, _ = QFileDialog.getOpenFileName(self, "載入解答 Load Solution", "", "FEMM 解答 (*.ans);;所有檔案 All (*)")
        if not p: return
        try:
            self.backend.load_solution(p)
            self._log(f"[OK] 解答已載入 Solution loaded: {p}")
        except Exception as e:
            QMessageBox.critical(self, "載入失敗 Load Failed", str(e))

    def save_project(self):
        proj = {"fem": self.backend._current_fem, "mode": self.backend.mode}
        p, _ = QFileDialog.getSaveFileName(self, "儲存專案 Save Project", "project.json", "JSON (*.json)")
        if not p: return
        with open(p, "w", encoding="utf-8") as f:
            json.dump(proj, f, ensure_ascii=False, indent=2)
        self._log(f"[OK] 專案已儲存 Project saved: {p}")

    def load_project(self):
        p, _ = QFileDialog.getOpenFileName(self, "載入專案 Load Project", "", "JSON (*.json);;所有檔案 All (*)")
        if not p: return
        with open(p, "r", encoding="utf-8") as f:
            proj = json.load(f)
        fem = proj.get("fem")
        if fem and os.path.isfile(fem) and self.backend.connected:
            self.backend.load_fem(fem)
            self._tr_fem.setText(1, os.path.basename(fem))
        self._log(f"[OK] 專案已載入 Project loaded: {p}")

    # ---- 模型操作 Model Operations ----
    def add_circuit(self):
        if not self._need_conn(): return
        dlg = CircuitDialog(self)
        if dlg.exec() != QDialog.Accepted: return
        name = dlg.name_edit.text().strip()
        cur = dlg.current_spin.value()
        ser = 1 if dlg.series_combo.currentIndex() == 0 else 0
        try:
            self.backend.add_circuit(name, cur, ser)
            self._log(f"[OK] 電路已新增 Circuit added: {name}, I={cur} A")
        except Exception as e:
            QMessageBox.critical(self, "錯誤 Error", str(e))

    def add_material_from_lib(self):
        flat = self._flat_materials()
        if not flat:
            QMessageBox.information(self, "材料庫 Materials", "材料庫為空。 Material library is empty.")
            return
        names = list(flat.keys())
        item, ok = QInputDialog.getItem(self, "選擇材料 Select Material", "材料 Material:", names, 0, False)
        if not ok or not item: return
        if self.backend.connected:
            try:
                props = flat[item]
                self.backend.add_material(item, props)
                self._log(f"[OK] 材料已新增 Material added: {item}")
            except Exception as e:
                self._log(f"[WARN] 新增材料失敗 add_material failed: {e}")

    def view_model_materials(self):
        """Read and display materials currently in the .fem model."""
        self.model_mat_tree.clear()
        mats = self.backend.get_model_materials()
        if not mats:
            self._log("[INFO] 無法讀取模型材質（可能尚未載入 .fem）")
            return
        flat = self._flat_materials()
        for i, name in enumerate(mats):
            item = QTreeWidgetItem(self.model_mat_tree, [str(i + 1), name])
            # Highlight if material exists in our library
            if name in flat:
                item.setToolTip(1, flat[name].get("note", ""))
        self._log(f"[OK] 模型包含 {len(mats)} 種材質 Model has {len(mats)} materials")
        # Switch to model materials tab
        for i in range(self.tabs.count()):
            if "模型材質" in self.tabs.tabText(i):
                self.tabs.setCurrentIndex(i)
                break

    def change_model_material(self):
        """Open dialog to change a material in the current model."""
        if not self._need_conn(): return
        mats = self.backend.get_model_materials()
        if not mats:
            QMessageBox.information(self, "模型材質 Model Materials",
                "找不到模型材質。請先載入 .fem 檔案。\n"
                "No model materials found. Load a .fem file first.")
            return
        old_name, ok = QInputDialog.getItem(
            self, "選擇要更換的材質 Select material to replace",
            "現有材質 Current material:", mats, 0, False)
        if not ok or not old_name: return
        self._do_change_material(old_name)

    def _change_selected_model_material(self):
        """Change the material selected in the model_mat_tree."""
        if not self._need_conn(): return
        sel = self.model_mat_tree.currentItem()
        if not sel:
            QMessageBox.information(self, "提示 Hint",
                "請先在列表中選擇要更換的材質。\nSelect a material from the list first.")
            return
        old_name = sel.text(1)
        self._do_change_material(old_name)

    def _do_change_material(self, old_name):
        flat = self._flat_materials()
        lib_names = list(flat.keys())
        dlg = ChangeMaterialDialog(old_name, lib_names, self)
        if dlg.exec() != QDialog.Accepted:
            return
        new_name = dlg.combo.currentText()
        if new_name == old_name:
            return
        try:
            props = flat.get(new_name)
            self.backend.modify_material(old_name, new_name, props)
            self._log(f"[OK] 材質已更換 Material changed: {old_name} → {new_name}")
            self._log(f"     ⚠ 請在 FEMM 中重新指定 block label 的材質。")
            self._log(f"     In FEMM, re-assign block labels to use the new material.")
            self.view_model_materials()
        except Exception as e:
            QMessageBox.critical(self, "更換失敗 Change Failed", str(e))

    # ---- 變壓器參數提取 Transformer Parameter Extraction ----
    def extract_transformer_params(self):
        if not self._need_conn(): return
        dlg = TransformerParamDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        pri_name = dlg.pri_edit.text().strip()
        sec_name = dlg.sec_edit.text().strip()
        freq = dlg.freq_spin.value()
        self._log(f"[...] 正在提取變壓器參數 Extracting transformer parameters...")
        try:
            p = self.backend.get_transformer_params(pri_name, sec_name, freq)
        except Exception as e:
            QMessageBox.critical(self, "提取失敗 Extraction Failed", str(e))
            self._log(f"[ERR] {e}")
            return

        # Format results
        lines = []
        lines.append("=" * 62)
        lines.append("  高頻變壓器參數 High-Frequency Transformer Parameters")
        lines.append("=" * 62)
        lines.append(f"  頻率 Frequency        : {freq:,.0f} Hz  ({freq/1e3:.1f} kHz)")
        lines.append("")
        lines.append("  ── 電路特性 Circuit Properties ──")
        lines.append(f"  一次側電流 I_pri      : {abs(p['pri_I']):.6f} A")
        lines.append(f"  一次側電壓 V_pri      : {abs(p['pri_V']):.6f} V")
        lines.append(f"  一次側磁通 Φ_pri      : {abs(p['pri_Flux']):.4e} Wb")
        lines.append(f"  二次側電流 I_sec      : {abs(p['sec_I']):.6f} A")
        lines.append(f"  二次側電壓 V_sec      : {abs(p['sec_V']):.6f} V")
        lines.append(f"  二次側磁通 Φ_sec      : {abs(p['sec_Flux']):.4e} Wb")
        lines.append("")
        lines.append("  ── 阻抗 Impedance ──")
        lines.append(f"  |Z_pri|               : {abs(p['Z_pri']):.6f} Ω")
        lines.append(f"  |Z_sec|               : {abs(p['Z_sec']):.6f} Ω")
        lines.append("")
        lines.append("  ── 電感值 Inductances ──")
        Lp = p["L_pri"]
        Ls = p["L_sec"]
        M  = p["M"]
        Lk = p["Lk_pri"]
        Lm = p["Lm"]
        lines.append(f"  一次側電感 Lp         : {abs(Lp)*1e6:.4f} μH")
        lines.append(f"  二次側電感 Ls         : {abs(Ls)*1e6:.4f} μH")
        lines.append(f"  互感 Mutual M         : {M*1e6:.4f} μH")
        lines.append(f"  耦合係數 k            : {p['k']:.6f}")
        lines.append(f"  一次側漏感 Lk(pri)    : {Lk*1e6:.4f} μH")
        lines.append(f"  二次側漏感 Lk(sec)    : {p['Lk_sec']*1e6:.4f} μH")
        lines.append(f"  激磁電感 Lm(pri ref)  : {Lm*1e6:.4f} μH")
        lines.append("")
        lines.append("  ── 損耗 / 電阻 Resistance ──")
        lines.append(f"  一次側等效電阻 R_pri  : {abs(p['R_pri'])*1e3:.4f} mΩ")
        lines.append(f"  二次側等效電阻 R_sec  : {abs(p['R_sec'])*1e3:.4f} mΩ")
        lines.append("")
        lines.append("  ── 匝比 Turns Ratio ──")
        lines.append(f"  N_pri / N_sec (from Φ): {p['turns_ratio']:.4f}")
        lines.append("")
        lines.append("=" * 62)

        report = "\n".join(lines)
        self.xfmr_text.setPlainText(report)
        self.result_text.append(report)
        self._log("[OK] 變壓器參數提取完成 Transformer parameters extracted.")
        # Switch to transformer tab
        for i in range(self.tabs.count()):
            if "變壓器" in self.tabs.tabText(i) and "設計" not in self.tabs.tabText(i):
                self.tabs.setCurrentIndex(i)
                break

    # ---- 變壓器設計 Transformer Design ----
    def _collect_design_params(self):
        """Collect parameters from the design tab inputs."""
        flat = self._flat_materials()
        core_mat = self.td_core_mat.currentText()
        wind_mat = self.td_wind_mat.currentText()
        save_dir = os.path.join(os.path.dirname(__file__), os.pardir, "examples", "magnetics")
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.normpath(os.path.join(save_dir, "designed_transformer.fem"))
        return {
            "core_type": self.td_core_type.currentText(),
            "core_w": self.td_core_w.value(),
            "core_h": self.td_core_h.value(),
            "core_d": self.td_core_d.value(),
            "window_w": self.td_window_w.value(),
            "window_h": self.td_window_h.value(),
            "n_pri": self.td_n_pri.value(),
            "n_sec": self.td_n_sec.value(),
            "wire_d_pri": self.td_wire_d_pri.value(),
            "wire_d_sec": self.td_wire_d_sec.value(),
            "i_pri": self.td_i_pri.value(),
            "i_sec": self.td_i_sec.value(),
            "freq": self.td_freq.value(),
            "insul_gap": self.td_insul.value(),
            "core_mat": core_mat,
            "wind_mat": wind_mat,
            "core_props": flat.get(core_mat),
            "wind_props": flat.get(wind_mat),
            "save_path": save_path,
        }

    def _generate_transformer_model(self):
        if not self._need_conn(): return
        params = self._collect_design_params()
        self._log("[...] 正在產生變壓器模型 Generating transformer model...")
        self.progress.setVisible(True); self.progress.setRange(0, 0)
        QApplication.processEvents()
        try:
            info = self.backend.generate_transformer(params)
            self._tr_fem.setText(1, os.path.basename(params["save_path"]))
            lines = []
            lines.append("=" * 50)
            lines.append("  變壓器模型已產生 Transformer Model Generated")
            lines.append("=" * 50)
            lines.append(f"  鐵芯型式 Core type    : {params['core_type']}")
            lines.append(f"  鐵芯尺寸 Core size    : {info['total_w']:.1f} x {info['total_h']:.1f} mm")
            lines.append(f"  鐵芯截面積 Core Ae    : {info['core_area_mm2']:.2f} mm²")
            lines.append(f"  窗口面積 Window area   : {info['window_area_mm2']:.2f} mm²")
            lines.append(f"  一次側 N_pri          : {params['n_pri']} turns")
            lines.append(f"  二次側 N_sec          : {params['n_sec']} turns")
            lines.append(f"  頻率 Frequency        : {params['freq']:,.0f} Hz")
            lines.append(f"  鐵芯材料 Core         : {params['core_mat']}")
            lines.append(f"  導線材料 Wire         : {params['wind_mat']}")
            lines.append(f"  儲存路徑 Saved        : {params['save_path']}")
            lines.append("=" * 50)
            lines.append("")
            lines.append("  下一步：按 F5 執行分析，F6 提取參數，F7 密度圖")
            lines.append("  Next: F5 Analyze, F6 Params, F7 Density Plot")
            report = "\n".join(lines)
            self.td_output.setPlainText(report)
            self._log(f"[OK] 變壓器模型已產生 Model generated: {params['save_path']}")
            QMessageBox.information(self, "完成 Done",
                f"模型已產生！\nModel generated!\n\n"
                f"儲存於: {params['save_path']}\n\n"
                f"按 F5 執行分析。\nPress F5 to analyze.")
        except Exception as e:
            QMessageBox.critical(self, "產生失敗 Generation Failed", str(e))
            self._log(f"[ERR] {e}")
        finally:
            self.progress.setVisible(False)

    def _generate_and_analyze(self):
        if not self._need_conn(): return
        self._generate_transformer_model()
        # Check if model was generated successfully
        if self.backend._current_fem and os.path.isfile(self.backend._current_fem):
            self.run_analyze()

    # ---- 分析 Analysis ----
    def run_analyze(self):
        if not self._need_conn(): return
        self._log("[...] 正在執行分析 Running analysis...")
        self.progress.setVisible(True); self.progress.setRange(0, 0)
        QApplication.processEvents()

        if self.backend.mode == "COM":
            # COM 必須在主執行緒呼叫，否則跨執行緒錯誤
            # COM must run on main thread to avoid RPC_E_WRONG_THREAD
            try:
                self.backend.analyze()
                self.progress.setVisible(False)
                self._log("[OK] 分析完成 Analysis completed successfully.")
                self.result_text.append("=== 分析完成 Analysis Complete ===")
                self._log("[TIP] 按 F7 顯示密度圖，F6 提取變壓器參數。")
                self._log("      Press F7 for density plot, F6 for transformer params.")
                # 自動切換到密度圖頁籤 Auto-switch to density tab
                for i in range(self.tabs.count()):
                    if "密度圖" in self.tabs.tabText(i):
                        self.tabs.setCurrentIndex(i)
                        break
                QMessageBox.information(self, "完成 Done",
                    "分析完成！\nAnalysis completed!\n\n"
                    "提示：按 F7 顯示密度圖，F6 提取變壓器參數。\n"
                    "Tip: F7 for density plot, F6 for transformer params.")
            except Exception as e:
                self.progress.setVisible(False)
                self._log(f"[ERR] {e}")
                QMessageBox.warning(self, "分析失敗 Analysis Failed", str(e))
        else:
            # Lua CLI 可以在背景執行緒執行
            # Lua CLI can run in background thread
            self._worker = AnalyzeWorker(self.backend)
            self._worker.finished.connect(self._on_analyze_done)
            self._worker.start()

    def _on_analyze_done(self, ok, msg):
        self.progress.setVisible(False)
        if ok:
            self._log(f"[OK] {msg}")
            self.result_text.append("=== 分析完成 Analysis Complete ===")
            QMessageBox.information(self, "完成 Done", msg)
        else:
            self._log(f"[ERR] {msg}")
            QMessageBox.warning(self, "分析失敗 Analysis Failed", msg)

    # ---- 後處理 Post-processing ----
    def show_density(self):
        if not self._need_conn(): return
        try:
            self.backend.show_density_plot()
            self._log("[OK] 已在 FEMM 中顯示密度圖  Density plot shown in FEMM.")
        except Exception as e:
            QMessageBox.critical(self, "失敗 Failed", str(e))

    def _sample_and_show_inline(self):
        """取樣並在 APP 內顯示密度圖  Sample and display density inline."""
        if not self._need_conn(): return
        dlg = SampleDialog(self)
        if dlg.exec() != QDialog.Accepted: return
        self._do_density_sample(dlg, save_path=None)

    def sample_and_export(self):
        if not self._need_conn(): return
        dlg = SampleDialog(self)
        if dlg.exec() != QDialog.Accepted: return
        sp, _ = QFileDialog.getSaveFileName(
            self, "儲存 PNG  Save PNG", "field_plot.png", "PNG (*.png)")
        if not sp: return
        self._do_density_sample(dlg, save_path=sp)

    def _do_density_sample(self, dlg, save_path=None):
        """Core density sampling: display inline in APP + optionally save to file."""
        self._log("[...] 正在取樣磁場 Sampling field...")
        self.progress.setVisible(True); self.progress.setRange(0, 0)
        QApplication.processEvents()
        try:
            import io
            import numpy as np
            import matplotlib; matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from matplotlib import font_manager as fm

            # ---- 設定中文字體 Configure Chinese font ----
            for fname in ["Microsoft YaHei", "SimHei", "DFKai-SB", "MingLiU"]:
                if any(fname.lower() in f.name.lower() for f in fm.fontManager.ttflist):
                    plt.rcParams["font.sans-serif"] = [fname, "DejaVu Sans"]
                    break
            plt.rcParams["axes.unicode_minus"] = False

            xs, ys, B = self.backend.sample_b_field(
                dlg.xmin.value(), dlg.xmax.value(),
                dlg.ymin.value(), dlg.ymax.value(),
                dlg.nx.value(), dlg.ny.value())
            X, Y = np.meshgrid(xs, ys)

            fig, ax = plt.subplots(figsize=(8, 6))
            cf = ax.contourf(X, Y, B, levels=60, cmap="jet")
            fig.colorbar(cf, ax=ax, label="|B| (T)")

            # ---- 繪製模型幾何輪廓 Draw geometry outlines ----
            try:
                points, segments = self.backend.get_geometry_segments()
                if points and segments:
                    for s0, s1 in segments:
                        if s0 < len(points) and s1 < len(points):
                            x0, y0 = points[s0]
                            x1, y1 = points[s1]
                            ax.plot([x0, x1], [y0, y1], color="white",
                                    linewidth=0.8, alpha=0.85)
            except Exception:
                pass

            ax.set_xlabel("x (mm)"); ax.set_ylabel("y (mm)")
            ax.set_title("磁通密度分佈 Magnetic Flux Density |B|")
            ax.set_aspect("equal")
            fig.tight_layout()

            # ---- 匯出檔案 Save to file (optional) ----
            if save_path:
                fig.savefig(save_path, dpi=150)
                self._log(f"[OK] 磁場圖已儲存 Field plot saved: {save_path}")

            # ---- 在 APP 內顯示 Render inline in the density plot tab ----
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150)
            plt.close(fig)
            buf.seek(0)
            qimg = QImage()
            qimg.loadFromData(buf.getvalue())
            self._density_pixmap_full = QPixmap.fromImage(qimg)
            self.density_view.set_pixmap(self._density_pixmap_full)

            # ---- 分析統計報告 Analysis statistics report ----
            bmax = float(B.max())
            bmin = float(B.min())
            bmean = float(B.mean())
            bmean_nz = float(B[B > 0].mean()) if (B > 0).any() else 0.0
            bstd = float(B.std())
            nx, ny = dlg.nx.value(), dlg.ny.value()

            lines = []
            lines.append("=" * 56)
            lines.append("  磁通密度分析報告 Magnetic Flux Density Report")
            lines.append("=" * 56)
            lines.append(f"  取樣範圍 Sampling area:")
            lines.append(f"    X: {dlg.xmin.value():.2f} ~ {dlg.xmax.value():.2f} mm")
            lines.append(f"    Y: {dlg.ymin.value():.2f} ~ {dlg.ymax.value():.2f} mm")
            lines.append(f"  取樣解析度 Resolution : {nx} x {ny} = {nx*ny} 點 points")
            lines.append("")
            lines.append("  ── 磁通密度統計 |B| Statistics ──")
            lines.append(f"  B_max                 : {bmax:.6f} T")
            lines.append(f"  B_min                 : {bmin:.6f} T")
            lines.append(f"  B_mean                : {bmean:.6f} T")
            lines.append(f"  B_mean (非零 nonzero) : {bmean_nz:.6f} T")
            lines.append(f"  B_std  (標準差 std)   : {bstd:.6f} T")
            lines.append("")
            if save_path:
                lines.append(f"  已儲存 Saved: {save_path}")
            lines.append("=" * 56)
            report = "\n".join(lines)

            self.density_report.setPlainText(report)
            self.result_text.append(report)
            self._log(f"[OK] 密度圖已顯示 Density plot displayed. B_max={bmax:.4f} T")

            # 切換到密度圖頁籤 Switch to density plot tab
            for i in range(self.tabs.count()):
                if "密度圖" in self.tabs.tabText(i):
                    self.tabs.setCurrentIndex(i)
                    break

        except Exception as e:
            QMessageBox.critical(self, "取樣失敗 Sampling Failed", str(e))
            self._log(f"[ERR] {e}")
        finally:
            self.progress.setVisible(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)

    # ---- 說明 Help ----
    def show_about(self):
        QMessageBox.about(self, f"關於 About {APP_NAME}",
            f"<h2>{APP_NAME}</h2><p>版本 Version {APP_VERSION}</p>"
            "<p>專業 FEMM 前/後處理工具<br>Professional FEMM pre/post-processing tool.</p>"
            "<p>支援 COM (ActiveX) 與 Lua CLI 雙模式<br>Supports COM and Lua CLI dual mode.</p>"
            "<hr><p>2026 - 商業授權 Commercial License</p>")

    # ---- 輔助 Helpers ----
    def _need_conn(self):
        if self.backend.connected:
            return True
        QMessageBox.warning(self, "尚未連線 Not Connected",
            "請先透過 FEMM 選單啟動 FEMM\n"
            "Please start FEMM first via the FEMM menu\n"
            "(點 COM 連線 或 Lua 模式 / COM Connect or Lua Mode)")
        return False

    # ---- 範例載入 Demo Example ----
    def _get_demo_fem_path(self):
        return os.path.normpath(os.path.join(
            os.path.dirname(__file__), os.pardir,
            "examples", "magnetics", "hf_transformer", "hf_transformer_v2.fem"))

    def _auto_load_demo_fem(self):
        """COM 連線後自動載入範例 .fem  Auto-load demo .fem after COM connect."""
        demo_fem = self._get_demo_fem_path()
        if os.path.isfile(demo_fem) and self.backend.connected:
            try:
                self.backend.load_fem(demo_fem)
                self._tr_fem.setText(1, os.path.basename(demo_fem))
                self._log(f"[OK] 已自動載入範例模型 Auto-loaded demo: {demo_fem}")
                self._log("[TIP] 現在可以直接點「分析 Analyze (F5)」執行求解。")
                self._log("      You can now click 'Analyze (F5)' to run the solver.")
            except Exception as e:
                self._log(f"[WARN] 自動載入失敗 Auto-load failed: {e}")

    def _load_demo_example(self):
        demo_fem = self._get_demo_fem_path()
        demo_ans = demo_fem.replace(".fem", ".ans")
        if os.path.isfile(demo_fem):
            self.backend._current_fem = demo_fem
            self._tr_fem.setText(1, os.path.basename(demo_fem))
            QTreeWidgetItem(self.tree, ["範例 Example", "高頻變壓器 HF Transformer"])
            QTreeWidgetItem(self.tree, ["範例 .fem 路徑 Path", demo_fem])
            if os.path.isfile(demo_ans):
                QTreeWidgetItem(self.tree, ["範例 .ans 路徑 Path", demo_ans])
            self._log(f"[INFO] 已載入高頻變壓器範例  HF Transformer demo loaded.")
            self._log(f"       .fem: {demo_fem}")
            if os.path.isfile(demo_ans):
                self._log(f"       .ans: {demo_ans}")
            self._log("[TIP] 請先點 'COM 連線' 或 'Lua 模式' 建立連線，再執行分析。")
            self._log("      Click 'COM Connect' or 'Lua Mode' first, then run analysis.")
        else:
            self._log(f"[INFO] 範例檔案未找到 Demo not found: {demo_fem}")

    def _load_demo_and_notify(self):
        self._load_demo_example()
        QMessageBox.information(self, "範例已載入 Demo Loaded",
            "高頻變壓器範例已載入專案瀏覽器。\n"
            "HF Transformer example loaded.\n\n"
            "請先連線 FEMM 再開啟模型。\n"
            "Connect FEMM first, then open the model.")

    def closeEvent(self, event):
        if self.backend.connected:
            self.backend.disconnect()
        event.accept()
