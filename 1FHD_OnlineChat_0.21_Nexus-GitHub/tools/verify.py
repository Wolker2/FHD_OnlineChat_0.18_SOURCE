#!/usr/bin/env python3
"""Fresh isolated offline checks. No public/private chat traffic or deployment."""
import argparse,hashlib,json,shutil,subprocess,sys,tempfile,platform
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from build import build,build_native,hashes,load
import pefile

def verify(exes):
    logs={}
    with tempfile.TemporaryDirectory(prefix='onlinechat-verify-') as td:
        root=Path(td)
        shutil.copytree(ROOT/'SOURCE',root/'SOURCE')
        shutil.copytree(ROOT/'Native',root/'Native',ignore=shutil.ignore_patterns('*.dll'))
        for n in ('README_FIRST_RU.txt','build-profile.json'):shutil.copyfile(ROOT/n,root/n)
        files=build(root);digest=hashes(files);assert digest==load('original-file-sha256.json')
        dll=pefile.PE(data=files['Native/FHDOnlineChat.XenoPlugin.dll'])
        assert dll.FILE_HEADER.Machine==0x14c and dll.OPTIONAL_HEADER.Magic==0x10b
        exports=[s.name.decode() for s in dll.DIRECTORY_ENTRY_EXPORT.symbols if s.name]
        assert not any(n.startswith('Test_') for n in exports)
        assert {'XenoPlugin_Query','XenoPlugin_Initialize'}<=set(exports)
        assert files['ModuleInfo.txt'].startswith(b'\xff\xfe')
        assert 'FONT' in files['ModuleInfo.txt'].decode('utf-16').upper() or 'ШРИФТ' in files['ModuleInfo.txt'].decode('utf-16').upper()
        build_native(root,test=True,output=root/'SOURCE/tests_runtime_font1.dll')
        qa=root/'SOURCE/QA'
        def run(label,args):
            p=subprocess.run(args,cwd=root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            logs[label]=p.stdout
            print(label,p.returncode,flush=True)
            if p.returncode:
                print(p.stdout,flush=True);raise RuntimeError(label+' failed')
        run('ui_and_wrap',[sys.executable,str(qa/'wrap_test.py'),*exes])
        ui=json.loads((qa/'results.json').read_text());wrap=json.loads((qa/'wrap_results.json').read_text())
        compat=json.loads((qa/'compatibility_results.json').read_text()) if exes else None
        run('network',[sys.executable,str(qa/'network_test.py')])
        network=json.loads((qa/'network_results.json').read_text())
        run('server',['node',str(qa/'server.test.mjs')])
        server=json.loads((qa/'server_results.json').read_text())
        assert len(ui['checks'])>=194 and len(wrap['wrap_checks'])==125
        assert network['checks'] and len(server['results'])==5
        if exes:assert len(compat['profiles'])==4
        return {'status':'PASS','python':platform.python_version(),'node':subprocess.check_output(['node','--version'],text=True).strip(),'original_runtime_files':digest,'all_four_runtime_files_byte_identical':True,'production_pe32_i386':True,'production_test_exports':False,'ui_checks':len(ui['checks']),'wrap_checks':len(wrap['wrap_checks']),'network_checks':len(network['checks']),'server_scenarios':len(server['results']),'compatibility':compat,'ui':ui,'wrap':wrap,'network':network,'server':server,'live_network_or_server_contact':False,'server_deployed':False,'windows_game_executed':False,'game_executables_bundled':False,'logs':logs}

def main():
    p=argparse.ArgumentParser();p.add_argument('--exe-a',type=Path);p.add_argument('--exe-b',type=Path);p.add_argument('--report',type=Path,default=ROOT/'dist/verification.json');a=p.parse_args()
    assert bool(a.exe_a)==bool(a.exe_b),'Provide both EXE fixtures or neither'
    exes=[str(a.exe_a.resolve()),str(a.exe_b.resolve())] if a.exe_a else []
    if exes:
        for path,want in zip(exes,('83300344af802bc51e64389c58f047e5afdf195c133048098be3881fae29ed98','e43a4b15503c705eebe2d8ce5778c2a2fb090db515a3fd86d319e5c5aa692ebf')):
            assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==want
    result=verify(exes);a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('status','ui_checks','wrap_checks','network_checks','server_scenarios','all_four_runtime_files_byte_identical')}))
if __name__=='__main__':main()
