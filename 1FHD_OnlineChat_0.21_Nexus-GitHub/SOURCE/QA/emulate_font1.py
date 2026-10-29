"""Execute compiled PE32 plugin code on an x86 CPU emulator.
OS, networking and D3D COM are instrumented stubs; this is not a Windows/game test.
"""
import sys,json,struct
from pathlib import Path
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
P=Path(__file__).resolve().parents[1]
Q=Path(__file__).resolve().parent
u=Uc(UC_ARCH_X86,UC_MODE_32);mapped=[]
def region(addr,size,prot=4):
 size=(size+4095)&~4095;u.mem_map(addr,size);mapped.append((addr,addr+size,prot))
def put(addr,val):u.mem_write(addr,struct.pack('<I',val&0xffffffff))
def get(addr):return struct.unpack('<I',u.mem_read(addr,4))[0]
region(0x20000000,0x200000);region(0x30000000,0x1000000);region(0x50000000,0x100000,0x20);region(0x60000000,4096,0x20)
clock={'day':27,'tick':1000}
packets=[]
heap=0x30000000
def alloc(data):
 global heap
 a=heap;heap+=((len(data)+15)&~15);u.mem_write(a,data);return a
def wide(s):return alloc(s.encode('utf-16-le')+b'\0\0')
def readw(a):
 b=bytearray()
 for i in range(2000):
  p=bytes(u.mem_read(a+i*2,2))
  if p==b'\0\0':break
  b+=p
 return b.decode('utf-16-le')
def readz(a):
 b=bytearray()
 for i in range(200000):
  p=bytes(u.mem_read(a+i,1))
  if not p[0]:break
  b+=p
 return b.decode()
pe=pefile.PE(str(P/'tests_runtime_font1.dll'));base=pe.OPTIONAL_HEADER.ImageBase
region(base,pe.OPTIONAL_HEADER.SizeOfImage,0x20);u.mem_write(base,pe.get_memory_mapped_image())
exports={x.name.decode():base+x.address for x in pe.DIRECTORY_ENTRY_EXPORT.symbols if x.name}
def exp(name):return exports.get(name) or next(v for k,v in exports.items() if k.startswith(name+'@'))
callbacks={};fake=0x50000000;calls=[]
def stub(name,n,fn):
 global fake
 a=fake;fake+=16;u.mem_write(a,b'\xc2'+struct.pack('<H',n*4));callbacks[a]=(name,n,fn);return a

def intercept(uc,addr,size,data):
 if addr==0x60000000:uc.emu_stop();return
 if addr not in callbacks:return
 name,n,fn=callbacks[addr];sp=uc.reg_read(UC_X86_REG_ESP);args=[get(sp+4+4*i) for i in range(n)]
 result=fn(*args);uc.reg_write(UC_X86_REG_EAX,(result or 0)&0xffffffff)
u.hook_add(UC_HOOK_CODE,intercept,begin=0x50000000,end=0x500fffff)
u.hook_add(UC_HOOK_CODE,intercept,begin=0x60000000,end=0x60000000)
read_stats={'calls':0,'interfere':None}
def memory_read(proc,src,dst,n,got):
 read_stats['calls']+=1
 try:
  u.mem_write(dst,bytes(u.mem_read(src,n)));put(got,n)
  if read_stats['interfere']:read_stats['interfere'](src,n)
  return 1
 except Exception:return 0

def query(addr,out,n):
 for a,b,prot in mapped:
  if a<=addr<b:
   u.mem_write(out,struct.pack('<7I',a,a,prot,b-a,0x1000,prot,0x20000));return 28
 return 0

def multi(cp,flags,src,n,dst,cap):
 n=n if n<0x80000000 else n-0x100000000
 s=readz(src)+'\0' if n==-1 else bytes(u.mem_read(src,n)).decode('utf-8')
 data=s.encode('utf-16-le')
 if len(data)//2>cap:return 0
 u.mem_write(dst,data);return len(data)//2

def to_utf(cp,flags,src,n,dst,cap,a,b):
 n=n if n<0x80000000 else n-0x100000000
 s=readw(src)+'\0' if n==-1 else bytes(u.mem_read(src,n*2)).decode('utf-16-le')
 data=s.encode()
 if len(data)>cap:return 0
 u.mem_write(dst,data);return len(data)

def exchange(p,v):old=get(p);put(p,v);return old
def compare(p,v,c):old=get(p);put(p,v if old==c else old);return old
def local_time(p):u.mem_write(p,struct.pack('<8H',2026,10,2,clock['day'],12,0,0,0))
def wire_send(ws,kind,ptr,n):packets.append(json.loads(bytes(u.mem_read(ptr,n)).decode()));return 0
# Instrument the actual UTF-16 preferences file write/flush/replace path.
import configparser
fs={};handles={};next_handle=[1000];io={'fail_write':False,'fail_move':False,'writes':0,'closes':0,'capture':0}
config_path='C:\\Game\\Mods\\FHDOnlineChat_User.ini'
def ini_values(path):
 c=configparser.ConfigParser(interpolation=None)
 if path in fs:c.read_string(fs[path].decode('utf-16'))
 return c
def ini_string(section,key,default,out,cap,path):
 c=ini_values(readw(path));v=c.get(readw(section),readw(key),fallback=readw(default))[:cap-1];u.mem_write(out,v.encode('utf-16-le')+b'\0\0');return len(v)
def ini_int(section,key,default,path):
 c=ini_values(readw(path))
 try:return c.getint(readw(section),readw(key),fallback=default)
 except ValueError:return default
def create_file(path,access,share,security,mode,attrs,template):
 n=next_handle[0];next_handle[0]+=1;name=readw(path);handles[n]=name
 if mode==3 and name not in fs:return 0xffffffff
 if mode==2 or name not in fs:fs[name]=b''
 return n
def write_file(f,ptr,n,out,over):
 io['writes']+=1
 if io['fail_write']:put(out,0);return 0
 fs[handles[f]]=fs.get(handles[f],b'')+bytes(u.mem_read(ptr,n));put(out,n);return 1
def move_file(src,dst,flags):
 if io['fail_move']:return 0
 assert flags==9;fs[readw(dst)]=fs.pop(readw(src));return 1
def delete_file(path):fs.pop(readw(path),None);return 1
def capture(hwnd):old=io['capture'];io['capture']=hwnd;return old
def release():io['capture']=0;return 1
def close_ws(*args):io['closes']+=1;return 0
save_path='C:\\Game\\Save\\sample.sav'
def read_file(f,ptr,n,out,over):
 data=fs.get(handles[f],b'')[:n];u.mem_write(ptr,data);put(out,len(data));return 1
def find_first(glob,out):
 if save_path not in fs:return 0xffffffff
 data=bytearray(592);struct.pack_into('<I',data,20,10);data[44:44+len('sample.sav'.encode('utf-16-le'))]='sample.sav'.encode('utf-16-le');u.mem_write(out,bytes(data));return 4000
def compare_time(a,b):
 aa=struct.unpack('<Q',u.mem_read(a,8))[0];bb=struct.unpack('<Q',u.mem_read(b,8))[0];return 1 if aa>bb else -1 if aa<bb else 0
def char_type(kind,ptr,n,out):
 c=bytes(u.mem_read(ptr,n*2)).decode('utf-16-le',errors='surrogatepass');typ=0x100 if c and c[0].isalpha() else 4 if c and c[0].isnumeric() else 0;u.mem_write(out,struct.pack('<H',typ));return 1
active_module=[0]
protect_calls=[]
def protect(addr,n,new,old):protect_calls.append((addr,n,new));put(old,4);return 1
known={
 'GetModuleHandleW':(1,lambda name:active_module[0] if not name else 0),'VirtualProtect':(4,protect),
 'ReadFile':(5,read_file),'FindFirstFileW':(2,find_first),'FindNextFileW':(2,lambda h,p:0),'FindClose':(1,lambda h:1),'CompareFileTime':(2,compare_time),'SetFilePointer':(4,lambda *a:0),
 'GetStringTypeW':(4,char_type),
 'GetPrivateProfileStringW':(6,ini_string),'GetPrivateProfileIntW':(4,ini_int),
 'CreateFileW':(7,create_file),'WriteFile':(5,write_file),'CloseHandle':(1,lambda f:1),'FlushFileBuffers':(1,lambda f:1),'MoveFileExW':(3,move_file),'DeleteFileW':(1,delete_file),
 'SetCapture':(1,capture),'ReleaseCapture':(0,release),
 'CallNextHookEx':(4,lambda *x:0),'TranslateMessage':(1,lambda x:1),'GetLocalTime':(1,local_time),'WinHttpWebSocketSend':(4,wire_send),
 'GetCurrentProcess':(0,lambda:0xffffffff),'ReadProcessMemory':(5,memory_read),'VirtualQuery':(3,query),
 'InterlockedExchange':(2,exchange),'InterlockedCompareExchange':(3,compare),
 'MultiByteToWideChar':(6,multi),'WideCharToMultiByte':(8,to_utf),
 'GetClientRect':(2,lambda h,p:(u.mem_write(p,struct.pack('<4i',0,0,1920,1080)) or 1)),
 'GetTickCount':(0,lambda:clock['tick']),'PostMessageW':(4,lambda *x:1),
 'WinHttpWebSocketClose':(4,close_ws),
 'Sleep':(1,lambda x:None),'GetCurrentProcessId':(0,lambda:1),
}
def unknown(name):
 def fail(*x):raise AssertionError('Unexpected API '+name)
 return fail
