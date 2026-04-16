"""Diagnose pyfemm import issue."""
import traceback
import sys

print(f"Python: {sys.executable}")
print(f"Version: {sys.version}")

try:
    import pyfemm
    print(f"[OK] pyfemm imported: {pyfemm.__file__}")
    print(f"     dir: {[x for x in dir(pyfemm) if not x.startswith('_')]}")
except Exception:
    print("[FAIL] Cannot import pyfemm:")
    traceback.print_exc()

print()
try:
    import win32com.client
    print(f"[OK] win32com imported: {win32com.__file__}")
except Exception:
    print("[FAIL] Cannot import win32com:")
    traceback.print_exc()

print()
try:
    import pyfemm
    print("Calling pyfemm.openfemm()...")
    pyfemm.openfemm()
    print("[OK] openfemm() succeeded!")
    pyfemm.closefemm()
except Exception:
    print("[FAIL] openfemm() failed:")
    traceback.print_exc()
