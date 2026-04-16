"""Write bilingual (Chinese+English) gui.py with HF transformer demo auto-load."""
import os

GUI_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pyfemm_gui", "gui.py")

CONTENT = '''\
"""
PyFEMM Studio - Professional FEMM pre/post-processing GUI (PySide6).
\u529f\u80fd Features: COM / Lua CLI \u96d9\u6a21\u5f0f dual-mode, \u6750\u6599\u5eab material library,
\u96fb\u8def circuits, \u6c42\u89e3\u5668 solver, \u78c1\u5834\u53d6\u6a23 field sampling, \u5c08\u6848 I/O.
"""
import json, os, sys

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMainWindow, QMenu, QMenuBar, QMessageBox, QProgressBar,
    QSpinBox, QSplitter, QStatusBar, QTabWidget, QTextEdit, QToolBar,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from pyfemm_gui.femm_backend import FemmBackend

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
            self.finished.emit(True, "\u5206\u6790\u5b8c\u6210 Analysis completed successfully.")
        except Exception as e:
            self.finished.emit(False, str(e))


class SampleDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("\u53d6\u6a23\u8a2d\u5b9a Sampling Settings")
        form = QFormLayout()
        self.xmin = QDoubleSpinBox(); self.xmin.setRange(-10, 10); self.xmin.setValue(-0.025); self.xmin.setDecimals(4)
        self.xmax = QDoubleSpinBox(); self.xmax.setRange(-10, 10); self.xmax.setValue(0.025); self.xmax.setDecimals(4)
        self.ymin = QDoubleSpinBox(); self.ymin.setRange(-10, 10); self.ymin.setValue(-0.025); self.ymin.setDecimals(4)
        self.ymax = QDoubleSpinBox(); self.ymax.setRange(-10, 10); self.ymax.setValue(0.025); self.ymax.setDecimals(4)
        self.nx = QSpinBox(); self.nx.setRange(4, 2000); self.nx.setValue(120)
        self.ny = QSpinBox(); self.ny.setRange(4, 2000); self.ny.setValue(120)
        form.addRow("X \u6700\u5c0f\u503c X min (m):", self.xmin)
        form.addRow("X \u6700\u5927\u503c X max (m):", self.xmax)
        form.addRow("Y \u6700\u5c0f\u503c Y min (m):", self.ymin)
        form.addRow("Y \u6700\u5927\u503c Y max (m):", self.ymax)
        form.addRow("X \u53d6\u6a23\u9ede\u6578 X points:", self.nx)
        form.addRow("Y \u53d6\u6a23\u9ede\u6578 Y points:", self.ny)
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
        self.setWindowTitle("\u65b0\u589e\u96fb\u8def Add Circuit")
        form = QFormLayout()
        self.name_edit = QLineEdit("Primary")
        self.current_spin = QDoubleSpinBox()
        self.current_spin.setRange(-1e9, 1e9)
        self.current_spin.setDecimals(6)
        self.current_spin.setValue(0.5)
        self.series_combo = QComboBox()
        self.series_combo.addItems(["\u4e32\u806f Series (1)", "\u4e26\u806f Parallel (0)"])
        form.addRow("\u96fb\u8def\u540d\u7a31 Circuit name:", self.name_edit)
        form.addRow("\u96fb\u6d41 Current (A):", self.current_spin)
        form.addRow("\u9023\u63a5\u65b9\u5f0f Connection:", self.series_combo)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay = QVBoxLayout()
        lay.addLayout(form)
        lay.addWidget(btns)
        self.setLayout(lay)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1024, 680)

        self.backend = FemmBackend()
        self.materials = {}
        self._load_material_db()

        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._update_status()
        self._load_demo_example()

    # ---- \u9078\u55ae Menu ----
    def _build_menu(self):
        bar = self.menuBar()
        # \u6a94\u6848 File
        fm = bar.addMenu("\u6a94\u6848 File(&F)")
        fm.addAction(self._act("\u958b\u555f\u6a21\u578b Open .fem...", self.open_fem, "Ctrl+O"))
        fm.addAction(self._act("\u8f09\u5165\u89e3\u7b54 Load .ans...", self.open_ans))
        fm.addSeparator()
        fm.addAction(self._act("\u5132\u5b58\u5c08\u6848 Save Project...", self.save_project, "Ctrl+S"))
        fm.addAction(self._act("\u8f09\u5165\u5c08\u6848 Load Project...", self.load_project, "Ctrl+Shift+O"))
        fm.addSeparator()
        fm.addAction(self._act("\u8f09\u5165\u7bc4\u4f8b Load Demo Example", self._load_demo_and_notify))
        fm.addSeparator()
        fm.addAction(self._act("\u7d50\u675f Exit", self.close, "Ctrl+Q"))
        # FEMM \u9023\u7dda
        mm = bar.addMenu("FEMM \u9023\u7dda(&M)")
        mm.addAction(self._act("\u555f\u52d5 FEMM (COM) Start FEMM", self.start_femm_com))
        mm.addAction(self._act("\u4f7f\u7528 Lua CLI \u6a21\u5f0f Use Lua CLI", self.start_femm_lua))
        mm.addSeparator()
        mm.addAction(self._act("\u95dc\u9589 FEMM Close FEMM", self.stop_femm))
        # \u6a21\u578b Model
        dm = bar.addMenu("\u6a21\u578b Model(&D)")
        dm.addAction(self._act("\u65b0\u589e\u96fb\u8def Add Circuit...", self.add_circuit))
        dm.addAction(self._act("\u5f9e\u6750\u6599\u5eab\u65b0\u589e Add Material...", self.add_material_from_lib))
        dm.addAction(self._act("\u57f7\u884c\u5206\u6790 Run Analysis", self.run_analyze, "F5"))
        # \u5f8c\u8655\u7406 Post
        pm = bar.addMenu("\u5f8c\u8655\u7406 Post(&P)")
        pm.addAction(self._act("\u78c1\u901a\u5bc6\u5ea6\u5716 Density Plot", self.show_density))
        pm.addAction(self._act("\u53d6\u6a23\u532f\u51fa PNG Sample & Export", self.sample_and_export))
        # \u8aaa\u660e Help
        hm = bar.addMenu("\u8aaa\u660e Help(&H)")
        hm.addAction(self._act("\u95dc\u65bc About", self.show_about))

    def _act(self, text, slot, shortcut=None):
        a = QAction(text, self)
        a.triggered.connect(slot)
        if shortcut:
            a.setShortcut(shortcut)
        return a

    # ---- \u5de5\u5177\u5217 Toolbar ----
    def _build_toolbar(self):
        tb = QToolBar("Main"); tb.setMovable(False); self.addToolBar(tb)
        tb.addAction(self._act("COM \u9023\u7dda Connect", self.start_femm_com))
        tb.addAction(self._act("Lua \u6a21\u5f0f Mode", self.start_femm_lua))
        tb.addSeparator()
        tb.addAction(self._act("\u958b\u555f .fem Open", self.open_fem))
        tb.addAction(self._act("\u8f09\u5165 .ans Load", self.open_ans))
        tb.addSeparator()
        tb.addAction(self._act("\u5206\u6790 Analyze (F5)", self.run_analyze))
        tb.addAction(self._act("\u5bc6\u5ea6\u5716 Density", self.show_density))
        tb.addAction(self._act("\u53d6\u6a23 PNG Sample", self.sample_and_export))

    # ---- \u4e2d\u592e\u9762\u677f Central Panel ----
    def _build_central(self):
        sp = QSplitter(Qt.Horizontal)
        # \u5de6\u5074\uff1a\u5c08\u6848\u700f\u89bd\u5668 Left: Project Browser
        left = QWidget(); ll = QVBoxLayout(); ll.setContentsMargins(4,4,4,4)
        lbl = QLabel("\u5c08\u6848\u700f\u89bd\u5668 Project Browser")
        lbl.setStyleSheet("font-weight:bold; font-size:13px;")
        ll.addWidget(lbl)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["\u9805\u76ee Item", "\u503c Value"])
        self.tree.setColumnWidth(0, 210)
        self._tr_conn = QTreeWidgetItem(self.tree, ["\u9023\u7dda\u72c0\u614b Connection", "\u672a\u9023\u7dda not connected"])
        self._tr_fem  = QTreeWidgetItem(self.tree, ["\u6a21\u578b\u6a94\u6848 FEM File", "(\u7121 none)"])
        self._tr_mat  = QTreeWidgetItem(self.tree, ["\u6750\u6599\u5eab Materials", f"{len(self.materials)} \u9805 items"])
        ll.addWidget(self.tree)
        left.setLayout(ll)
        # \u53f3\u5074\uff1a\u9801\u7c64 Right: Tabs
        self.tabs = QTabWidget()
        # \u65e5\u8a8c Log
        self.log = QTextEdit(); self.log.setReadOnly(True)
        self.tabs.addTab(self.log, "\u65e5\u8a8c Log")
        # \u6750\u6599\u5eab Materials
        mp = QWidget(); ml = QVBoxLayout()
        self.mat_tree = QTreeWidget()
        self.mat_tree.setHeaderLabels(["\u6750\u6599 Material", "mu", "sigma", "rho"])
        self._fill_mat_tree()
        ml.addWidget(self.mat_tree); mp.setLayout(ml)
        self.tabs.addTab(mp, "\u6750\u6599\u5eab Materials")
        # \u7d50\u679c Results
        rp = QWidget(); rl = QVBoxLayout()
        self.result_text = QTextEdit(); self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("\u5206\u6790\u7d50\u679c\u5c07\u5728\u6b64\u986f\u793a Analysis results will appear here...")
        rl.addWidget(self.result_text); rp.setLayout(rl)
        self.tabs.addTab(rp, "\u7d50\u679c Results")
        sp.addWidget(left); sp.addWidget(self.tabs)
        sp.setStretchFactor(0, 1); sp.setStretchFactor(1, 3)
        self.setCentralWidget(sp)

    def _build_statusbar(self):
        self.status = QStatusBar(); self.setStatusBar(self.status)
        self.progress = QProgressBar(); self.progress.setMaximumWidth(200)
        self.progress.setVisible(False)
        self.status.addPermanentWidget(self.progress)

    def _update_status(self):
        mode_map = {"COM": "COM \u6a21\u5f0f", "Lua CLI": "Lua CLI \u6a21\u5f0f", "not connected": "\u672a\u9023\u7dda"}
        mode_zh = mode_map.get(self.backend.mode, self.backend.mode)
        self.status.showMessage(f"\u6a21\u5f0f Mode: {mode_zh}  |  {APP_NAME} v{APP_VERSION}")
        self._tr_conn.setText(1, mode_zh)

    def _log(self, msg):
        self.log.append(msg)

    # ---- \u6750\u6599 Materials ----
    def _load_material_db(self):
        mf = os.path.join(os.path.dirname(__file__), "materials.json")
        if os.path.isfile(mf):
            with open(mf, "r", encoding="utf-8") as f:
                self.materials = json.load(f)

    def _fill_mat_tree(self):
        self.mat_tree.clear()
        for name, p in self.materials.items():
            mu = p.get("mu", p.get("mu_x", "-"))
            QTreeWidgetItem(self.mat_tree, [name, str(mu), str(p.get("sigma","-")), str(p.get("rho","-"))])

    # ---- FEMM \u9023\u7dda Connection ----
    def start_femm_com(self):
        try:
            self.backend.connect_com()
            self._log("[OK] \u5df2\u900f\u904e COM \u555f\u52d5 FEMM  FEMM started via COM.")
            self._update_status()
        except ImportError:
            QMessageBox.critical(self, "\u932f\u8aa4 Error",
                "\u7121\u6cd5\u532f\u5165 pyfemm \u6a21\u7d44\u3002\\nCannot import pyfemm.\\n\\n"
                "\u8acb\u5b89\u88dd Please install:\\n  pip install pyfemm pywin32\\n\\n"
                "\u6216\u6539\u7528 Lua CLI \u6a21\u5f0f Or use Lua CLI mode.")
        except Exception as e:
            QMessageBox.critical(self, "COM \u9023\u7dda\u5931\u6557 Connection Failed", str(e))
            self._log(f"[ERR] COM \u5931\u6557 failed: {e}")

    def start_femm_lua(self):
        try:
            self.backend.connect_lua()
            self._log("[OK] \u5df2\u5207\u63db\u81f3 Lua CLI \u6a21\u5f0f  Switched to Lua CLI mode.")
            self._update_status()
        except FileNotFoundError as e:
            QMessageBox.critical(self, "\u627e\u4e0d\u5230 FEMM  FEMM Not Found", str(e))

    def stop_femm(self):
        self.backend.disconnect()
        self._log("[OK] \u5df2\u4e2d\u65b7 FEMM \u9023\u7dda  FEMM disconnected.")
        self._update_status()

    # ---- \u6a94\u6848\u64cd\u4f5c File Operations ----
    def open_fem(self):
        if not self._need_conn(): return
        p, _ = QFileDialog.getOpenFileName(self, "\u958b\u555f\u6a21\u578b Open FEM", "", "FEMM \u6a21\u578b (*.fem);;\u6240\u6709\u6a94\u6848 All (*)")
        if not p: return
        try:
            self.backend.load_fem(p)
            self._tr_fem.setText(1, os.path.basename(p))
            self._log(f"[OK] \u5df2\u8f09\u5165 Loaded: {p}")
        except Exception as e:
            QMessageBox.critical(self, "\u8f09\u5165\u5931\u6557 Load Failed", str(e))

    def open_ans(self):
        if not self._need_conn(): return
        p, _ = QFileDialog.getOpenFileName(self, "\u8f09\u5165\u89e3\u7b54 Load Solution", "", "FEMM \u89e3\u7b54 (*.ans);;\u6240\u6709\u6a94\u6848 All (*)")
        if not p: return
        try:
            self.backend.load_solution(p)
            self._log(f"[OK] \u89e3\u7b54\u5df2\u8f09\u5165 Solution loaded: {p}")
        except Exception as e:
            QMessageBox.critical(self, "\u8f09\u5165\u5931\u6557 Load Failed", str(e))

    def save_project(self):
        proj = {"fem": self.backend._current_fem, "mode": self.backend.mode}
        p, _ = QFileDialog.getSaveFileName(self, "\u5132\u5b58\u5c08\u6848 Save Project", "project.json", "JSON (*.json)")
        if not p: return
        with open(p, "w", encoding="utf-8") as f:
            json.dump(proj, f, ensure_ascii=False, indent=2)
        self._log(f"[OK] \u5c08\u6848\u5df2\u5132\u5b58 Project saved: {p}")

    def load_project(self):
        p, _ = QFileDialog.getOpenFileName(self, "\u8f09\u5165\u5c08\u6848 Load Project", "", "JSON (*.json);;\u6240\u6709\u6a94\u6848 All (*)")
        if not p: return
        with open(p, "r", encoding="utf-8") as f:
            proj = json.load(f)
        fem = proj.get("fem")
        if fem and os.path.isfile(fem) and self.backend.connected:
            self.backend.load_fem(fem)
            self._tr_fem.setText(1, os.path.basename(fem))
        self._log(f"[OK] \u5c08\u6848\u5df2\u8f09\u5165 Project loaded: {p}")

    # ---- \u6a21\u578b\u64cd\u4f5c Model Operations ----
    def add_circuit(self):
        if not self._need_conn(): return
        dlg = CircuitDialog(self)
        if dlg.exec() != QDialog.Accepted: return
        name = dlg.name_edit.text().strip()
        cur = dlg.current_spin.value()
        ser = 1 if dlg.series_combo.currentIndex() == 0 else 0
        try:
            self.backend.add_circuit(name, cur, ser)
            self._log(f"[OK] \u96fb\u8def\u5df2\u65b0\u589e Circuit added: {name}, I={cur} A")
        except Exception as e:
            QMessageBox.critical(self, "\u932f\u8aa4 Error", str(e))

    def add_material_from_lib(self):
        if not self.materials:
            QMessageBox.information(self, "\u6750\u6599\u5eab Materials", "\u6750\u6599\u5eab\u70ba\u7a7a\u3002 Material library is empty.")
            return
        names = list(self.materials.keys())
        item, ok = QInputDialog.getItem(self, "\u9078\u64c7\u6750\u6599 Select Material", "\u6750\u6599 Material:", names, 0, False)
        if not ok or not item: return
        if self.backend.connected:
            try:
                self.backend.add_material(item)
                self._log(f"[OK] \u6750\u6599\u5df2\u65b0\u589e Material added: {item}")
            except Exception as e:
                self._log(f"[WARN] \u65b0\u589e\u6750\u6599\u5931\u6557 add_material failed: {e}")

    # ---- \u5206\u6790 Analysis ----
    def run_analyze(self):
        if not self._need_conn(): return
        self._log("[...] \u6b63\u5728\u57f7\u884c\u5206\u6790 Running analysis...")
        self.progress.setVisible(True); self.progress.setRange(0, 0)
        self._worker = AnalyzeWorker(self.backend)
        self._worker.finished.connect(self._on_analyze_done)
        self._worker.start()

    def _on_analyze_done(self, ok, msg):
        self.progress.setVisible(False)
        if ok:
            self._log(f"[OK] {msg}")
            self.result_text.append("=== \u5206\u6790\u5b8c\u6210 Analysis Complete ===")
            QMessageBox.information(self, "\u5b8c\u6210 Done", msg)
        else:
            self._log(f"[ERR] {msg}")
            QMessageBox.warning(self, "\u5206\u6790\u5931\u6557 Analysis Failed", msg)

    # ---- \u5f8c\u8655\u7406 Post-processing ----
    def show_density(self):
        if not self._need_conn(): return
        try:
            self.backend.show_density_plot()
            self._log("[OK] \u5df2\u5728 FEMM \u4e2d\u986f\u793a\u5bc6\u5ea6\u5716  Density plot shown in FEMM.")
        except Exception as e:
            QMessageBox.critical(self, "\u5931\u6557 Failed", str(e))

    def sample_and_export(self):
        if not self._need_conn(): return
        dlg = SampleDialog(self)
        if dlg.exec() != QDialog.Accepted: return
        sp, _ = QFileDialog.getSaveFileName(self, "\u5132\u5b58 PNG  Save PNG", "field_plot.png", "PNG (*.png)")
        if not sp: return
        self._log("[...] \u6b63\u5728\u53d6\u6a23\u78c1\u5834 Sampling field...")
        self.progress.setVisible(True); self.progress.setRange(0, 0)
        QApplication.processEvents()
        try:
            import numpy as np
            import matplotlib; matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            xs, ys, B = self.backend.sample_b_field(
                dlg.xmin.value(), dlg.xmax.value(),
                dlg.ymin.value(), dlg.ymax.value(),
                dlg.nx.value(), dlg.ny.value())
            X, Y = np.meshgrid(xs, ys)
            fig, ax = plt.subplots(figsize=(7, 6))
            cf = ax.contourf(X*1000, Y*1000, B, levels=60, cmap="viridis")
            fig.colorbar(cf, ax=ax, label="|B| (T)")
            ax.set_xlabel("x (mm)"); ax.set_ylabel("y (mm)")
            ax.set_title("\u78c1\u901a\u5bc6\u5ea6 Magnetic Flux Density |B|")
            fig.tight_layout(); fig.savefig(sp, dpi=150); plt.close(fig)
            bmax = float(B.max())
            bmean = float(B[B > 0].mean()) if (B > 0).any() else 0.0
            r = (f"\u53d6\u6a23\u5b8c\u6210 Sampling done: {dlg.nx.value()}x{dlg.ny.value()} \u9ede points\\n"
                 f"B_max = {bmax:.4f} T\\nB_mean (\u975e\u96f6 nonzero) = {bmean:.4f} T\\n"
                 f"\u5df2\u5132\u5b58 Saved: {sp}")
            self.result_text.append(r)
            self._log(f"[OK] \u78c1\u5834\u5716\u5df2\u5132\u5b58 Field plot saved: {sp}")
            QMessageBox.information(self, "\u5b8c\u6210 Done", r)
        except Exception as e:
            QMessageBox.critical(self, "\u53d6\u6a23\u5931\u6557 Sampling Failed", str(e))
            self._log(f"[ERR] {e}")
        finally:
            self.progress.setVisible(False)

    # ---- \u8aaa\u660e Help ----
    def show_about(self):
        QMessageBox.about(self, f"\u95dc\u65bc About {APP_NAME}",
            f"<h2>{APP_NAME}</h2><p>\u7248\u672c Version {APP_VERSION}</p>"
            "<p>\u5c08\u696d FEMM \u524d/\u5f8c\u8655\u7406\u5de5\u5177<br>Professional FEMM pre/post-processing tool.</p>"
            "<p>\u652f\u63f4 COM (ActiveX) \u8207 Lua CLI \u96d9\u6a21\u5f0f<br>Supports COM and Lua CLI dual mode.</p>"
            "<hr><p>2026 - \u5546\u696d\u6388\u6b0a Commercial License</p>")

    # ---- \u8f14\u52a9 Helpers ----
    def _need_conn(self):
        if self.backend.connected:
            return True
        QMessageBox.warning(self, "\u5c1a\u672a\u9023\u7dda Not Connected",
            "\u8acb\u5148\u900f\u904e FEMM \u9078\u55ae\u555f\u52d5 FEMM\\n"
            "Please start FEMM first via the FEMM menu\\n"
            "(\u9ede COM \u9023\u7dda \u6216 Lua \u6a21\u5f0f / COM Connect or Lua Mode)")
        return False

    # ---- \u7bc4\u4f8b\u8f09\u5165 Demo Example ----
    def _load_demo_example(self):
        demo_fem = os.path.normpath(os.path.join(
            os.path.dirname(__file__), os.pardir,
            "examples", "magnetics", "hf_transformer", "hf_transformer_v2.fem"))
        demo_ans = demo_fem.replace(".fem", ".ans")
        if os.path.isfile(demo_fem):
            self.backend._current_fem = demo_fem
            self._tr_fem.setText(1, os.path.basename(demo_fem))
            QTreeWidgetItem(self.tree, ["\u7bc4\u4f8b Example", "\u9ad8\u983b\u8b8a\u58d3\u5668 HF Transformer"])
            QTreeWidgetItem(self.tree, ["\u7bc4\u4f8b .fem \u8def\u5f91 Path", demo_fem])
            if os.path.isfile(demo_ans):
                QTreeWidgetItem(self.tree, ["\u7bc4\u4f8b .ans \u8def\u5f91 Path", demo_ans])
            self._log(f"[INFO] \u5df2\u8f09\u5165\u9ad8\u983b\u8b8a\u58d3\u5668\u7bc4\u4f8b  HF Transformer demo loaded.")
            self._log(f"       .fem: {demo_fem}")
            if os.path.isfile(demo_ans):
                self._log(f"       .ans: {demo_ans}")
            self._log("[TIP] \u8acb\u5148\u9ede 'COM \u9023\u7dda' \u6216 'Lua \u6a21\u5f0f' \u5efa\u7acb\u9023\u7dda\uff0c\u518d\u57f7\u884c\u5206\u6790\u3002")
            self._log("      Click 'COM Connect' or 'Lua Mode' first, then run analysis.")
        else:
            self._log(f"[INFO] \u7bc4\u4f8b\u6a94\u6848\u672a\u627e\u5230 Demo not found: {demo_fem}")

    def _load_demo_and_notify(self):
        self._load_demo_example()
        QMessageBox.information(self, "\u7bc4\u4f8b\u5df2\u8f09\u5165 Demo Loaded",
            "\u9ad8\u983b\u8b8a\u58d3\u5668\u7bc4\u4f8b\u5df2\u8f09\u5165\u5c08\u6848\u700f\u89bd\u5668\u3002\\n"
            "HF Transformer example loaded.\\n\\n"
            "\u8acb\u5148\u9023\u7dda FEMM \u518d\u958b\u555f\u6a21\u578b\u3002\\n"
            "Connect FEMM first, then open the model.")

    def closeEvent(self, event):
        if self.backend.connected:
            self.backend.disconnect()
        event.accept()
'''

with open(GUI_PATH, "w", encoding="utf-8") as f:
    f.write(CONTENT)
print(f"[OK] Bilingual gui.py written to: {GUI_PATH}")
print(f"     Size: {os.path.getsize(GUI_PATH)} bytes")
