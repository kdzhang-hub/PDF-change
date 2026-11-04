"""Map PDF PostScript font names to actual installed Windows families."""
from functools import lru_cache
from pathlib import Path
import os,struct


def user_font_dirs():
    # Windows packaged/sandboxed processes may redirect LOCALAPPDATA. Fonts
    # installed for this user still live under the actual profile directory.
    roots=[Path(os.environ.get('LOCALAPPDATA',''))/'Microsoft'/'Windows'/'Fonts',
           Path.home()/'AppData'/'Local'/'Microsoft'/'Windows'/'Fonts']
    return list(dict.fromkeys(path for path in roots if path.is_dir()))

def font_names(path):
    data=path if isinstance(path,bytes) else Path(path).read_bytes()
    offsets=[0]
    if data[:4]==b'ttcf':offsets=list(struct.unpack_from('>'+str(struct.unpack_from('>I',data,8)[0])+'I',data,12))
    fonts=[]
    for base in offsets:
        count=struct.unpack_from('>H',data,base+4)[0]
        names=None
        for i in range(count):
            pos=base+12+i*16
            if data[pos:pos+4]==b'name':names=struct.unpack_from('>I',data,pos+8)[0];break
        if names is None:continue
        n,strings=struct.unpack_from('>HH',data,names+2);records={};local_family=None
        for i in range(n):
            platform,enc,lang,key,length,start=struct.unpack_from('>6H',data,names+6+i*12)
            if key not in (1,4,6,16):continue
            raw=data[names+strings+start:names+strings+start+length]
            try:value=raw.decode('utf-16-be' if platform in (0,3) else 'mac_roman')
            except UnicodeError:continue
            if key==1 and lang==0x804:local_family=value
            rank=2 if lang==0x409 else 1 if platform==3 else 0
            if key not in records or rank>records[key][0]:records[key]=(rank,value)
        values={k:v[1] for k,v in records.items()}
        if local_family:values[1001]=local_family
        if values.get(1):fonts.append(values)
    return fonts

@lru_cache(maxsize=1)
def installed_map():
    mapping={}
    if os.name!='nt':return mapping
    import winreg
    paths=set()
    for hive in (winreg.HKEY_LOCAL_MACHINE,winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive,r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts') as key:
                for i in range(winreg.QueryInfoKey(key)[1]):
                    _,value,_=winreg.EnumValue(key,i)
                    if not isinstance(value,str):continue
                    p=Path(value)
                    for candidate in (p,Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/p,*[folder/p for folder in user_font_dirs()]):
                        if candidate.is_file():paths.add(candidate)
        except OSError:pass
    for folder in user_font_dirs():paths.update(p for p in folder.iterdir() if p.suffix.lower() in ('.ttf','.ttc','.otf'))
    for path in sorted(paths):
        try:
            for names in font_names(path):
                canonical=names.get(1001,names[1])
                # Typographic family name (16) is shared by Light/Regular/Heavy.
                # Treating it as a face alias made generic family names resolve
                # to a random weight depending on filesystem iteration order.
                for key,value in names.items():
                    if key!=16:mapping[value.replace(' ','').lower()]=canonical
        except (OSError,ValueError,struct.error,IndexError):continue
    return mapping

def resolve(name):
    aliases={'Helvetica':'Arial','Helvetica-Bold':'Arial','ArialMT':'Arial','Arial-BoldMT':'Arial','Times-Roman':'Times New Roman',
             'Courier':'Courier New','MicrosoftYaHei':'Microsoft YaHei','MicrosoftYaHei-Bold':'Microsoft YaHei','STSong-Light':'SimSun'}
    return installed_map().get(name.replace(' ','').lower(),aliases.get(name,name))

_ACTIVATED=set()
def activate_existing(families):
    if os.name!='nt':return
    import ctypes
    folders=user_font_dirs()
    needed={f.replace(' ','').lower() for f in families}
    changed=False
    for path in dict.fromkeys(p for folder in folders for p in folder.iterdir()):
        if path in _ACTIVATED or path.suffix.lower() not in ('.ttf','.ttc','.otf'):continue
        try:names=font_names(path)
        except (OSError,ValueError,struct.error):continue
        if not any(value.replace(' ','').lower() in needed for face in names for value in face.values()):continue
        count=ctypes.windll.gdi32.AddFontResourceExW(ctypes.c_wchar_p(str(path)),0,None)
        if count:_ACTIVATED.add(path);changed=True
    if changed:ctypes.windll.user32.SendNotifyMessageW(0xffff,0x1d,0,0)