for dll in pe.DIRECTORY_ENTRY_IMPORT:
 for i in dll.imports:
  name=i.name.decode() if i.name else str(i.ordinal);n,fn=known.get(name,(0,unknown(name)))
  put(i.address,stub(name,n,fn))
def call(name,*args):
 sp=0x201ff000
 u.mem_write(sp,struct.pack('<'+'I'*(1+len(args)),0x60000000,*[v&0xffffffff for v in args]));u.reg_write(UC_X86_REG_ESP,sp)
 u.emu_start(exp(name),0x60000000,count=400000000)
 return u.reg_read(UC_X86_REG_EAX)
checks=[]
def check(label,condition):assert condition,label;checks.append(label);print('PASS',label)
MY='00000000-0000-4000-8000-000000000000';A='11111111-1111-4111-8111-111111111111';B='22222222-2222-4222-8222-222222222222'
def recv(o):call('Test_Receive',alloc(json.dumps(o,ensure_ascii=False).encode()+b'\0'))
def hello():recv({'type':'hello','id':MY,'history':[]})
def presence(names=None):recv({'type':'presence','online':3,'users':[{'id':MY,'name':'Я'},{'id':A,'name':names[0] if names else 'Алекс'},{'id':B,'name':names[1] if names else 'Боб'}]})
def txt():a=call('Test_Text');return bytes(u.mem_read(a,call('Test_Length')*2)).decode('utf-16-le')
def key(m,w=0,l=0):return call('Test_Message',7,m,w,l)
def click(x,y,right=False):return key(0x204 if right else 0x201,0,(y<<16)|x)
def type_text(s):
 key(0x100,13)
 for c in s:key(0x102,ord(c))
def pop_events():
 out=[];ptr=alloc(bytes(1344))
 while call('FHDChat_PollEx',ptr):
  b=bytes(u.mem_read(ptr,1344));out.append({'nick':b[:72].decode('utf-16-le').split('\0')[0],'body':b[72:1096].decode('utf-16-le').split('\0')[0],'peer':b[1096:1168].decode('utf-16-le').split('\0')[0],'id':b[1168:1248].split(b'\0')[0].decode(),'own':struct.unpack_from('<i',b,1248)[0],'channel':struct.unpack_from('<i',b,1252)[0],'event':struct.unpack_from('<i',b,1256)[0],'sender':b[1264:1344].split(b'\0')[0].decode()})
 return out
# Instrument actual draw function for geometry, tab hit testing and visible labels.
render=[];bound=[0]
def obj(n):vt=alloc(bytes(n*4));return alloc(struct.pack('<I',vt)),vt
def slot(vt,i,n,fn):put(vt+4*i,stub('COM'+str(i),n,fn))
tex,tvt=obj(21);pixels=alloc(bytes(512*256*4))
slot(tvt,2,1,lambda x:1);slot(tvt,19,5,lambda t,l,p,r,f:(u.mem_write(p,struct.pack('<II',2048,pixels)) or 0));slot(tvt,20,2,lambda t,l:0)
sb,svt=obj(6)
for i in (2,4,5):slot(svt,i,1,lambda *x:0)
dev,dvt=obj(119)
slot(dvt,48,2,lambda d,p:(u.mem_write(p,struct.pack('<4I2f',0,0,1920,1080,0.,1.)) or 0))
slot(dvt,23,9,lambda d,w,h,l,us,f,po,p,sh:(put(p,tex) or 0));slot(dvt,59,3,lambda d,t,p:(put(p,sb) or 0))
slot(dvt,65,3,lambda d,s,t:bound.__setitem__(0,t) or 0)
for i,n in ((57,3),(67,4),(69,4),(89,2),(92,2),(107,2)):slot(dvt,i,n,lambda *x:0)
def draw(d,kind,n,ptr,stride):render.append((bound[0],bytes(u.mem_read(ptr,n*3*stride))));return 0
slot(dvt,83,5,draw)

# Additional helpers use the actual compiled bridge and overlay code.
def zid(s):return alloc(s.encode()+b'\0')
def choose(id,name):return call('Test_Choose',zid(id),wide(name))
def count(id):return call('Test_ConversationMessages',zid(id))
def unread(id):return call('Test_ConversationUnread',zid(id))
def body(id,row):return readw(call('Test_ConversationText',zid(id),row))
def color(name,id):return call('Test_Color',wide(name),zid(id))
def enter():return key(0x100,13)
def clear():
 for _ in range(call('Test_Length')):key(0x102,8)
def input_text(s):
 if not call('Test_Editing'):enter()
 clear()
 for c in s:key(0x102,ord(c))
def pm(id,name,text,own=False,to=None):
 recv({'type':'private','fromId':MY if own else id,'toId':id if own else MY,'toName':name,'name':'Я' if own else name,'text':text})
def public(id,name,text):recv({'type':'chat','fromId':id,'name':name,'text':text})
def pump():call('Test_Pump')
def frame():call('Test_Draw',dev)
def signed(n):return n if n<0x80000000 else n-0x100000000
def parse(s):
 out=alloc(bytes(80));name=alloc(bytes(72));offset=alloc(bytes(4));r=signed(call('FHDChat_ParsePrivateW',wide(s),out,80,name,36,offset));return r,readz(out),readw(name),get(offset)
