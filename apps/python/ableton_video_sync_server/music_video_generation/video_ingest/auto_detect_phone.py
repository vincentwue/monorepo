import time, psutil, subprocess

def mtp_ready():
    for p in psutil.disk_partitions():
        if "MTP" in p.opts or "PortableDevice" in p.device:
            return True
    return False

while True:
    if mtp_ready():
        print("[OK] MTP Zugriff erlaubt  starte Sync!")
        subprocess.run(["python", "D:/scripts/sync_android.py"])
        break
    else:
        print(" Warten auf Freigabe...")
    time.sleep(3)
