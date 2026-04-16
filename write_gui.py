"""Build script: writes the professional bilingual GUI files."""
import os

BASE = os.path.dirname(os.path.abspath(__file__))
GUI_DIR = os.path.join(BASE, "pyfemm_gui")

files = {}

# ── __init__.py ──
files["__init__.py"] = '# pyfemm_gui package\n'

# ── femm_backend.py ──
files["femm_backend.py"] = r'''"""
FEMM backend - COM (pyfemm) + Lua CLI fallback.
pyfemm is imported lazily only when connect_com() is called.
"""
import os, subprocess

FEMM_EXE = r"C:\femm42\bin\femm.exe"

class FemmBackend:
    def __init__(self):
        self._pyfemm = None
        self._connected = False
        self._mode = None
        self._current_fem = None

    @property
    def connected(self):
        return self._connected

    @property
    def mode(self):
        return self._mode or "not connected"

    def connect_com(self):
        import pyfemm
        pyfemm.openfemm()
        self._pyfemm = pyfemm
        self._connected = True
        self._mode = "COM"

    def connect_lua(self):
        if not os.path.isfile(FEMM_EXE):
            raise FileNotFoundError(f"Cannot find FEMM: {FEMM_EXE}")
        self._mode = "Lua CLI"
        self._connected = True

    def disconnect(self):
        if self._pyfemm:
            try:
                self._pyfemm.closefemm()
            except Exception:
                pass
        self._pyfemm = None
        self._connected = False
        self._mode = None

    def load_fem(self, path):
        self._current_fem = path
        if self._mode == "COM":
            self._pyfemm.opendocument(path)

    def save_fem(self, path):
        if self._mode == "COM":
            self._pyfemm.mi_saveas(path)
        self._current_fem = path

    def add_material(self, name):
        if self._mode == "COM":
            self._pyfemm.mi_addmaterial(name)

    def add_circuit(self, name, current, series=1):
        if self._mode == "COM":
            self._pyfemm.mi_addcircprop(name, current, series)

    def analyze(self):
        if self._mode == "COM":
            self._pyfemm.mi_analyze()
            self._pyfemm.mi_loadsolution()
        elif self._mode == "Lua CLI":
            self._run_lua_analyze()

    def _run_lua_analyze(self):
        if not self._current_fem:
            raise RuntimeError("No .fem loaded")
        fp = self._current_fem.replace("\\", "/")
        lua = f'open("{fp}")\nmi_analyze()\nmi_loadsolution()\n'
        lua_path = self._current_fem.replace(".fem", "_auto.lua")
        with open(lua_path, "w", encoding="utf-8") as f:
            f.write(lua)
        r = subprocess.run([FEMM_EXE, "-lua-script", lua_path],
                           capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            raise RuntimeError(f"Lua solve failed:\n{r.stderr}")

    def load_solution(self, path):
        if self._mode == "COM":
            self._pyfemm.opendocument(path)

    def show_density_plot(self):
        if self._mode == "COM":
            self._pyfemm.mo_showdensityplot(1, 0, 0.0, 1.0, "bmag")

    def get_point_values(self, x, y):
        if self._mode == "COM":
            return self._pyfemm.mo_getpointvalues(x, y)
        return None

    def get_circuit_properties(self, name):
        if self._mode == "COM":
            return self._pyfemm.mo_getcircuitproperties(name)
        return None

    def sample_b_field(self, xmin, xmax, ymin, ymax, nx, ny):
        import numpy as np
        xs = np.linspace(xmin, xmax, nx)
        ys = np.linspace(ymin, ymax, ny)
        B = np.zeros((ny, nx), dtype=float)
        for j, y_val in enumerate(ys):
            for i, x_val in enumerate(xs):
                vals = self.get_point_values(float(x_val), float(y_val))
                if vals and isinstance(vals, (list, tuple)) and len(vals) >= 3:
                    B[j, i] = (vals[1]**2 + vals[2]**2)**0.5
        return xs, ys, B
'''