call('Test_SessionOverride',1)
call('Test_ConfigPath',wide(config_path))
call('FHDChat_SetNickW',wide('Я'))
check('Online unknown before server presence',call('FHDChat_GetOnline')==0xffffffff)
call('Test_Transport',0);hello();presence();check('Live online count retained',call('FHDChat_GetOnline')==3)
check('At command resolves exact nickname',parse('@Алекс привет')==(1,A,'Алекс',7))
check('Opening quote command resolves nickname',parse('"Боб привет')==(1,B,'Боб',5))
check('Closing quote is optional',parse('"Боб" привет')==(1,B,'Боб',6))
check('Whitespace after recipient removed',parse('@Боб    привет')==(1,B,'Боб',8))
check('Empty command body rejected',parse('@Боб   ')[0]==-2)
check('Nickname prefix does not match another name',parse('@Бобби привет')[0]==0)
check('Self cannot be addressed',parse('@Я привет')[0]==0)
presence(['Боб','Боб']);out=alloc(bytes(80));check('A disconnected exact ID never redirects to a namesake',call('FHDChat_SelectPeerW',wide('Боб'),zid('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),out,80)==0)
presence()
presence(['Ranger','Ranger One']);check('Longest nickname including spaces wins',parse('@Ranger One hello')==(1,B,'Ranger One',12))
check('Quoted spaced nickname resolves',parse('"Ranger One" hello')==(1,B,'Ranger One',13))
presence(['Дубль','Дубль']);check('Duplicate command recipient rejected',parse('@Дубль секрет')[0]==-1)
out=alloc(bytes(80));check('RMB exact ID still resolves duplicate nick',call('FHDChat_SelectPeerW',wide('Дубль'),zid(B),out,80)==1 and readz(out)==B)
# Equal names in real messages get separate viewer-local colors.
public(A,'Дубль','Первый игрок');public(B,'Дубль','Второй игрок');frame()
c1=color('Дубль',A);c2=color('Дубль',B)
check('Equal nicknames have different stable colors',c1!=c2 and c1==color('Дубль',A) and c2==color('Дубль',B))
textcolors=[struct.unpack_from('<I',b,i+16)[0] for texture,b in render[-2:] if texture for i in range(0,len(b),28)]
check('Real renderer uses both nickname colors',c1 in textcolors and c2 in textcolors)
check('All 128 same-name participants get distinct colors',len({color('128 duplicates',f'{i:08x}-0000-4000-8000-000000000000') for i in range(128)})==128)
for i in range(600):color('old connection '+str(i),f'{i+500:08x}-0000-4000-8000-000000000000')
check('Visible nickname colors survive cache reclamation',color('Дубль',A)==c1 and color('Дубль',B)==c2)
check('Default public tab does not mix histories',call('Test_Tab')==0 and call('Test_HistoryCount',0)==2 and call('Test_HistoryCount',1)==0)
click(25,835,True);check('RMB on second duplicate targets its exact ID',call('Test_Tab')==1 and readz(call('Test_Target'))==B)
check('Choosing a peer never activates typing',call('Test_Editing')==0)
input_text('draft B');click(20,790);input_text('public draft');click(150,790)
check('Public and personal drafts are separate',txt()=='draft B')
choose(A,'Дубль');input_text('draft A');choose(B,'Дубль');check('Each correspondent retains separate draft',txt()=='draft B')
pm(A,'Дубль','Only A');pm(B,'Дубль','Only B');pump()
check('Each correspondent has isolated history',count(A)==1 and count(B)==1 and body(A,0)=='Only A' and body(B,0)=='Only B')
def frame_text():
 frame();glyphs=[]
 for texture,b in render[-2:]:
  if not texture:continue
  for off in range(0,len(b),6*28):
   v=struct.unpack_from('<4fI2f',b,off);idx=round(v[6]*256/20)*32+round(v[5]*512/16)
   glyphs.append(chr(idx+32) if idx<95 else chr(0x400+idx-95) if idx<191 else '?')
 return ''.join(glyphs)
check('Inactive conversation gets its own unread badge',unread(A)==1 and unread(B)==0)
choose(A,'Дубль');shown=frame_text();check('Renderer shows selected conversation only','Only A' in shown and 'Only B' not in shown)
choose(B,'Дубль')

pm(A,'Дубль','Only A');pump()
check('Incoming other chat never changes selected recipient',readz(call('Test_Target'))==B and call('Test_ActiveCount')==1)
click(20,815);check('Sidebar click selects first conversation',readz(call('Test_Target'))==B and txt()=='draft B')
click(20,838);check('Sidebar click selects second conversation and clears its badge',readz(call('Test_Target'))==A and unread(A)==0 and txt()=='draft A')
enter();enter();check('Normal private send only targets selected UUID',packets[-1]=={'type':'private','toId':A,'text':'draft A'} and txt()=='')
choose(B,'Дубль');check('Other draft survives sending to first peer',txt()=='draft B')
# Failed prefix commands are never sent as ordinary public messages.
click(20,790);input_text('@Дубль секрет');before=len(packets);enter()
check('Ambiguous prefix retained with no public or private packet',len(packets)==before and txt()=='@Дубль секрет' and call('Test_Editing')==1)
check('Ambiguity explains RMB alternative', 'ПКМ' in readw(call('Test_Notice')))
input_text('@Missing hidden');enter();check('Unknown nick cannot leak command into public chat',len(packets)==before and txt()=='@Missing hidden')
input_text('@Дубль');enter();check('Incomplete ambiguous command stays in edit mode',len(packets)==before and call('Test_Editing')==1)
presence();input_text('@Боб');enter();check('Recipient without body does not send',len(packets)==before and txt()=='@Боб')
input_text('@Боб скрыто');enter();check('At command strips prefix and sends private packet',packets[-1]=={'type':'private','toId':B,'text':'скрыто'} and call('Test_Tab')==1 and readz(call('Test_Target'))==B)
check('Command preserves existing target draft',txt()=='draft B' and call('Test_Editing')==0)
click(20,790);check('Sent private command is removed from public draft',txt()=='')
input_text('"Алекс секрет');enter();check('Quote command sends privately and opens correct conversation',packets[-1]=={'type':'private','toId':A,'text':'секрет'} and readz(call('Test_Target'))==A)
check('Quote command does not restore previously sent draft',txt()=='')
input_text('@Боб private from PM');enter();check('Prefix can switch recipients from inside a personal conversation',packets[-1]=={'type':'private','toId':B,'text':'private from PM'} and txt()=='draft B')
# Incoming/outgoing are routed by peer ID; sender identity is retained for colors.
pm(A,'Алекс','A echo',True);pm(B,'Боб','B next');pump()
check('Outgoing echoes stay inside recipient conversation',body(A,count(A)-1)=='A echo' and body(B,count(B)-1)=='B next')
# Backup transport cannot expose a PM, including a prefix command.
click(20,790);call('Test_Transport',1);input_text('@Боб never public');before=len(packets);enter()
check('Reserve broadcast never carries a PM command',len(packets)==before and txt()=='@Боб never public')
check('No stale online count on reserve transport',call('FHDChat_GetOnline')==0xffffffff)
call('Test_Transport',0);presence();input_text('hello public');enter();check('Ordinary public send still public',packets[-1]=={'type':'chat','text':'hello public'})
# A flood in one conversation cannot erase the other.
old_a=count(A)
for i in range(45):pm(B,'Боб','B flood '+str(i))
pump();check('Thirty-message limit applies to each correspondent independently',count(B)==30 and count(A)==old_a and body(B,29)=='B flood 44')
pm(A,'Алекс','pending personal')
for i in range(150):public(B,'Боб','public '+str(i))
pump();pump();check('Public flood cannot evict pending private traffic',body(A,count(A)-1)=='pending personal' and call('Test_HistoryCount',0)==30)
# A long PM wraps and scrolls instead of disappearing beyond the panel.
choose(A,'Алекс');pm(A,'Алекс','long '*60);pump();check('Long private message wraps into multiple visible rows',call('Test_ActiveRows')>call('Test_ActiveCount'))
# Incoming new players create separate conversations without stealing focus.
C='33333333-3333-4333-8333-333333333333'
pm(C,'Третий','other thread');pump();check('New correspondent creates independent unread conversation',call('Test_ConversationCount')==3 and count(C)==1 and unread(C)==1 and readz(call('Test_Target'))==A)
# Independent sidebar scrolling does not change selected peer.
for i in range(10):pm(f'{i+20:08x}-0000-4000-8000-000000000000','Игрок '+str(i),'hi')
pump();check('More than one page of correspondents retained',call('Test_ConversationCount')==13)
for d in pe.DIRECTORY_ENTRY_IMPORT:
 for imp in d.imports:
  if imp.name==b'ScreenToClient':put(imp.address,stub('ScreenToClient',2,lambda h,p:1))
key(0x20a,((-120)&0xffff)<<16,(850<<16)|20);click(20,960)
check('Sidebar wheel and row click select off-page conversation',readz(call('Test_Target'))=='00000019-0000-4000-8000-000000000000')
# Keyboard ownership preserved while editing commands, even with no selected peer.
call('Test_SetGame',7)
def queue(m,w=0):
 ptr=alloc(struct.pack('<9I',7,m,w,0,0,0,0,0,0));call('Test_Queue',0,1,ptr);return struct.unpack('<4I',u.mem_read(ptr,16))
queue(0x100,13)
check('Inventory key remains blocked during typing',queue(0x100,0x49)==(0,0,0,0))
check('Space remains blocked during typing',queue(0x100,32)==(0,0,0,0))
queue(0x100,27);check('Escape ends typing',call('Test_Editing')==0)
check('Owned inventory key release remains consumed',queue(0x101,0x49)==(0,0,0,0))
clock['day']=28;clock['tick']=40000;call('Test_CheckDay')
check('Date change clears public and all personal conversations',call('Test_ConversationCount')==0 and call('Test_HistoryCount',1)==0 and call('Test_HistoryCount',0)==0)
enter();check('Enter allows a PM command with no recipient selected',call('Test_Editing')==1)
input_text('@Missing retained');click(20,790);click(150,790);check('Unselected PM command draft stays private across tabs',txt()=='@Missing retained')
input_text('@Алекс new day');enter();check('Commands still work after daily reset',packets[-1]=={'type':'private','toId':A,'text':'new day'})
# Verify actual glyph vertex colors, rather than only calling a color helper.
GREEN=0xff69ee8c
def glyph_color_at(x,y):
 for texture,b in render[-2:]:
  if not texture:continue
  for off in range(0,len(b),6*28):
   v=struct.unpack_from('<4fI2f',b,off)
   if round(v[0]+.5)==x and round(v[1]+.5)==y:return v[4]
 raise AssertionError('Missing nickname glyph')
click(20,790)
recv({'type':'hello','id':MY,'history':[]});presence(['Я','Я']);public(A,'Я','foreign first');public(MY,'Я','my public');public(B,'Я','foreign second');frame()
check('Own public nickname is always green',glyph_color_at(10,832)==GREEN)
check('Namesakes remain distinct from self and each other',len({glyph_color_at(10,812),glyph_color_at(10,852),GREEN})==3)
public(MY,'Я','my second public');frame();check('Own public color remains green across repeated messages',glyph_color_at(10,872)==GREEN)
pm(A,'Я','their private');pm(A,'Я','my private',True);pump();choose(A,'Я');frame()
check('Own private nickname is always green',glyph_color_at(138,852)==GREEN)
check('Private namesake has a different color',glyph_color_at(138,832)!=GREEN)
click(20,790)
recv({'type':'hello','id':MY,'history':[{'name':'Я','fromId':A,'text':'not me'},{'name':'Я','fromId':MY,'text':'mine'}]});frame()
check('Own current-ID history nickname is green, namesake is not',glyph_color_at(10,832)==GREEN and glyph_color_at(10,812)!=GREEN)

# Late reader can distinguish equal names in persisted server history too.
history_packet={'type':'hello','id':MY,'history':[{'name':'Same','fromId':A,'text':'one'},{'name':'Same','fromId':B,'text':'two'},{'name':'Я','fromId':B,'text':'not me'}]}
recv(history_packet);events=pop_events();rows=[e for e in events if e['event']==3]
check('History parser preserves sender IDs for equal-name colors',[e['sender'] for e in rows[:2]]==[A,B])
check('Own nickname with another sender ID remains another player',rows[2]['own']==0)
recv(history_packet);pump()
def save_frame_png(path,crop=False):
 from PIL import Image
 canvas=Image.new('RGBA',(1920,1080),(8,12,20,255));atlas=Image.frombytes('RGBA',(512,256),bytes(u.mem_read(pixels,512*256*4)),'raw','BGRA')
 for texture,b in render[-2:]:
  for off in range(0,len(b),6*28):
   a=struct.unpack_from('<4fI2f',b,off);z=struct.unpack_from('<4fI2f',b,off+5*28);x,y=round(a[0]+.5),round(a[1]+.5);w,h=round(z[0]-a[0]),round(z[1]-a[1]);color=((a[4]>>16)&255,(a[4]>>8)&255,a[4]&255,a[4]>>24);layer=Image.new('RGBA',(w,h),color)
   if texture:layer.putalpha(atlas.crop((round(a[5]*512),round(a[6]*256),round(z[5]*512),round(z[6]*256))).resize((w,h)).getchannel('A'))
   canvas.alpha_composite(layer,(x,y))
 if crop:
  x,y,w,h=bounds();canvas=canvas.crop((x,y,x+w,y+h))
 canvas.convert('RGB').save(path)

# Preferences UI, real event dispatch and disk serialization tests.
def bounds():
 p=alloc(bytes(16));call('Test_Bounds',p);return struct.unpack('<4i',u.mem_read(p,16))
def gear():
 x,y,w,h=bounds();click(x+w-20,y+12)
def lock_button():
 x,y,w,h=bounds();click(x+w-46,y+12);frame()
def local_click(dx,dy):
 x,y,w,h=bounds();return click(x+dx,y+dy)
def size_button(i):
 x,y,w,h=bounds();local_click(12+i*((w-32)//4)+10,120);frame()
def transparency(up=True):
 x,y,w,h=bounds();local_click(w-30 if up else w-70,155);frame()
def apply():
 x,y,w,h=bounds();local_click(w-65,h-23);frame()
def cancel():
 x,y,w,h=bounds();local_click(w-190,h-23);frame()
def name_text(text):
 if not call('Test_NameEditing'):enter()
 for _ in range(24):key(0x102,8)
 for c in text:key(0x102,ord(c))
 enter()
def prefs():
 p=alloc(bytes(80));call('FHDChat_LoadPreferences',p);b=bytes(u.mem_read(p,80));return b[:64].decode('utf-16-le').split('\0')[0],*struct.unpack_from('<4i',b,64)
check('Default standard geometry and transparency preserved',bounds()==(0,780,450,270) and call('Test_Opacity')==70)
click(20,790);input_text('draft through settings');gear();frame()
check('Settings gear opens modal without chat typing',call('Test_Settings')==1 and call('Test_Editing')==0)
check('Settings keyboard does not leak into gameplay',key(0x100,32)==1 and key(0x100,0x49)==1)
key(0x102,ord('X'));check('Nickname cannot start typing without Enter',call('Test_NameEditing')==0)
size_button(0);check('Small preset is 400x240',bounds()[2:]==(400,240))
size_button(1);check('Standard preset is 450x270',bounds()[2:]==(450,270))
size_button(2);check('Large preset is 600x360',bounds()[2:]==(600,360))
size_button(3);check('Extra large preset is 750x450',bounds()[2:]==(750,450))
for _ in range(12):transparency(True)
check('Transparency is bounded at ninety percent',call('Test_Opacity')==10)
for _ in range(12):transparency(False)
check('Zero transparency is fully opaque',call('Test_Opacity')==100 and all((struct.unpack_from('<I',b,i+16)[0]>>24)==255 for texture,b in render[-2:] if not texture for i in range(0,len(b),28)))
for _ in range(3):transparency(True)
transparency(True);check('Transparency preview changes background opacity',call('Test_Opacity')==60)
# The real renderer retains full text alpha while reducing background alpha.
text_alphas={struct.unpack_from('<I',b,i+16)[0]>>24 for texture,b in render[-2:] if texture for i in range(0,len(b),28)}
check('Transparency leaves text fully readable',text_alphas=={255})
check('Preview has not written settings to disk',config_path not in fs)
cancel();check('Cancel restores all saved geometry and opacity',call('Test_Settings')==0 and bounds()==(0,780,450,270) and call('Test_Opacity')==70)
check('Opening and cancelling settings preserves chat draft',txt()=='draft through settings')
gear();name_text('Космо Ranger');size_button(2);transparency(True);before_close=io['closes'];apply()
check('Custom Unicode nickname and appearance save together',prefs()==('Космо Ranger',2,60,-1,-1) and call('Test_Settings')==0)
n=alloc(bytes(64));call('FHDChat_GetNickW',n,32);check('Custom nickname becomes the displayed network nickname',readw(n)=='Космо Ranger' and call('Test_AutoNick')==0)
check('Nickname change requests one reconnection',io['closes']==before_close+1)
check('User preferences are UTF16 and replace is complete',fs[config_path].startswith(b'\xff\xfe') and config_path+'.tmp' not in fs)
call('Test_ReloadPreferences');frame();check('Saved appearance survives reloading preferences',bounds()[2:]==(600,360) and call('Test_Opacity')==60)
# Normal chat dragging persists once on release, not during frames/mouse moves.
if call("Test_WindowLocked"):lock_button()
x,y,w,h=bounds();before=io['writes'];click(x+250,y+12);key(0x200,1,((y+82)<<16)|(x+420));frame()
check('Header drag moves chat with mouse capture',bounds()[:2]==(170,min(y+70,1080-h)) and io['capture']==7)
check('Dragging and rendering do not write on every frame',io['writes']==before)
key(0x202,0,((y+82)<<16)|(x+420));check('Release saves position once and releases capture',io['writes']==before+1 and io['capture']==0)
check('Moved position persists to preferences file',prefs()[3:]==bounds()[:2])
call('Test_ReloadPreferences');frame();check('Position restored after reload',bounds()[:2]==prefs()[3:])
# Drag beyond viewport edges clamps instead of losing the panel.
x,y,w,h=bounds();click(x+250,y+12);key(0x200,1,(2000<<16)|3000);key(0x202,0,(2000<<16)|3000);frame()
check('Dragging cannot lose panel beyond the viewport',bounds()[:2]==(1920-w,1080-h))
# Shrinking viewport clamps saved position and largest size to fit.
slot(dvt,48,2,lambda d,p:(u.mem_write(p,struct.pack('<4I2f',0,0,640,480,0.,1.)) or 0));frame();x,y,w,h=bounds()
check('Resolution change keeps complete panel reachable',x>=0 and y>=0 and x+w<=640 and y+h<=480)
slot(dvt,48,2,lambda d,p:(u.mem_write(p,struct.pack('<4I2f',0,0,1920,1080,0.,1.)) or 0));frame()
# Failed saves leave existing complete INI and settings modal intact.
gear();name_text('Bad@Nick');previous=fs[config_path];apply()
check('Invalid nick rejected without changing persisted settings',call('Test_Settings')==1 and fs[config_path]==previous and bool(readw(call('Test_SettingsNotice'))))
name_text('★');apply();check('Unsupported Unicode symbols rejected before reconnect',call('Test_Settings')==1 and fs[config_path]==previous)
name_text('Новый');io['fail_write']=True;apply();io['fail_write']=False
check('Disk write failure keeps previous complete settings',call('Test_Settings')==1 and fs[config_path]==previous and config_path+'.tmp' not in fs)
io['fail_move']=True;apply();io['fail_move']=False
check('Replace failure keeps previous complete settings',call('Test_Settings')==1 and fs[config_path]==previous and config_path+'.tmp' not in fs)
cancel();gear();local_click(30,bounds()[3]-23);frame()
fs[save_path]=('\0'.join(['RSG','v2','date','game','x','Чужой свежий сейв','end'])+'\0').encode('utf-16-le');before_close=io['closes'];apply()
n=alloc(bytes(64));call('FHDChat_GetNickW',n,32);check('Automatic name waits for active pilot and ignores newest save file',readw(n)=='Космо Ranger' and io['closes']==before_close)
check('Reset restores automatic nickname, standard size and position',prefs()==('',1,70,-1,-1) and bounds()==(0,780,450,270) and call('Test_AutoNick')==1)
# Drag capture is also released on loss of focus.
x,y,w,h=bounds();click(x+250,y+12);key(0x8);check('Focus loss releases drag capture',io['capture']==0)
# Existing keyboard suppression still applies while editing the nickname.
gear();enter();check('Enter enables nickname editing',call('Test_NameEditing')==1)
check('Inventory and space consumed by real queue in nickname field',queue(0x100,0x49)==(0,0,0,0) and queue(0x100,32)==(0,0,0,0))
key(0x100,27);check('First Escape stops nickname editing',call('Test_Settings')==1 and call('Test_NameEditing')==0)
key(0x100,27);check('Second Escape cancels settings',call('Test_Settings')==0)
RENAMED='44444444-4444-4444-8444-444444444444'
recv({'type':'hello','id':RENAMED,'history':[{'name':'Я','fromId':MY,'text':'mine before rename'},{'name':'Я','fromId':A,'text':'same name, other person'}]});rows=pop_events();check('Own history stays own after nickname reconnect',[e['own'] for e in rows if e['event']==3]==[1,0])
# Malformed saved integers safely fall back to defaults.
fs[config_path]=('[Chat]\r\nNickname=Bad@Nick\r\nSize=90\r\nOpacity=0\r\nX=999999\r\nY=-50\r\n').encode('utf-16')
call('Test_ReloadPreferences');frame();check('Corrupt preferences fall back to safe reachable defaults',prefs()==('',1,70,-1,-1) and bounds()==(0,780,450,270))
gear()
for preset in range(4):
 size_button(preset);x,y,w,h=bounds()
 inside_vertices=all(x-.6<=struct.unpack_from('<f',b,i)[0]<=x+w+.1 and y-.6<=struct.unpack_from('<f',b,i+4)[0]<=y+h+.1 for texture,b in render[-2:] for i in range(0,len(b),28))
 check('Settings vertices fit panel for preset '+str(preset),inside_vertices)
 if preset in (0,1):save_frame_png(Q/('settings021_'+str(preset)+'.png'),True)
if call('Test_WindowLocked'):lock_button()
before=io['writes'];saved_bounds=bounds();x,y,w,h=saved_bounds;click(x+80,y+12);key(0x200,1,(300<<16)|400);key(0x202,0,(300<<16)|400);frame()
check('Settings drag remains an unsaved preview',io['writes']==before and bounds()[:2]!=saved_bounds[:2])
cancel();check('Cancelling settings drag restores prior position',bounds()==(0,780,450,270))
check('Double click on chat never reaches game',key(0x203,0,(800<<16)|40)==1)
gear()
# Non-round externally edited opacity still cannot overshoot either boundary.
cancel();fs[config_path]=('[Chat]\r\nSize=1\r\nOpacity=95\r\n').encode('utf-16');call('Test_ReloadPreferences');frame();gear();transparency(False);check('Non-round loaded opacity clamps at one hundred',call('Test_Opacity')==100)
for _ in range(12):transparency(True)
check('Non-round opacity clamps at ten',call('Test_Opacity')==10)
cancel();fs.pop(config_path,None);call('Test_ReloadPreferences');frame()
# Default visuals remain ready for the review scene below.

# Gear and persistent lock state: normal chat and the settings modal.
check('Window is locked by default including old INI without Locked key',call('Test_WindowLocked')==1)
def drag_attempt():
 x,y,w,h=bounds();before=bounds();click(x+250,y+12);key(0x200,1,((y-120)<<16)|(x+350));key(0x202,0,((y-120)<<16)|(x+350));frame();return before,bounds()
before_writes=io['writes'];before,after=drag_attempt()
check('Locked chat cannot move or capture mouse',before==after and io['capture']==0 and io['writes']==before_writes)
gear();frame();check('Gear opens settings while window locked',call('Test_Settings')==1)
before,after=drag_attempt();check('Lock also blocks dragging settings header',before==after and io['capture']==0)
# Toggle inside modal: saves lock only, preserving unapplied appearance preview.
size_button(2);before_close=io['closes'];before_reads=read_stats['calls'];lock_button()
check('Lock button unlocks immediately without reconnect or pilot read',call('Test_WindowLocked')==0 and io['closes']==before_close and read_stats['calls']==before_reads)
check('Lock change persists without applying size preview',ini_values(config_path).getint('Chat','Locked')==0 and ini_values(config_path).getint('Chat','Size')==1)
cancel();check('Cancel preserves explicit lock toggle and cancels only preview',call('Test_WindowLocked')==0 and bounds()[2:]==(450,270))
call('Test_ReloadPreferences');frame();check('Unlocked state survives reload',call('Test_WindowLocked')==0)
before,after=drag_attempt();check('Unlocked window moves normally',before!=after and io['capture']==0)
lock_button();before,after=drag_attempt();check('Relocking blocks accidental movement',call('Test_WindowLocked')==1 and before==after)
call('Test_ReloadPreferences');frame();check('Locked state survives reload',call('Test_WindowLocked')==1)
# Chat draft/editing remain intact when either icon is used appropriately.
click(bounds()[0]+20,bounds()[1]+12);input_text('черновик при фиксации');draft=txt();lock_button()
check('Lock toggle preserves typed chat draft and editing state',txt()==draft and call('Test_Editing')==1)
key(0x100,27);frame();save_frame_png(Q/'unlocked021.png',True)
lock_button();frame();save_frame_png(Q/'locked021.png',True)
# Saving ordinary settings must not forget the lock preference.
gear();transparency(True);apply();call('Test_ReloadPreferences');frame();check('Appearance save preserves lock flag',call('Test_WindowLocked')==1 and ini_values(config_path).getint('Chat','Locked')==1)
# A disk error still applies the requested safety lock for this session.
lock_button();previous=fs[config_path];io['fail_write']=True;lock_button();io['fail_write']=False
check('Lock remains effective in memory when persistence fails',call('Test_WindowLocked')==1 and fs[config_path]==previous)
before,after=drag_attempt();check('Failed lock persistence cannot allow accidental drag',before==after and io['capture']==0)
lock_button();lock_button();check('Lock state can be saved on later retry',ini_values(config_path).getint('Chat','Locked')==1)
# Settings can close by the same gear without changing lock state.
gear();frame();gear();frame();check('Same gear toggles settings closed',call('Test_Settings')==0 and call('Test_WindowLocked')==1)
# Missing/invalid values use the safe locked default while other preferences survive.
fs[config_path]=('[Chat]\r\nSize=2\r\nOpacity=60\r\nX=100\r\nY=200\r\nLocked=88\r\n').encode('utf-16');call('Test_ReloadPreferences');frame()
check('Invalid lock key defaults to locked preserving other settings',call('Test_WindowLocked')==1 and bounds()==(100,200,600,360) and call('Test_Opacity')==60)
fs.pop(config_path,None);call('Test_ReloadPreferences');frame()

# Visibility and input ownership in/out of a campaign.
check('Active campaign renders chat normally',call('Test_SessionActive')==1)
click(bounds()[0]+20,bounds()[1]+12);input_text('черновик перед меню');before_txt=txt()
call('Test_SessionOverride',0);before_draw=len(render);frame()
check('No chat geometry is drawn in main menu',len(render)==before_draw)
check('Returning to menu ends typing and retains draft',call('Test_Editing')==0 and txt()==before_txt)
before_open=call('Test_Open');x,y,w,h=bounds()
check('Menu Enter Space inventory and F12 pass to game',all(key(0x100,k)==0 for k in (13,32,0x49,0x7b)) and call('Test_Open')==before_open)
check('Invisible menu chat does not intercept clicks or mouse move',click(x+w-20,y+12)==0 and click(x+30,y+40,True)==0 and key(0x200,0,((y+12)<<16)|(x+30))==0)
call('Test_SessionOverride',1);before_draw=len(render);frame();check('Loading a campaign restores chat render with same draft',len(render)==before_draw+2 and txt()==before_txt)
gear();size_button(2);call('Test_SessionOverride',0);frame();check('Leaving game cancels settings preview',call('Test_Settings')==0 and call('Test_NameEditing')==0)
call('Test_SessionOverride',1);frame();check('Saved geometry and lock survive menu round trip',bounds()[2:]==(450,270) and call('Test_WindowLocked')==1)
# F12 remains user-controlled inside game, and does not toggle while in menu.
key(0x100,0x7b);check('F12 hides inside active game',call('Test_Open')==0)
call('Test_SessionOverride',0);key(0x100,0x7b);call('Test_SessionOverride',1);frame();check('Menu does not change manual F12 visibility choice',call('Test_Open')==0)
key(0x100,0x7b);frame()
# Optional unchanged real-EXE visibility checks.
if (P/'upload/Rangers.exe').exists() and (P/'upload/Rangers(1).exe').exists():
 # Real attached PE images: startup nil player, loaded pilot, campaign destruction.
 import pefile
 if not any(a<=0x400000<b for a,b,_ in mapped):region(0x400000,0x4d1000,0x20)
 for index,(name,slot,vmt) in enumerate([('Rangers.exe',0x47c19c,0x38be5c),('Rangers(1).exe',0x4100fc,0x347118)]):
  pegame=pefile.PE(str(P/'upload'/name));u.mem_write(0x400000,bytes(0x4d1000));u.mem_write(0x400000,pegame.get_memory_mapped_image());active_module[0]=0x400000;call('Test_SessionOverride',0xffffffff)
  check(name+' startup menu detected from actual game slot',call('Test_SupportedExe')==1 and call('Test_SessionActive')==0)
  before=len(render);frame();check(name+' startup menu has no chat draw',len(render)==before)
  actor=alloc(struct.pack('<3I',0x400000+vmt,55,0)+bytes(0xdf0-12));put(0x400000+slot,actor^0xb1cd15d3)
  check(name+' live pilot enables chat independent of nickname',call('Test_SessionActive')==1)
  before=len(render);frame();check(name+' in-game chat draws normally',len(render)==before+2)
  before_reads=read_stats['calls'];call('Test_SessionActive');call('Test_SessionActive');check(name+' unchanged session does not repeatedly read heap memory',read_stats['calls']==before_reads)
  put(0x400000+slot,0xb1cd15d3);before=len(render);frame();check(name+' return-to-menu nil player immediately hides chat',call('Test_SessionActive')==0 and len(render)==before)
  check(name+' menu keyboard stays native',key(0x100,13)==0 and key(0x100,0x7b)==0)
  bad=alloc(struct.pack('<I',0x12345678));put(0x400000+slot,bad^0xb1cd15d3);check(name+' invalid player object cannot show chat',call('Test_SessionActive')==0)
  put(0x400000+slot,0x70000000^0xb1cd15d3);check(name+' invalid player address is handled safely',call('Test_SessionActive')==0)
call('Test_SessionOverride',1);frame()

# Daily primary room reset, queue isolation and fallback calendar.
call('Test_Transport',0);hello();presence();pump();clock['day']=28;clock['tick']+=40000
recv({'type':'hello','id':MY,'day':'20261029','history':[{'name':'Алекс','fromId':A,'text':'today history','day':'20261029'},{'name':'Алекс','fromId':A,'text':'yesterday history','day':'20261028'}]});pump()
check('Hello history imports only current calendar day',call('Test_HistoryCount',0)==1)
pm(A,'Алекс','private today');public(B,'Боб','public today');pump();check('Today public and private messages both visible',call('Test_HistoryCount',0)==2 and call('Test_HistoryCount',1)==1)
before_nick=alloc(bytes(64));call('FHDChat_GetNickW',before_nick,32);before_nick=readw(before_nick);before_bounds=bounds();before_lock=call('Test_WindowLocked')
# Queue old events, then reset, then today's new message; old queue must not return.
public(A,'Алекс','queued yesterday public');pm(A,'Алекс','queued yesterday private')
recv({'type':'reset','day':'20261030'});recv({'type':'chat','day':'20261030','fromId':B,'name':'Боб','text':'new day only'});pump()
check('Reset clears every old conversation and skips stale queued events',call('Test_HistoryCount',0)==1 and call('Test_HistoryCount',1)==0 and call('Test_ConversationCount')==0)
recv({'type':'reset','day':'20261030'});pump();check('Duplicate midnight reset does not erase new-day messages',call('Test_HistoryCount',0)==1)
recv({'type':'hello','id':MY,'day':'20261029','history':[{'name':'Алекс','fromId':A,'text':'stale reconnect','day':'20261029'}]});pump();check('Late previous-day hello cannot restore or clear current history',call('Test_HistoryCount',0)==1)
recv({'type':'chat','day':'20261029','name':'Алекс','fromId':A,'text':'late yesterday'});pump();check('Late previous-day live message is dropped',call('Test_HistoryCount',0)==1)
out=alloc(bytes(64));call('FHDChat_GetNickW',out,32);check('Midnight leaves nickname geometry and fixation unchanged',readw(out)==before_nick and bounds()==before_bounds and call('Test_WindowLocked')==before_lock)
clock['day']=27;clock['tick']+=40000;call('Test_CheckDay');check('Primary room date is authoritative over a different local clock',call('FHDChat_PrivateDay')==20261030 and call('Test_HistoryCount',0)==1)
# A newer day on an ordinary message also recovers a delayed/missed reset signal.
recv({'type':'private','day':'20261031','fromId':A,'toId':MY,'name':'Алекс','text':'new day recovered'});pump();check('Day marker on live traffic recovers missed midnight event',call('Test_HistoryCount',0)==0 and call('Test_HistoryCount',1)==1)
# Main-menu hidden chat still receives and clears history.
call('Test_SessionOverride',0);recv({'type':'reset','day':'20261101'});frame();check('Daily cleanup works while chat is hidden in main menu',call('Test_HistoryCount',0)==0 and call('Test_HistoryCount',1)==0)
call('Test_SessionOverride',1)
# A full previous-day queue must not repaint old messages before its reset marker.
for i in range(90):public(A,'Алекс','queued old public '+str(i));pm(B,'Боб','queued old private '+str(i))
recv({'type':'reset','day':'20261102'});pump();check('Full old-day queues never repaint history after midnight',call('Test_HistoryCount',0)==0 and call('Test_HistoryCount',1)==0)
pump()
# Reserve public transport uses the local calendar, never trusts a public reset packet.
call('Test_Transport',1);clock['day']=28;clock['tick']+=40000;call('Test_CheckDay');public(B,'Боб','reserve today');pump();before_count=call('Test_HistoryCount',0)
recv({'type':'reset','day':'20991231'});pump();check('Public reserve cannot spoof primary room reset date',call('FHDChat_PrivateDay')==20261028 and call('Test_HistoryCount',0)==before_count)
clock['day']=29;clock['tick']+=40000;call('Test_CheckDay');check('Reserve chat is also cleared on its real calendar day change',call('Test_HistoryCount',0)==0)
call('Test_Transport',0);hello();presence()

# Notification preference: real settings UI + persistence + incoming event path.
def notifications_button(value):
 x,y,w,h=bounds();local_click(w-46 if value else w-114,190);frame()
def visible(value):
 if call('Test_Open')!=int(value):key(0x100,0x7b)
 frame()
def notification_setting(value):
 visible(True)
 if not call('Test_Settings'):gear()
 notifications_button(value);apply()
fs.pop(config_path,None);call('Test_ReloadPreferences');frame();hello();presence();pump()
check('Notifications default OFF for missing user INI',call('Test_Notifications')==0)
visible(False);public(A,'Алекс','silent public by default');pm(B,'Боб','silent private by default');pump()
check('Default OFF keeps public and private incoming chat hidden',call('Test_Open')==0)
visible(True);gear();notifications_button(True)
check('ON is only a pending setting until Apply',call('Test_PendingNotifications')==1 and call('Test_Notifications')==0 and config_path not in fs)
cancel();check('Cancel discards pending notification change',call('Test_Notifications')==0)
gear();notifications_button(True);before_bounds=bounds();apply()
check('Apply saves ON in the existing user INI without changing geometry',call('Test_Notifications')==1 and ini_values(config_path).getint('Chat','Notifications')==1 and bounds()==before_bounds)
call('Test_ReloadPreferences');frame();check('Notification ON survives preferences reload',call('Test_Notifications')==1)
visible(False);public(MY,'Я','own public echo');pm(A,'Алекс','own private echo',True);pump()
check('Own public and private echoes never auto-open',call('Test_Open')==0)
recv({'type':'error','message':'service notice'});presence();pump()
check('Service errors and presence never auto-open',call('Test_Open')==0)
recv({'type':'hello','id':MY,'history':[{'name':'Алекс','fromId':A,'text':'replayed past message'}]});pump()
check('Replayed reconnect history never auto-opens',call('Test_Open')==0 and call('Test_HistoryCount',0)==1)
# Daily reset does not itself count as a notification.
recv({'type':'reset','day':'20261030'});pump()
check('Daily reset does not open a hidden panel',call('Test_Open')==0)
visible(True);click(bounds()[0]+20,bounds()[1]+12);input_text('draft preserved on notification');key(0x100,27)
draft=txt();tab=call('Test_Tab');visible(False);public(A,'Алекс','a new public message');pump()
check('New foreign public message opens hidden chat and preserves selected tab and draft',call('Test_Open')==1 and call('Test_Tab')==tab and txt()==draft)
check('Auto-open does not start typing or block inventory and Space',call('Test_Editing')==0 and key(0x100,0x49)==0 and key(0x100,32)==0)
visible(False);pm(B,'Боб','a new private message');pump()
check('New foreign PM opens hidden chat and retains the message',call('Test_Open')==1 and count(B)>0)
notification_setting(False);visible(False);public(A,'Алекс','off public');pm(A,'Алекс','off private');pump()
check('Applied OFF suppresses both public and private auto-open',call('Test_Notifications')==0 and call('Test_Open')==0)
visible(True);gear();notifications_button(True);previous=fs[config_path];io['fail_write']=True;apply();io['fail_write']=False
check('Failed notification write keeps old file and active OFF value',call('Test_Settings')==1 and call('Test_Notifications')==0 and fs[config_path]==previous)
io['fail_move']=True;apply();io['fail_move']=False
check('Failed atomic replace also rolls notification setting back',call('Test_Settings')==1 and call('Test_Notifications')==0 and fs[config_path]==previous)
apply();check('Notification Apply can be retried after disk failure',call('Test_Notifications')==1 and ini_values(config_path).getint('Chat','Notifications')==1)
gear();notifications_button(False);lock_button()
check('Independent lock toggle preserves applied ON rather than pending OFF',ini_values(config_path).getint('Chat','Notifications')==1 and call('Test_Notifications')==1 and call('Test_PendingNotifications')==0)
cancel();gear();local_click(30,bounds()[3]-23);frame()
check('Reset prepares notification OFF without immediately applying it',call('Test_PendingNotifications')==0 and call('Test_Notifications')==1)
cancel();check('Cancel of Reset leaves notifications ON',call('Test_Notifications')==1)
# No expansion or deferred expansion when messages arrive in main menu.
visible(False);call('Test_SessionOverride',0);before=len(render);public(A,'Алекс','menu public');pm(A,'Алекс','menu private');frame()
check('Enabled notifications never open or render chat in main menu',call('Test_Open')==0 and len(render)==before)
call('Test_SessionOverride',1);frame();check('Returning to game does not replay menu notifications',call('Test_Open')==0)
# An auto-open must not restore a hidden modal that steals gameplay input.
visible(True);gear();visible(False);public(A,'Алекс','close hidden settings on notification');pump()
check('Auto-open returns to chat rather than a hidden modal or text editor',call('Test_Open')==1 and call('Test_Settings')==0 and call('Test_Editing')==0)
notification_setting(False);before=ini_values(config_path);call('Test_ReloadPreferences');frame()
check('Explicit OFF survives reload alongside the lock flag',call('Test_Notifications')==0 and ini_values(config_path).getint('Chat','Locked')==before.getint('Chat','Locked'))
fs[config_path]=('[Chat]\r\nSize=1\r\nOpacity=70\r\nLocked=1\r\n').encode('utf-16');call('Test_ReloadPreferences');frame()
check('Older INI without Notifications migrates to OFF',call('Test_Notifications')==0)
fs[config_path]=('[Chat]\r\nNotifications=88\r\nSize=1\r\nOpacity=70\r\nLocked=1\r\n').encode('utf-16');call('Test_ReloadPreferences');frame()
check('Invalid notification value falls back to OFF',call('Test_Notifications')==0)
# Replayed rows remain available through the legacy public poll export.
hello();pump();recv({'type':'hello','id':MY,'history':[{'name':'Алекс','fromId':A,'text':'legacy replay still available'}]})
out_n=alloc(bytes(72));out_t=alloc(bytes(1024));out_own=alloc(bytes(4))
check('Legacy public PollW still returns replayed history',call('FHDChat_PollW',out_n,36,out_t,512,out_own)==1 and readw(out_t)=='legacy replay still available')
notification_setting(True);visible(False);call('Test_Transport',1)
recv({'type':'broadcast','name':'Боб','fromId':B,'text':'reserve live message'});pump()
check('Enabled notifications also open for live reserve public messages',call('Test_Open')==1)
call('Test_Transport',0);hello();presence();pump();notification_setting(False)
# Notification controls fit all four sizes and use real renderer vertices.
gear()
for preset in range(4):
 size_button(preset);notifications_button(True);x,y,w,h=bounds()
 inside_vertices=all(x-.6<=struct.unpack_from('<f',b,i)[0]<=x+w and y-.6<=struct.unpack_from('<f',b,i+4)[0]<=y+h for texture,b in render[-2:] for i in range(0,len(b),28))
 check('Notification settings render within panel for preset '+str(preset),inside_vertices)
 check('Notification controls contain distinct ON and OFF labels for preset '+str(preset),all(word in frame_text() for word in ['Уведомления','Выкл','Вкл']))
 if preset in (0,1):save_frame_png(Q/('notifications021_'+str(preset)+'.png'),True)
cancel();notification_setting(False);visible(True)

# Render a compact review scene with two equal-name correspondents.
presence(['Ranger','Ranger']);pm(A,'Ranger','Привет! Это наш личный чат.');pm(B,'Ranger','Другой Ranger пишет отдельно.');pm(A,'Ranger','Да, сообщения второго игрока сюда не попадают.');pump();choose(A,'Ranger');frame()
from PIL import Image
canvas=Image.new('RGBA',(1920,1080),(8,12,20,255));atlas=Image.frombytes('RGBA',(512,256),bytes(u.mem_read(pixels,512*256*4)),'raw','BGRA')
# Only latest frame's two draw batches.
for t,b in render[-2:]:
 for off in range(0,len(b),6*28):
  a=struct.unpack_from('<4fI2f',b,off);z=struct.unpack_from('<4fI2f',b,off+5*28);x,y=round(a[0]+.5),round(a[1]+.5);w,h=round(z[0]-a[0]),round(z[1]-a[1]);color=((a[4]>>16)&255,(a[4]>>8)&255,a[4]&255,a[4]>>24);layer=Image.new('RGBA',(w,h),color)
  if t:layer.putalpha(atlas.crop((round(a[5]*512),round(a[6]*256),round(z[5]*512),round(z[6]*256))).resize((w,h)).getchannel('A'))
  canvas.alpha_composite(layer,(x,y))
canvas.convert('RGB').save(Q/'panel021.png')
# Optional: unchanged 0.17 compatibility/pilot fixtures, pass both EXE paths.
if len(sys.argv)>2:
 # Map the actual supplied EXEs and run their verified render instructions.
 # This executes our compiled detector/hooks, not a Python copy of the matcher.
 import hashlib
 exe_paths=[Path(sys.argv[1]) if len(sys.argv)>1 else P/'upload/Rangers.exe',Path(sys.argv[2]) if len(sys.argv)>2 else P/'upload/Rangers(1).exe']
 profiles=[('83300344af802bc51e64389c58f047e5afdf195c133048098be3881fae29ed98',0x47a798,[0xc530d,0xc5402,0xc560d]),('e43a4b15503c705eebe2d8ce5778c2a2fb090db515a3fd86d319e5c5aa692ebf',0x41302c,[0x3caf19,0x3cb00e,0x3cb1ef])]
 if not any(a<=0x400000<b for a,b,_ in mapped):region(0x400000,0x4d1000,0x20);region(0x1000000,0x4d1000,0x20)
 compatibility=[]
 def invoke(address,*args):
  sp=0x201ff000;u.mem_write(sp,struct.pack('<'+'I'*(1+len(args)),0x60000000,*args));u.reg_write(UC_X86_REG_ESP,sp);u.emu_start(address,0x60000000,count=10000000);return u.reg_read(UC_X86_REG_EAX)
 def load_exe(path,loadbase):
  pegame=pefile.PE(str(path))
  if loadbase!=pegame.OPTIONAL_HEADER.ImageBase:pegame.relocate_image(loadbase)
  u.mem_write(loadbase,bytes(0x4d1000));u.mem_write(loadbase,pegame.get_memory_mapped_image());active_module[0]=loadbase;return pegame
 player_profiles=[(0x47c19c,0x38be5c,0x38c07c,0x38bf52),(0x4100fc,0x347118,0x347300,0x34720e)]
 KEY=0xb1cd15d3
 
 def pilot_fixture(base,index,name):
  slot,vmt,getter,classname=player_profiles[index]
  raw=name.encode('utf-16-le');bstr=alloc(struct.pack('<I',len(raw))+raw+b'\0\0')+4
  actor=alloc(struct.pack('<3I',base+vmt,123,bstr)+bytes(0xdf0-12));put(base+slot,actor^KEY);return actor,bstr
 
 def pilot_name():
  out=alloc(bytes(64));result=call('Test_ReadPilot',out,32);return (result if result<0x80000000 else result-0x100000000),readw(out)
 def current_nick():
  out=alloc(bytes(64));call('FHDChat_GetNickW',out,32);return readw(out)
 def auto_refresh():clock['tick']+=1000;return call('Test_RefreshPilot',0)
 def manual_preferences(name):
  raw=name.encode('utf-16-le');ptr=alloc(raw+bytes(64-len(raw))+struct.pack('<4i',1,70,-1,-1));return call('FHDChat_SavePreferences',ptr)
 for index,path in enumerate(exe_paths):
  expected,rva,sites=profiles[index];assert hashlib.sha256(path.read_bytes()).hexdigest()==expected,'Wrong EXE fixture: '+str(path)
  label='profile '+('A' if index==0 else 'B')
  for loadbase in (0x400000,0x1000000):
   pegame=load_exe(path,loadbase);tag=label+(' relocated' if loadbase!=0x400000 else ' original base')
   before=hashlib.sha256(bytes(u.mem_read(loadbase,pegame.OPTIONAL_HEADER.SizeOfImage))).hexdigest()
   check(tag+' accepted by compiled detector',call('Test_SupportedExe')==1 and call('Test_Profile')==index+1 and call('Test_DeviceRva')==rva)
   check(tag+' does not patch game image while detecting',hashlib.sha256(bytes(u.mem_read(loadbase,pegame.OPTIONAL_HEADER.SizeOfImage))).hexdigest()==before)
   check(tag+' waits for uncreated game device',call('Test_RealDevice')==0 and call('Test_HookRealDevice')==0)
   slot,vmt,getter,classname=player_profiles[index];check(tag+' active-pilot signatures verified',call('Test_PilotReady')==1)
   check(tag+' no active game pilot is handled safely',pilot_name()==(0,''))
   actor,bstr=pilot_fixture(loadbase,index,'Старый сейв');check(tag+' reads loaded pilot from verified TPlayer',pilot_name()==(1,'Старый сейв'))
   # Compare against the native game's own XOR getter, without invoking it in production.
   getter_start=getter-4 if index==0 else getter
   check(tag+' agrees with actual game GetPlayer routine',invoke(loadbase+getter_start)==actor)
   manual_preferences('Ручной');before=read_stats['calls'];before_close=io['closes'];auto_refresh();check(tag+' manual override avoids memory reads',current_nick()=='Ручной' and read_stats['calls']==before and io['closes']==before_close)
   manual_preferences('');auto_refresh();check(tag+' automatic nickname uses loaded save rather than disk date',current_nick()=='Старый сейв')
   first_close=io['closes'];auto_refresh();auto_refresh();check(tag+' unchanged pilot never reconnects repeatedly',io['closes']==first_close)
   # Complete the previous reconnect: the synthetic worker has no reconnect thread.
   call('Test_HeartbeatStart',0)
   # New game needs no file on disk. Two equal snapshots replace the identity.
   next_actor,next_bstr=pilot_fixture(loadbase,index,'Новый пилот');before_close=io['closes'];auto_refresh();check(tag+' waits for stable new-game identity',current_nick()=='Старый сейв' and io['closes']==before_close)
   auto_refresh();check(tag+' new unsaved character becomes nickname once',current_nick()=='Новый пилот' and io['closes']==before_close+1)
   before=read_stats['calls'];call('Test_RefreshPilot',0);check(tag+' polling is limited to once per second',read_stats['calls']==before)
   # Menu/destruction gap must not adopt a random pointer or change the nickname.
   put(loadbase+slot,KEY);auto_refresh();check(tag+' menu with nil player preserves current chat identity',current_nick()=='Новый пилот' and pilot_name()==(0,''))
   # Returning to an older save switches to its pilot even if another file is newer.
   put(loadbase+slot,actor^KEY);auto_refresh();auto_refresh();check(tag+' loading old save switches back to that pilot',current_nick()=='Старый сейв')
   old_vmt=get(actor);put(actor,loadbase+vmt+4);check(tag+' rejects wrong object class',pilot_name()==(0,''));put(actor,old_vmt)
   put(actor+8,0x70000000);check(tag+' inaccessible name pointer never crashes',pilot_name()==(0,''));put(actor+8,bstr)
   size=get(bstr-4);put(bstr-4,0xffffffff);check(tag+' oversized string length rejected',pilot_name()==(0,''));put(bstr-4,3);check(tag+' odd byte length rejected',pilot_name()==(0,''));put(bstr-4,size)
   tail=bytes(u.mem_read(bstr+size,2));u.mem_write(bstr+size,b'X\0');check(tag+' missing UTF16 terminator rejected',pilot_name()==(0,''));u.mem_write(bstr+size,tail)
   def interfere(src,n):
    if src==bstr:put(loadbase+slot,next_actor^KEY)
   read_stats['interfere']=interfere;check(tag+' pilot changing during read is discarded',pilot_name()==(0,''));read_stats['interfere']=None;put(loadbase+slot,actor^KEY)
   # Confirm only a couple of bounded reads, not a directory scan or image search.
   before=read_stats['calls'];pilot_name();check(tag+' name snapshot uses bounded memory reads',read_stats['calls']-before<=8)
   put(loadbase+slot,KEY)
 
   # Clone the D3D mock vtable and attach only the instance in this EXE's global.
   vt=alloc(bytes(u.mem_read(dvt,119*4)));game_dev=alloc(struct.pack('<I',vt));methods=[]
   old_end=stub('RealEndScene',1,lambda d:(methods.append(('end',d)) or 0x77));old_present=stub('RealPresent',5,lambda d,*a:(methods.append(('present',d,*a)) or 0x88));put(vt+42*4,old_end);put(vt+17*4,old_present)
   put(loadbase+rva,game_dev)
   check(tag+' selects correct device global',call('Test_RealDevice')==game_dev)
   check(tag+' installs actual device vtable hooks',call('Test_HookRealDevice')==1 and get(vt+42*4)!=old_end and get(vt+17*4)!=old_present)
   for site in sites:
    before_draw=len(render);before_methods=len(methods);sp=0x201ff000;u.reg_write(UC_X86_REG_ESP,sp)
    u.emu_start(loadbase+site,loadbase+site+33,count=10000000)
    check(tag+' real render pair '+hex(site)+' preserves calls and draws chat',u.reg_read(UC_X86_REG_ESP)==sp and u.reg_read(UC_X86_REG_EAX)==0x88 and methods[before_methods:]==[('end',game_dev),('present',game_dev,0,0,0,0)] and len(render)==before_draw+2)
   compatibility.append({'profile':index+1,'file':path.name,'sha256':expected,'load_base':hex(loadbase),'device_rva':hex(rva),'status':'PASS detector + actual EXE render instructions + compiled hooks with instrumented D3D'})
  # Unknown or partially modified builds must not reuse a previous device slot.
  pegame=load_exe(path,0x400000);nt=pegame.DOS_HEADER.e_lfanew
  mutations=[('timestamp',nt+8,b'\0'*4),('image size',nt+24+56,b'\0'*4),('machine',nt+4,b'\x64\x86'),('optional magic',nt+24,b'\x0b\x02'),('EndScene high displacement',sites[0]+11,b'\x01'),('Present global',sites[1]+23,b'\x01'),('third render path',sites[2]+32,b'\x00')]
  for name,offset,replacement in mutations:
   load_exe(path,0x400000);u.mem_write(0x400000+offset,replacement);before_protect=len(protect_calls)
   check(label+' rejects changed '+name,call('Test_SupportedExe')==0 and call('Test_DeviceRva')==0 and call('Test_Profile')==0 and call('Test_HookRealDevice')==0 and len(protect_calls)==before_protect)
  check(label+' original supplied file stays unmodified',hashlib.sha256(path.read_bytes()).hexdigest()==expected)
  for feature,offset in [('getter',player_profiles[index][2]+5),('class identity',player_profiles[index][3]+1),('VMT size',player_profiles[index][1]-40)]:
   load_exe(path,0x400000);u.mem_write(0x400000+offset,b'\0');check(label+' bad '+feature+' disables only automatic name reader',call('Test_SupportedExe')==1 and call('Test_PilotReady')==0 and pilot_name()==(-1,''))
 
 active_module[0]=0;check('Missing module disables device selection',call('Test_SupportedExe')==0 and call('Test_RealDevice')==0)
 (Q/'compatibility_results.json').write_text(json.dumps({'status':'PASS, compiled x86 with real mapped EXE fixtures and mocked WinAPI/D3D','executables_not_executed_on_windows':True,'profiles':compatibility},indent=2))
 
(Q/'results.json').write_text(json.dumps({'status':'PASS (compiled x86, instrumented WinAPI/D3D/network)','checks':checks,'windows_game_test':False},ensure_ascii=False,indent=2))
