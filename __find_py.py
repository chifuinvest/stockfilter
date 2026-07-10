"""查注册表 + 卸载清单，找所有 Python 安装路径，写进 __pypaths.txt"""
import winreg, os, pathlib

OUT = pathlib.Path(r"c:\Users\Bart\Documents\trae_projects\stockfilter\__pypaths.txt")
lines = []
def log(m):
    lines.append(m)
    print(m, flush=True)

log(f"=== PYTHON SEARCH @ {__import__('datetime').datetime.now()} ===")

# 1) Registry: HKCU\Software\Python\PythonCore\<ver>\InstallPath
for hive_name, hive in [("HKCU", winreg.HKEY_CURRENT_USER), ("HKLM", winreg.HKEY_LOCAL_MACHINE), ("HKLM64", winreg.HKEY_LOCAL_MACHINE)]:
    try:
        if hive_name == "HKLM64":
            k = winreg.OpenKey(hive, r"Software\Python\PythonCore", 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        else:
            k = winreg.OpenKey(hive, r"Software\Python\PythonCore", 0, winreg.KEY_READ)
        i = 0
        while True:
            try:
                ver = winreg.EnumKey(k, i); i += 1
                try:
                    ip = winreg.OpenKey(k, rf"{ver}\InstallPath")
                    exec_path, _ = winreg.QueryValueEx(ip, "ExecutablePath") if False else (None, None)
                    try:
                        install_path, _ = winreg.QueryValueEx(ip, "")
                        p = pathlib.Path(install_path) / "python.exe"
                        if p.exists():
                            log(f"[REG {hive_name}] Python {ver}:  {p}  (exists={p.exists()})")
                            try:
                                import subprocess
                                v = subprocess.run([str(p), "--version"], capture_output=True, text=True, timeout=10)
                                log(f"    -> version: {v.stdout.strip()} {v.stderr.strip()}")
                                pip = subprocess.run([str(p), "-m", "pip", "--version"], capture_output=True, text=True, timeout=10)
                                log(f"    -> pip: {pip.stdout.strip()}")
                            except Exception as e:
                                log(f"    -> version probe failed: {e}")
                    except FileNotFoundError:
                        pass
                except OSError:
                    pass
            except OSError:
                break
        winreg.CloseKey(k)
    except FileNotFoundError:
        log(f"[REG {hive_name}] PythonCore not present")
    except Exception as e:
        log(f"[REG {hive_name}] ERROR: {e}")

# 2) Env PATH search
log("\n=== PATH entries ===")
for p in os.environ.get("PATH", "").split(os.pathsep):
    p = p.strip().strip('"')
    if not p:
        continue
    cand = pathlib.Path(p) / "python.exe"
    try:
        if cand.exists():
            log(f"  [PATH] {cand}")
    except Exception:
        pass

# 3) Uninstall registry
log("\n=== Uninstall registry (DisplayName contains Python) ===")
for unkey in [
    r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
    r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
]:
    for hive_n, hive_v in [("HKCU", winreg.HKEY_CURRENT_USER), ("HKLM", winreg.HKEY_LOCAL_MACHINE)]:
        try:
            base = winreg.OpenKey(hive_v, unkey, 0, winreg.KEY_READ)
            j = 0
            while True:
                try:
                    sub = winreg.EnumKey(base, j); j += 1
                    try:
                        sk = winreg.OpenKey(base, sub)
                        dn = ""
                        loc = ""
                        try:
                            dn, _ = winreg.QueryValueEx(sk, "DisplayName")
                        except Exception:
                            pass
                        try:
                            loc, _ = winreg.QueryValueEx(sk, "InstallLocation")
                        except Exception:
                            pass
                        if "Python" in dn:
                            log(f"  [UNINSTALL {hive_n}] {dn}  InstallLocation={loc}")
                    except Exception:
                        pass
                except OSError:
                    break
            winreg.CloseKey(base)
        except Exception as e:
            pass

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"\nLOG WROTE TO {OUT}")