# ── gui.py ──
files["gui.py"] = r'''"""
PyFEMM Studio - Professional FEMM pre/post-processing GUI (PySide6).
Features: COM / Lua CLI dual-mode, material library, circuits, solver,
          field sampling, project I/O, professional layout.
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
            self.finished.emit(True, "Analysis completed successfully.")
        except Exception as e:
            self.finished.emit(False, str(e))


class SampleDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sampling Settings")
        form = QFormLayout()
        self.xmin = QDoubleSpinBox(); self.xmin.setRange(-10, 10); self.xmin.setValue(-0.025); self.xmin.setDecimals(4)
        self.xmax = QDoubleSpinBox(); self.xmax.setRange(-10, 10); self.xmax.setValue(0.025); self.xmax.setDecimals(4)
        self.ymin = QDoubleSpinBox(); self.ymin.setRange(-10, 10); self.ymin.setValue(-0.025); self.ymin.setDecimals(4)
        self.ymax = QDoubleSpinBox(); self.ymax.setRange(-10, 10); self.ymax.setValue(0.025); self.ymax.setDecimals(4)
        self.nx = QSpinBox(); self.nx.setRange(4, 2000); self.nx.setValue(120)
        self.ny = QSpinBox(); self.ny.setRange(4, 2000); self.ny.setValue(120)
        form.addRow("X min (m):", self.xmin)
        form.addRow("X max (m):", self.xmax)
        form.addRow("Y min (m):", self.ymin)
        form.addRow("Y max (m):", self.ymax)
        form.addRow("X points:", self.nx)
        form.addRow("Y points:", self.ny)
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
        self.setWindowTitle("Add Circuit")
        form = QFormLayout()
        self.name_edit = QLineEdit("Primary")
        self.current_spin = QDoubleSpinBox()
        self.current_spin.setRange(-1e9, 1e9)
        self.current_spin.setDecimals(6)
        self.current_spin.setValue(0.5)
        self.series_combo = QComboBox()
        self.series_combo.addItems(["Series (1)", "Parallel (0)"])
        form.addRow("Circuit name:", self.name_edit)
        form.addRow("Current (A):", self.current_spin)
        form.addRow("Connection:", self.series_combo)
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
        self.resize(960, 640)

        self.backend = FemmBackend()
        self.materials = {}
        self._load_material_db()

        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._update_status()

    # ---- Menu ----
    def _build_menu(self):
        bar = self.menuBar()
        # File
        fm = bar.addMenu("File(&F)")
        fm.addAction(self._act("Open .fem...", self.open_fem, "Ctrl+O"))
        fm.addAction(self._act("Load .ans...", self.open_ans))
        fm.addSeparator()
        fm.addAction(self._act("Save Project...", self.save_project, "Ctrl+S"))
        fm.addAction(self._act("Load Project...", self.load_project, "Ctrl+Shift+O"))
        fm.addSeparator()
        fm.addAction(self._act("Exit", self.close, "Ctrl+Q"))
        # FEMM
        mm = bar.addMenu("FEMM(&M)")
        mm.addAction(self._act("Start FEMM (COM)", self.start_femm_com))
        mm.addAction(self._act("Use Lua CLI mode", self.start_femm_lua))
        mm.addSeparator()
        mm.addAction(self._act("Close FEMM", self.stop_femm))
        # Model
        dm = bar.addMenu("Model(&D)")
        dm.addAction(self._act("Add Circuit...", self.add_circuit))
        dm.addAction(self._act("Add Material from Library...", self.add_material_from_lib))
        dm.addAction(self._act("Run Analysis", self.run_analyze, "F5"))
        # Post-processing
        pm = bar.addMenu("Post(&P)")
        pm.addAction(self._act("FEMM Density Plot", self.show_density))
        pm.addAction(self._act("Sample & Export PNG...", self.sample_and_export))
        # Help
        hm = bar.addMenu("Help(&H)")
        hm.addAction(self._act("About", self.show_about))

    def _act(self, text, slot, shortcut=None):
        a = QAction(text, self)
        a.triggered.connect(slot)
        if shortcut:
            a.setShortcut(shortcut)
        return a

    # ---- Toolbar ----
    def _build_toolbar(self):
        tb = QToolBar("Main"); tb.setMovable(False); self.addToolBar(tb)
        tb.addAction(self._act("COM Connect", self.start_femm_com))
        tb.addAction(self._act("Lua Mode", self.start_femm_lua))
        tb.addSeparator()
        tb.addAction(self._act("Open .fem", self.open_fem))
        tb.addAction(self._act("Load .ans", self.open_ans))
        tb.addSeparator()
        tb.addAction(self._act("Analyze (F5)", self.run_analyze))
        tb.addAction(self._act("Density Plot", self.show_density))
        tb.addAction(self._act("Sample PNG", self.sample_and_export))

    # ---- Central panel ----
    def _build_central(self):
        sp = QSplitter(Qt.Horizontal)
        # Left: project tree
        left = QWidget(); ll = QVBoxLayout(); ll.setContentsMargins(4,4,4,4)
        lbl = QLabel("Project Browser")
        lbl.setStyleSheet("font-weight:bold; font-size:13px;")
        ll.addWidget(lbl)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Item", "Value"])
        self.tree.setColumnWidth(0, 160)
        self._tr_conn = QTreeWidgetItem(self.tree, ["Connection", "not connected"])
        self._tr_fem  = QTreeWidgetItem(self.tree, ["FEM File", "(none)"])
        self._tr_mat  = QTreeWidgetItem(self.tree, ["Materials", f"{len(self.materials)} items"])
        ll.addWidget(self.tree)
        left.setLayout(ll)
        # Right: tabs
        self.tabs = QTabWidget()
        # Log tab
        self.log = QTextEdit(); self.log.setReadOnly(True)
        self.tabs.addTab(self.log, "Log")
        # Materials tab
        mp = QWidget(); ml = QVBoxLayout()
        self.mat_tree = QTreeWidget()
        self.mat_tree.setHeaderLabels(["Material", "mu", "sigma", "rho"])
        self._fill_mat_tree()
        ml.addWidget(self.mat_tree); mp.setLayout(ml)
        self.tabs.addTab(mp, "Materials")
        # Results tab
        rp = QWidget(); rl = QVBoxLayout()
        self.result_text = QTextEdit(); self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("Analysis results will appear here...")
        rl.addWidget(self.result_text); rp.setLayout(rl)
        self.tabs.addTab(rp, "Results")
        sp.addWidget(left); sp.addWidget(self.tabs)
        sp.setStretchFactor(0, 1); sp.setStretchFactor(1, 3)
        self.setCentralWidget(sp)

    def _build_statusbar(self):
        self.status = QStatusBar(); self.setStatusBar(self.status)
        self.progress = QProgressBar(); self.progress.setMaximumWidth(200)
        self.progress.setVisible(False)
        self.status.addPermanentWidget(self.progress)

    def _update_status(self):
        self.status.showMessage(f"Mode: {self.backend.mode}  |  {APP_NAME} v{APP_VERSION}")
        self._tr_conn.setText(1, self.backend.mode)

    def _log(self, msg):
        self.log.append(msg)

    # ---- Materials ----
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

    # ---- FEMM connection ----
    def start_femm_com(self):
        try:
            self.backend.connect_com()
            self._log("[OK] FEMM started via COM (visible).")
            self._update_status()
        except ImportError:
            QMessageBox.critical(self, "Error",
                "Cannot import pyfemm.\n\n"
                "Please install:\n  pip install pyfemm pywin32\n\n"
                "Or use Lua CLI mode instead.")
        except Exception as e:
            QMessageBox.critical(self, "COM Connection Failed", str(e))
            self._log(f"[ERR] COM failed: {e}")

    def start_femm_lua(self):
        try:
            self.backend.connect_lua()
            self._log("[OK] Switched to Lua CLI mode.")
            self._update_status()
        except FileNotFoundError as e:
            QMessageBox.critical(self, "FEMM Not Found", str(e))

    def stop_femm(self):
        self.backend.disconnect()
        self._log("[OK] FEMM disconnected.")
        self._update_status()

    # ---- File ops ----
    def open_fem(self):
        if not self._need_conn(): return
        p, _ = QFileDialog.getOpenFileName(self, "Open FEM", "", "FEMM Model (*.fem);;All (*)")
        if not p: return
        try:
            self.backend.load_fem(p)
            self._tr_fem.setText(1, os.path.basename(p))
            self._log(f"[OK] Loaded: {p}")
        except Exception as e:
            QMessageBox.critical(self, "Load Failed", str(e))

    def open_ans(self):
        if not self._need_conn(): return
        p, _ = QFileDialog.getOpenFileName(self, "Load Solution", "", "FEMM Solution (*.ans);;All (*)")
        if not p: return
        try:
            self.backend.load_solution(p)
            self._log(f"[OK] Solution loaded: {p}")
        except Exception as e:
            QMessageBox.critical(self, "Load Failed", str(e))

    def save_project(self):
        proj = {"fem": self.backend._current_fem, "mode": self.backend.mode}
        p, _ = QFileDialog.getSaveFileName(self, "Save Project", "project.json", "JSON (*.json)")
        if not p: return
        with open(p, "w", encoding="utf-8") as f:
            json.dump(proj, f, ensure_ascii=False, indent=2)
        self._log(f"[OK] Project saved: {p}")

    def load_project(self):
        p, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "JSON (*.json);;All (*)")
        if not p: return
        with open(p, "r", encoding="utf-8") as f:
            proj = json.load(f)
        fem = proj.get("fem")
        if fem and os.path.isfile(fem) and self.backend.connected:
            self.backend.load_fem(fem)
            self._tr_fem.setText(1, os.path.basename(fem))
        self._log(f"[OK] Project loaded: {p}")

    # ---- Model ops ----
    def add_circuit(self):
        if not self._need_conn(): return
        dlg = CircuitDialog(self)
        if dlg.exec() != QDialog.Accepted: return
        name = dlg.name_edit.text().strip()
        cur = dlg.current_spin.value()
        ser = 1 if dlg.series_combo.currentIndex() == 0 else 0
        try:
            self.backend.add_circuit(name, cur, ser)
            self._log(f"[OK] Circuit added: {name}, I={cur} A")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def add_material_from_lib(self):
        if not self.materials:
            QMessageBox.information(self, "Materials", "Material library is empty.")
            return
        names = list(self.materials.keys())
        item, ok = QInputDialog.getItem(self, "Select Material", "Material:", names, 0, False)
        if not ok or not item: return
        if self.backend.connected:
            try:
                self.backend.add_material(item)
                self._log(f"[OK] Material added: {item}")
            except Exception as e:
                self._log(f"[WARN] add_material failed: {e}")

    # ---- Analysis ----
    def run_analyze(self):
        if not self._need_conn(): return
        self._log("[...] Running analysis...")
        self.progress.setVisible(True); self.progress.setRange(0, 0)
        self._worker = AnalyzeWorker(self.backend)
        self._worker.finished.connect(self._on_analyze_done)
        self._worker.start()

    def _on_analyze_done(self, ok, msg):
        self.progress.setVisible(False)
        if ok:
            self._log(f"[OK] {msg}")
            self.result_text.append("=== Analysis Complete ===")
            QMessageBox.information(self, "Done", msg)
        else:
            self._log(f"[ERR] {msg}")
            QMessageBox.warning(self, "Analysis Failed", msg)

    # ---- Post-processing ----
    def show_density(self):
        if not self._need_conn(): return
        try:
            self.backend.show_density_plot()
            self._log("[OK] Density plot shown in FEMM.")
        except Exception as e:
            QMessageBox.critical(self, "Failed", str(e))

    def sample_and_export(self):
        if not self._need_conn(): return
        dlg = SampleDialog(self)
        if dlg.exec() != QDialog.Accepted: return
        sp, _ = QFileDialog.getSaveFileName(self, "Save PNG", "field_plot.png", "PNG (*.png)")
        if not sp: return
        self._log("[...] Sampling field...")
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
            ax.set_title("Magnetic Flux Density |B|")
            fig.tight_layout(); fig.savefig(sp, dpi=150); plt.close(fig)
            bmax = float(B.max())
            bmean = float(B[B > 0].mean()) if (B > 0).any() else 0.0
            r = (f"Sampling done: {dlg.nx.value()}x{dlg.ny.value()} points\n"
                 f"B_max = {bmax:.4f} T\nB_mean (nonzero) = {bmean:.4f} T\n"
                 f"Saved: {sp}")
            self.result_text.append(r)
            self._log(f"[OK] Field plot saved: {sp}")
            QMessageBox.information(self, "Done", r)
        except Exception as e:
            QMessageBox.critical(self, "Sampling Failed", str(e))
            self._log(f"[ERR] {e}")
        finally:
            self.progress.setVisible(False)

    # ---- Help ----
    def show_about(self):
        QMessageBox.about(self, f"About {APP_NAME}",
            f"<h2>{APP_NAME}</h2><p>Version {APP_VERSION}</p>"
            "<p>Professional FEMM pre/post-processing tool.</p>"
            "<p>Supports COM (ActiveX) and Lua CLI dual mode.</p>"
            "<hr><p>2026 - Commercial License</p>")

    # ---- Helpers ----
    def _need_conn(self):
        if self.backend.connected:
            return True
        QMessageBox.warning(self, "Not Connected",
            "Please start FEMM first via the FEMM menu\n"
            "(COM Connect or Lua CLI mode).")
        return False

    def closeEvent(self, event):
        if self.backend.connected:
            self.backend.disconnect()
        event.accept()
'''

# ── main.py ──
files["main.py"] = r'''import sys
from PySide6.QtWidgets import QApplication
from pyfemm_gui.gui import MainWindow, QSS

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
'''

# Write all files
for name, content in files.items():
    path = os.path.join(GUI_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] {path}")

print("\nAll GUI files written successfully.")
