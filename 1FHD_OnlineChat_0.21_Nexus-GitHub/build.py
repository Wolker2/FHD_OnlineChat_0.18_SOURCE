#!/usr/bin/env python3
"""Rebuild the supplied preview from C; normalize only its original PE timestamp."""
import argparse,hashlib,json,struct,subprocess,sys,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def load(name,root=ROOT):return json.loads((root/name).read_text(encoding='utf-8'))
def hashes(files):return {n:hashlib.sha256(b).hexdigest() for n,b in files.items()}
def build_native(root=ROOT,test=False,output=None):
    profile=load('build-profile.json',root)
    with tempfile.TemporaryDirectory(prefix='onlinechat-compile-') as d:
        dll=Path(d)/( 'tests_runtime_font1.dll' if test else profile['dll_filename'])
        args=[sys.executable,'-m','ziglang','cc','-target','x86-windows-gnu','-shared','-O2','-fno-builtin']
        args+=['-DFHD_TEST'] if test else ['-s']
        args+=['bridge.c','overlay.c','plugin_zig.def','-luser32','-lgdi32','-lwinhttp','-lshell32','-o',str(dll)]
        subprocess.run(args,cwd=root/'SOURCE',check=True)
        data=bytearray(dll.read_bytes())
        if not test:
            nt=struct.unpack_from('<I',data,0x3c)[0]
            assert data[nt:nt+4]==b'PE\0\0'
            struct.pack_into('<I',data,nt+8,int(profile['production_pe_timestamp'],0))
        result=bytes(data)
        if output:
            output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(result)
        return result

def build(root=ROOT):
    return {'ModuleInfo.txt':b'\xff\xfe'+(root/'SOURCE/ModuleInfo.txt').read_bytes().decode('utf-8').encode('utf-16-le'),
            'Native/FHDOnlineChat.XenoPlugin.dll':build_native(root),
            'Native/FHDOnlineChat.XenoPlugin.ini':(root/'Native/FHDOnlineChat.XenoPlugin.ini').read_bytes(),
            'README_FIRST_RU.txt':(root/'README_FIRST_RU.txt').read_bytes()}

def main():
    p=argparse.ArgumentParser();p.add_argument('--verify-original',action='store_true');p.add_argument('--test-dll',type=Path);p.add_argument('--output',type=Path,default=ROOT/'dist/FHD_OnlineChat-0.21-FONT-PREVIEW-1-install.zip');a=p.parse_args()
    if a.test_dll:build_native(test=True,output=a.test_dll);return
    files=build();digest=hashes(files)
    if a.verify_original:assert digest==load('original-file-sha256.json'),'Rebuild differs from original'
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(a.output,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():
            entry=zipfile.ZipInfo('Mods/OtherMods/FHD_OnlineChat/'+name,(2026,10,28,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o100644<<16;z.writestr(entry,data)
    print(json.dumps({'output':str(a.output),'files':len(files),'original_verified':a.verify_original,'sha256':digest},indent=2))
if __name__=='__main__':main()
