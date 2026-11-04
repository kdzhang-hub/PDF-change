"""Activate existing user fonts for this Windows session; no registry/file writes."""
from pathlib import Path
import sys,ctypes,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.text_recovery import candidates
result=[];seen=set()
for path,index,name in candidates():
    if 'AppData' not in path or path in seen:continue
    seen.add(path)
    count=ctypes.windll.gdi32.AddFontResourceExW(ctypes.c_wchar_p(path),0,None)
    result.append({'font':name,'registered_faces':count})
ctypes.windll.user32.SendNotifyMessageW(0xffff,0x1d,0,0)
print(json.dumps(result,ensure_ascii=True))
