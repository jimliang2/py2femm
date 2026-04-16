"""
FEMM backend - COM (femm) + Lua CLI fallback.
femm module is imported lazily only when connect_com() is called.
Note: pip package is 'pyfemm', but import name is 'femm'.
"""
import math
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
        import femm
        femm.openfemm()
        self._pyfemm = femm
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

    def add_material(self, name, props=None):
        """Add material to FEMM using full py2femm-compatible properties.
        props keys: mu_x, mu_y, H_c, J, Sigma, Lam_d, Phi_hmax, lam_fill,
                    LamType, Phi_hx, Phi_hy, NStrands, WireD, bh_b, bh_h
        """
        if self._mode == "COM":
            if props:
                self._pyfemm.mi_addmaterial(
                    name,
                    props.get("mu_x", 1),
                    props.get("mu_y", 1),
                    props.get("H_c", 0),
                    props.get("J", 0),
                    props.get("Sigma", 0),
                    props.get("Lam_d", 0),
                    props.get("Phi_hmax", 0),
                    props.get("lam_fill", 1),
                    props.get("LamType", 0),
                    props.get("Phi_hx", 0),
                    props.get("Phi_hy", 0),
                    props.get("NStrands", 0),
                    props.get("WireD", 0),
                )
                # Add BH curve data if present
                bh_b = props.get("bh_b")
                bh_h = props.get("bh_h")
                if bh_b and bh_h and len(bh_b) == len(bh_h):
                    for b, h in zip(bh_b, bh_h):
                        self._pyfemm.mi_addbhpoint(name, b, h)
            else:
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
                    bx = abs(vals[1]) if isinstance(vals[1], complex) else vals[1]
                    by = abs(vals[2]) if isinstance(vals[2], complex) else vals[2]
                    B[j, i] = (bx**2 + by**2)**0.5
        return xs, ys, B

    # ---- Material modification ----
    def modify_material(self, old_name, new_name, props):
        """Delete old material and add new one with full properties."""
        if self._mode == "COM":
            try:
                self._pyfemm.mi_deletematerial(old_name)
            except Exception:
                pass
            self.add_material(new_name, props)

    def get_model_materials(self):
        """Read material names from the current .fem file."""
        if not self._current_fem or not os.path.isfile(self._current_fem):
            return []
        materials = []
        in_block = False
        with open(self._current_fem, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                stripped = line.strip()
                if stripped == "[BlockProps]":
                    in_block = True
                    continue
                if in_block:
                    if stripped.startswith("[") and stripped.endswith("]"):
                        break
                    if stripped.startswith("<BlockName>"):
                        name = stripped.replace("<BlockName>", "").strip().strip("=").strip().strip('"').strip("'")
                        if name:
                            materials.append(name)
        return materials

    def get_geometry_segments(self):
        """Parse [NumPoints] and [NumSegments] from .fem to get geometry outlines."""
        if not self._current_fem or not os.path.isfile(self._current_fem):
            return [], []
        lines = open(self._current_fem, "r", encoding="utf-8", errors="ignore").readlines()
        points = []
        segments = []
        i = 0
        while i < len(lines):
            s = lines[i].strip()
            if s.startswith("[NumPoints]"):
                n = int(s.split("=")[1].strip())
                for j in range(1, n + 1):
                    parts = lines[i + j].split()
                    points.append((float(parts[0]), float(parts[1])))
                i += n + 1
            elif s.startswith("[NumSegments]"):
                n = int(s.split("=")[1].strip())
                for j in range(1, n + 1):
                    parts = lines[i + j].split()
                    segments.append((int(parts[0]), int(parts[1])))
                i += n + 1
            else:
                i += 1
        return points, segments

    # ---- Transformer model generation ----
    def generate_transformer(self, params):
        """Generate a complete EE-core transformer model in FEMM.
        params: dict with core_w, core_h, core_d, window_w, window_h,
                n_pri, n_sec, wire_d_pri, wire_d_sec, i_pri, i_sec,
                freq, insul_gap, core_mat, wind_mat, save_path
        """
        if self._mode != "COM" or not self._pyfemm:
            raise RuntimeError("COM not connected")
        f = self._pyfemm

        cw = params["core_w"]       # center leg width (mm)
        ch = params["core_h"]       # top/bottom plate height (mm)  
        cd = params["core_d"]       # core depth (mm) - for 2D axisym not used directly
        ww = params["window_w"]     # winding window width (mm)
        wh = params["window_h"]     # winding window height (mm)
        freq = params["freq"]
        insul = params["insul_gap"]

        # EE core geometry (axisymmetric, only right half)
        # Center leg: x=0..cw, y=0..wh+2*ch
        # Bottom plate: x=0..cw+ww+cw, y=0..ch  (actually 0 to outer)
        # Top plate: x=0..cw+ww+cw, y=ch+wh..2*ch+wh
        # Outer leg: x=cw+ww..cw+ww+cw, y=0..2*ch+wh
        ow = cw  # outer leg width = center leg width
        total_w = cw + ww + ow
        total_h = 2 * ch + wh

        # New document
        f.newdocument(0)  # 0 = magnetics
        f.mi_probdef(freq, "millimeters", "planar", 1e-8, cd, 30, 0)

        # --- Draw core outline ---
        # Bottom plate
        pts_core = [
            (0, 0), (total_w, 0), (total_w, ch),
            (cw + ww, ch), (cw, ch),  (0, ch),
            # Top plate
            (0, ch + wh), (cw, ch + wh), (cw + ww, ch + wh),
            (total_w, ch + wh), (total_w, total_h), (0, total_h),
        ]
        # Bottom plate outline
        f.mi_addnode(0, 0); f.mi_addnode(total_w, 0)
        f.mi_addnode(total_w, ch); f.mi_addnode(0, ch)
        f.mi_addsegment(0, 0, total_w, 0)
        f.mi_addsegment(total_w, 0, total_w, ch)
        f.mi_addsegment(total_w, ch, cw + ww, ch)
        f.mi_addsegment(cw, ch, 0, ch)
        f.mi_addsegment(0, ch, 0, 0)

        # Top plate outline
        f.mi_addnode(0, ch + wh); f.mi_addnode(cw, ch + wh)
        f.mi_addnode(cw + ww, ch + wh); f.mi_addnode(total_w, ch + wh)
        f.mi_addnode(total_w, total_h); f.mi_addnode(0, total_h)
        f.mi_addsegment(0, ch + wh, cw, ch + wh)
        f.mi_addsegment(cw + ww, ch + wh, total_w, ch + wh)
        f.mi_addsegment(total_w, ch + wh, total_w, total_h)
        f.mi_addsegment(total_w, total_h, 0, total_h)
        f.mi_addsegment(0, total_h, 0, ch + wh)

        # Center leg (right side: x=0..cw)
        f.mi_addnode(cw, ch); f.mi_addnode(cw, ch + wh)
        f.mi_addsegment(cw, ch, cw, ch + wh)

        # Outer leg (x=cw+ww..total_w)
        f.mi_addnode(cw + ww, ch); f.mi_addnode(cw + ww, ch + wh)
        f.mi_addsegment(cw + ww, ch, cw + ww, ch + wh)

        # --- Winding regions ---
        # Primary: in window, left half
        pw = (ww - insul) / 2  # primary winding width
        px0 = cw + insul / 4
        px1 = px0 + pw - insul / 4
        py0 = ch + insul / 2
        py1 = ch + wh - insul / 2
        f.mi_addnode(px0, py0); f.mi_addnode(px1, py0)
        f.mi_addnode(px1, py1); f.mi_addnode(px0, py1)
        f.mi_addsegment(px0, py0, px1, py0)
        f.mi_addsegment(px1, py0, px1, py1)
        f.mi_addsegment(px1, py1, px0, py1)
        f.mi_addsegment(px0, py1, px0, py0)

        # Secondary: in window, right half
        sx0 = px1 + insul / 2
        sx1 = cw + ww - insul / 4
        f.mi_addnode(sx0, py0); f.mi_addnode(sx1, py0)
        f.mi_addnode(sx1, py1); f.mi_addnode(sx0, py1)
        f.mi_addsegment(sx0, py0, sx1, py0)
        f.mi_addsegment(sx1, py0, sx1, py1)
        f.mi_addsegment(sx1, py1, sx0, py1)
        f.mi_addsegment(sx0, py1, sx0, py0)

        # --- Boundary (air region) ---
        margin = max(total_w, total_h) * 2
        f.mi_addnode(-margin, -margin)
        f.mi_addnode(margin, -margin)
        f.mi_addnode(margin, margin + total_h)
        f.mi_addnode(-margin, margin + total_h)
        f.mi_addsegment(-margin, -margin, margin, -margin)
        f.mi_addsegment(margin, -margin, margin, margin + total_h)
        f.mi_addsegment(margin, margin + total_h, -margin, margin + total_h)
        f.mi_addsegment(-margin, margin + total_h, -margin, -margin)

        # --- Materials (must be added AFTER newdocument) ---
        core_mat = params["core_mat"]
        wind_mat = params["wind_mat"]
        # Add Air
        f.mi_addmaterial("Air", 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0)
        # Add core material
        core_props = params.get("core_props")
        if core_props:
            self.add_material(core_mat, core_props)
        else:
            f.mi_addmaterial(core_mat)
        # Add winding material (skip if same as core)
        wind_props = params.get("wind_props")
        if wind_mat != core_mat:
            if wind_props:
                self.add_material(wind_mat, wind_props)
            else:
                f.mi_addmaterial(wind_mat)

        # --- Circuits ---
        n_pri = params["n_pri"]
        n_sec = params["n_sec"]
        i_pri = params["i_pri"]
        i_sec = params["i_sec"]
        f.mi_addcircprop("primary", i_pri, 1)
        f.mi_addcircprop("secondary", i_sec, 1)

        # --- Block labels ---
        # Core bottom plate center
        f.mi_addblocklabel(total_w / 2, ch / 2)
        f.mi_selectlabel(total_w / 2, ch / 2)
        f.mi_setblockprop(core_mat, 0, 0, "", 0, 0, 0)
        f.mi_clearselected()

        # Core top plate center
        f.mi_addblocklabel(total_w / 2, ch + wh + ch / 2)
        f.mi_selectlabel(total_w / 2, ch + wh + ch / 2)
        f.mi_setblockprop(core_mat, 0, 0, "", 0, 0, 0)
        f.mi_clearselected()

        # Center leg
        f.mi_addblocklabel(cw / 2, ch + wh / 2)
        f.mi_selectlabel(cw / 2, ch + wh / 2)
        f.mi_setblockprop(core_mat, 0, 0, "", 0, 0, 0)
        f.mi_clearselected()

        # Outer leg
        f.mi_addblocklabel(cw + ww + ow / 2, ch + wh / 2)
        f.mi_selectlabel(cw + ww + ow / 2, ch + wh / 2)
        f.mi_setblockprop(core_mat, 0, 0, "", 0, 0, 0)
        f.mi_clearselected()

        # Primary winding
        pmx = (px0 + px1) / 2; pmy = (py0 + py1) / 2
        f.mi_addblocklabel(pmx, pmy)
        f.mi_selectlabel(pmx, pmy)
        f.mi_setblockprop(wind_mat, 0, 0, "primary", 0, 0, n_pri)
        f.mi_clearselected()

        # Secondary winding
        smx = (sx0 + sx1) / 2; smy = (py0 + py1) / 2
        f.mi_addblocklabel(smx, smy)
        f.mi_selectlabel(smx, smy)
        f.mi_setblockprop(wind_mat, 0, 0, "secondary", 0, 0, n_sec)
        f.mi_clearselected()

        # Air (window gap between windings)
        air_x = (px1 + sx0) / 2; air_y = (py0 + py1) / 2
        f.mi_addblocklabel(air_x, air_y)
        f.mi_selectlabel(air_x, air_y)
        f.mi_setblockprop("Air", 0, 0, "", 0, 0, 0)
        f.mi_clearselected()

        # Air (outer region)
        f.mi_addblocklabel(-margin / 2, -margin / 2)
        f.mi_selectlabel(-margin / 2, -margin / 2)
        f.mi_setblockprop("Air", 0, 0, "", 0, 0, 0)
        f.mi_clearselected()

        # --- Boundary condition ---
        f.mi_addboundprop("A=0", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        # Apply to outer boundary
        for seg in [(-margin, -margin, margin, -margin),
                     (margin, -margin, margin, margin + total_h),
                     (margin, margin + total_h, -margin, margin + total_h),
                     (-margin, margin + total_h, -margin, -margin)]:
            f.mi_selectsegment((seg[0] + seg[2]) / 2, (seg[1] + seg[3]) / 2)
        f.mi_setsegmentprop("A=0", 0, 0, 0, 0)
        f.mi_clearselected()

        # --- Save ---
        save_path = params.get("save_path", "")
        if save_path:
            f.mi_saveas(save_path)
            self._current_fem = save_path

        f.mi_zoomnatural()

        return {
            "total_w": total_w, "total_h": total_h,
            "core_area_mm2": cw * cd,
            "window_area_mm2": ww * wh,
            "pri_region": (px0, py0, px1, py1),
            "sec_region": (sx0, py0, sx1, py1),
        }

    # ---- Transformer parameter extraction ----
    def get_transformer_params(self, primary_circuit="primary",
                                secondary_circuit="secondary",
                                freq=100000):
        """Extract full transformer parameters from post-processor.
        Returns dict with Lp, Ls, M, k, Lk_pri, Lk_sec, Lm, Rp, Rs,
        turns_ratio, pri/sec circuit data.
        """
        if self._mode != "COM" or not self._pyfemm:
            raise RuntimeError("COM not connected")

        result = {"freq_Hz": freq}

        # Get circuit properties: returns (I, V, FluxLinkage) as complex
        try:
            pri = self._pyfemm.mo_getcircuitproperties(primary_circuit)
            result["pri_I"] = pri[0]
            result["pri_V"] = pri[1]
            result["pri_Flux"] = pri[2]
        except Exception as e:
            raise RuntimeError(f"Cannot read primary circuit '{primary_circuit}': {e}")

        try:
            sec = self._pyfemm.mo_getcircuitproperties(secondary_circuit)
            result["sec_I"] = sec[0]
            result["sec_V"] = sec[1]
            result["sec_Flux"] = sec[2]
        except Exception as e:
            raise RuntimeError(f"Cannot read secondary circuit '{secondary_circuit}': {e}")

        omega = 2 * math.pi * freq
        I_pri = pri[0]  # complex current
        I_sec = sec[0]
        V_pri = pri[1]
        V_sec = sec[1]
        Flux_pri = pri[2]
        Flux_sec = sec[2]

        # Primary impedance and inductance
        if abs(I_pri) > 1e-15:
            Z_pri = V_pri / I_pri
            result["Z_pri"] = Z_pri
            result["R_pri"] = Z_pri.real
            if omega > 0:
                result["L_pri"] = Z_pri.imag / omega
            else:
                result["L_pri"] = 0
        else:
            result["Z_pri"] = 0
            result["R_pri"] = 0
            result["L_pri"] = 0

        # Secondary impedance and inductance
        if abs(I_sec) > 1e-15:
            Z_sec = V_sec / I_sec
            result["Z_sec"] = Z_sec
            result["R_sec"] = Z_sec.real
            if omega > 0:
                result["L_sec"] = Z_sec.imag / omega
            else:
                result["L_sec"] = 0
        else:
            result["Z_sec"] = 0
            result["R_sec"] = 0
            result["L_sec"] = 0

        Lp = result["L_pri"]
        Ls = result["L_sec"]

        # Mutual inductance from flux linkage
        # M = Flux_sec / I_pri (when secondary is open-circuit or lightly loaded)
        if abs(I_pri) > 1e-15:
            M = abs(Flux_sec) / abs(I_pri)
        else:
            M = 0
        result["M"] = M

        # Coupling coefficient k = M / sqrt(Lp * Ls)
        if abs(Lp) > 1e-20 and abs(Ls) > 1e-20:
            k = M / math.sqrt(abs(Lp) * abs(Ls))
            k = min(k, 1.0)  # clamp
        else:
            k = 0
        result["k"] = k

        # Leakage inductances
        result["Lk_pri"] = abs(Lp) * (1 - k * k)
        result["Lk_sec"] = abs(Ls) * (1 - k * k)

        # Magnetizing inductance (referred to primary)
        result["Lm"] = abs(Lp) * k * k if k > 0 else abs(Lp)

        # Turns ratio from flux linkage
        if abs(Flux_sec) > 1e-20:
            result["turns_ratio"] = abs(Flux_pri) / abs(Flux_sec)
        else:
            result["turns_ratio"] = 0

        return result
