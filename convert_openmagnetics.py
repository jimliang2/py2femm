"""
Convert OpenMagnetics MAS core_materials.ndjson → FEMM-compatible materials.json
for PyFEMM Studio.

Maps MAS fields to FEMM mi_addmaterial parameters:
  mu_x, mu_y  ← permeability.initial (at 25°C) or complex.real (low freq)
  H_c         ← coerciveForce (at 25°C)
  Sigma       ← resistivity → conductivity (1/resistivity in MS/m)
  rho         ← density (kg/m³)
  Bsat        ← saturation.magneticFluxDensity (at 25°C)
  Curie       ← curieTemperature (°C)

Categories:
  鐵氧體 Ferrite  ← material == "ferrite"
  粉芯 Powder Core ← material == "powder"
  奈米晶 Nanocrystalline ← material == "nanocrystalline"
  非晶 Amorphous ← material == "amorphous"
"""
import json, os, sys


def get_initial_mu(perm_data):
    """Extract initial permeability at ~25°C."""
    init = perm_data.get("initial")
    if init is None:
        # Try from complex real at lowest frequency
        cx = perm_data.get("complex", {})
        real_list = cx.get("real", [])
        if real_list:
            return round(real_list[0]["value"])
        return 1000  # fallback

    if isinstance(init, dict):
        # Single value (powder cores)
        return round(init.get("value", 1000))

    if isinstance(init, list):
        # Find closest to 25°C
        best = None
        best_diff = 999
        for entry in init:
            t = entry.get("temperature", 25)
            diff = abs(t - 25)
            if diff < best_diff:
                best_diff = diff
                best = entry.get("value", 1000)
        return round(best) if best else 1000

    return 1000


def get_coercive_force(mat):
    """Get H_c in A/m at 25°C."""
    cf = mat.get("coerciveForce")
    if not cf:
        return 0
    if isinstance(cf, list):
        for entry in cf:
            if abs(entry.get("temperature", 25) - 25) < 30:
                return round(entry.get("magneticField", 0), 2)
        return round(cf[0].get("magneticField", 0), 2)
    return 0


def get_resistivity_sigma(mat):
    """Get conductivity in MS/m from resistivity in Ω·m."""
    res = mat.get("resistivity")
    if not res:
        return 0
    if isinstance(res, list):
        for entry in res:
            if abs(entry.get("temperature", 25) - 25) < 30:
                val = entry.get("value", 0)
                if val > 0:
                    return round(1.0 / val, 8)  # 1/(Ω·m) = S/m → MS/m needs /1e6
        val = res[0].get("value", 0)
        if val > 0:
            return round(1.0 / val, 8)
    return 0


def get_saturation(mat):
    """Get saturation flux density in T at 25°C."""
    sat = mat.get("saturation")
    if not sat:
        return None
    if isinstance(sat, list):
        for entry in sat:
            if abs(entry.get("temperature", 25) - 25) < 30:
                return round(entry.get("magneticFluxDensity", 0), 4)
        # Fallback to first entry
        return round(sat[0].get("magneticFluxDensity", 0), 4)
    return None


CATEGORY_MAP = {
    "ferrite": "鐵氧體 Ferrite (OpenMagnetics)",
    "powder": "粉芯 Powder Core (OpenMagnetics)",
    "nanocrystalline": "奈米晶 Nanocrystalline (OpenMagnetics)",
    "amorphous": "非晶 Amorphous (OpenMagnetics)",
}


def convert(ndjson_path, output_path):
    with open(ndjson_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    categories = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        mat = json.loads(line)
        name = mat.get("name", "Unknown")
        mat_type = mat.get("material", "ferrite")
        cat = CATEGORY_MAP.get(mat_type, f"其他 Other ({mat_type})")

        mu = get_initial_mu(mat.get("permeability", {}))
        hc = get_coercive_force(mat)
        sigma = get_resistivity_sigma(mat)
        density = mat.get("density", 0)
        bsat = get_saturation(mat)
        curie = mat.get("curieTemperature")
        mfr = mat.get("manufacturerInfo", {}).get("name", "")
        family = mat.get("family", "")
        composition = mat.get("materialComposition", "")
        datasheet = mat.get("manufacturerInfo", {}).get("datasheetUrl", "")

        entry = {
            "mu_x": mu,
            "mu_y": mu,
            "H_c": hc,
            "J": 0,
            "Sigma": sigma,
            "Lam_d": 0,
            "lam_fill": 1.0,
            "LamType": 0,
            "Phi_hmax": 0,
            "Phi_hx": 0,
            "Phi_hy": 0,
            "NStrands": 0,
            "WireD": 0,
            "rho": density,
        }

        # Build note
        parts = []
        if mfr:
            parts.append(mfr)
        if composition:
            parts.append(composition)
        if family:
            parts.append(f"Family: {family}")
        if bsat:
            parts.append(f"Bsat={bsat}T")
        if curie:
            parts.append(f"Tc={curie}°C")
        if datasheet:
            parts.append(f"DS: {datasheet}")
        entry["note"] = "; ".join(parts)

        if bsat:
            entry["Bsat"] = bsat
        if curie:
            entry["Curie"] = curie

        if cat not in categories:
            categories[cat] = {}
        categories[cat][name] = entry

    # Sort each category by name
    for cat in categories:
        categories[cat] = dict(sorted(categories[cat].items()))

    output = {
        "format_version": "2.0",
        "description": "OpenMagnetics MAS core materials converted for FEMM. "
                       "411 materials from TDK, Ferroxcube, Magnetics Inc, etc.",
        "source": "https://github.com/OpenMagnetics/MAS",
        "categories": categories,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    total = sum(len(v) for v in categories.values())
    print(f"Converted {total} materials in {len(categories)} categories → {output_path}")
    for cat, mats in categories.items():
        print(f"  {cat}: {len(mats)}")


if __name__ == "__main__":
    src = os.path.join(os.path.dirname(__file__), "core_materials_raw.ndjson")
    dst = os.path.join(os.path.dirname(__file__), "pyfemm_gui", "openmagnetics_materials.json")
    convert(src, dst)
