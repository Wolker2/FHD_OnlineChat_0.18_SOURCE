import runpy,io,contextlib,json
from pathlib import Path
with contextlib.redirect_stdout(io.StringIO()):ns=runpy.run_path(str(Path(__file__).with_name('emulate_font1.py')))
globals().update({k:v for k,v in ns.items() if k not in ['__name__','__file__','__spec__','__package__','__loader__','__cached__']})
network_checks=[]
def test(label,condition):
 assert condition,label;network_checks.append(label);print('PASS',label)
def set_api(name,n,fn):
 for dll in pe.DIRECTORY_ENTRY_IMPORT:
  for i in dll.imports:
   if i.name and i.name.decode()==name:put(i.address,stub(name,n,fn));return
 raise AssertionError('Missing import '+name)
set_api('GetSystemTime',1,local_time);set_api('GetLastError',0,lambda:12002)
class ThreadStopped(Exception):pass
attempt={};recv_packets=[]
def sleep(ms):
 if ms==5000:raise ThreadStopped()
 if ms!=1:raise AssertionError('Unexpected network Sleep '+str(ms))
set_api('Sleep',1,sleep)
set_api('WinHttpOpen',5,lambda *x:111)
set_api('WinHttpConnect',4,lambda s,h,p,z:attempt.setdefault('host',readw(h)) and 112)
set_api('WinHttpOpenRequest',7,lambda *x:113)
set_api('WinHttpSetOption',4,lambda *x:1)
set_api('WinHttpSetTimeouts',5,lambda *x:1)
set_api('WinHttpSendRequest',7,lambda *x:1)
set_api('WinHttpReceiveResponse',2,lambda *x:1)
def headers(h,l,n,out,size,idx):put(out,attempt['status']);return 1
set_api('WinHttpQueryHeaders',6,headers)
set_api('WinHttpWebSocketCompleteUpgrade',2,lambda *x:123)
set_api('WinHttpCloseHandle',1,lambda *x:1)
def receive(ws,out,n,size,kind):
 if not recv_packets:return 12002
 item=recv_packets.pop(0)
 if isinstance(item,int):return item
 data=json.dumps(item,ensure_ascii=False).encode();assert len(data)<n;u.mem_write(out,data);put(size,len(data));put(kind,2);return 0
set_api('WinHttpWebSocketReceive',5,receive)
def once(status=101,rows=None):
 attempt.clear();attempt['status']=status;recv_packets[:]=rows or []
 try:call('Test_NetworkRun')
 except ThreadStopped:pass
 else:raise AssertionError('Thread did not reach controlled retry boundary')
 return attempt['host']
# Exercise the complete compiled WinHTTP connection loop through mocked calls.
call('Test_NetworkReset');host=once(rows=[{'type':'hello','id':MY,'day':'20261029','history':[]},{'type':'presence','online':1,'users':[{'id':MY,'name':'Я'}]}])
test('One idle/transport receive failure retries primary instead of all-day fallback',host.endswith('workers.dev') and call('Test_UseBackup')==0)
call('Test_NetworkReset');once(503);once(503)
test('Two failed primary handshakes still retry primary',call('Test_UseBackup')==0)
once(503);test('Three failed primary handshakes temporarily enable reserve',call('Test_UseBackup')==1)
host=once(rows=[{'type':'phx_reply','ref':'1','status':'ok'}]);test('Fallback path actually connects to reserve host',host.endswith('supabase.co'))
clock['tick']+=59999;test('Temporary fallback lasts until the retry interval',call('Test_UseBackup')==1)
clock['tick']+=1;test('Primary is retried after sixty seconds without restarting game',call('Test_UseBackup')==0)
host=once(rows=[{'type':'hello','id':MY,'history':[]}]);test('Full connection loop switches back to primary after fallback',host.endswith('workers.dev'))
call('Test_NetworkReset');once(429);test('Explicit HTTP 429 retains daily quota fallback policy',call('Test_UseBackup')==1)
clock['day']+=1;test('Quota fallback expires on the next UTC date',call('Test_UseBackup')==0);clock['day']-=1
call('Test_NetworkReset');call('Test_ConnectionFailed',0,503,0);call('Test_ConnectionFailed',0,503,0);call('Test_ConnectionFailed',0,0,1)
test('Intentional nickname/probe reconnect does not count as outage',call('Test_UseBackup')==0)
# Healthy primary idle for one simulated hour: 360 actual heartbeat sends.
call('Test_NetworkReset');call('Test_HeartbeatStart',0);pump();before_packets=len(packets);before_closes=io['closes'];before_counts=(call('Test_HistoryCount',0),call('Test_HistoryCount',1))
for i in range(360):
 clock['tick']+=10000;call('Test_HeartbeatStep');recv({'type':'pong'});call('Test_ReceiveActivity');pump()
test('One simulated idle hour sends 360 application keepalives',len(packets)-before_packets==360 and all(p.get('type')=='ping' for p in packets[before_packets:]))
test('Responsive idle connection remains open for the full hour',io['closes']==before_closes and call('Test_Closing')==0)
test('Heartbeat replies do not become chat messages',before_counts==(call('Test_HistoryCount',0),call('Test_HistoryCount',1)))
clock['tick']+=34999;call('Test_HeartbeatStep');test('Watchdog allows a response before thirty-five seconds',call('Test_Closing')==0)
clock['tick']+=1;call('Test_HeartbeatStep');test('Watchdog closes a silent stale primary at thirty-five seconds',call('Test_Closing')==1 and io['closes']==before_closes+1)
call('Test_HeartbeatStep');test('A stale socket is closed only once while reconnecting',io['closes']==before_closes+1)
test('Sending into a known dead socket is refused',call('FHDChat_SendW',wide('keep this draft'))==0)
# Send/heartbeat/close serialization: busy is not considered a network failure.
call('Test_NetworkReset');call('Test_HeartbeatStart',0);call('Test_WireBusy',1);clock['tick']+=10000;before_packets=len(packets);before_closes=io['closes']
test('Busy socket returns failure to UI without clearing a draft',call('FHDChat_SendW',wide('retry later'))==0 and len(packets)==before_packets)
call('Test_HeartbeatStep');test('Busy heartbeat does not force a false disconnect',io['closes']==before_closes)
call('Test_WireBusy',0);call('Test_HeartbeatStep');test('Skipped busy heartbeat retries after sender releases socket',len(packets)==before_packets+1)
# Actual API errors are different from the busy guard.
set_api('WinHttpWebSocketSend',4,lambda *x:12030);call('Test_NetworkReset');call('Test_HeartbeatStart',0);clock['tick']+=10000;before_closes=io['closes'];call('Test_HeartbeatStep')
test('A failed primary heartbeat triggers reconnect',call('Test_Closing')==1 and io['closes']==before_closes+1)
set_api('WinHttpWebSocketSend',4,wire_send)
# Reserve receives its own protocol heartbeat and is probed even without incoming data.
call('Test_NetworkReset')
for i in range(3):call('Test_ConnectionFailed',0,503,0)
call('Test_HeartbeatStart',1);clock['tick']+=20000;before_packets=len(packets);call('Test_HeartbeatStep')
test('Reserve keeps its Phoenix heartbeat protocol',len(packets)==before_packets+1 and packets[-1].get('event')=='heartbeat')
clock['tick']+=40000;before_closes=io['closes'];call('Test_HeartbeatStep')
test('Silent reserve is interrupted for a scheduled primary retry',call('Test_Closing')==1 and io['closes']==before_closes+1 and call('Test_UseBackup')==0)
call('Test_NetworkReset');call('Test_ConnectionFailed',0,429,0);call('Test_HeartbeatStart',1);clock['day']+=1;call('Test_HeartbeatStep')
test('Silent quota reserve also retries primary after date change',call('Test_Closing')==1);clock['day']-=1
call('Test_NetworkReset');call('Test_HeartbeatStart',1)
test('Reserve status is explicitly visible in panel header','Резерв' in frame_text())
visible(True)
if call('Test_Settings'):cancel()
click(bounds()[0]+20,bounds()[1]+12);input_text('draft on send failure');call('Test_WireBusy',1);before_text=txt();enter()
test('Actual UI retains entered draft when the socket is busy',txt()==before_text)
call('Test_WireBusy',0);input_text('draft on lost socket');call('Test_NetworkReset');before_text=txt();enter()
test('Actual UI retains entered draft when connection is lost',txt()==before_text)
call('Test_HeartbeatStart',1);input_text('');key(0x100,27)
clock['tick']+=7000;shown=frame_text();frame();save_frame_png((Q/'reserve021.png'),True)
test('Reserve has an explicit warning that history is not saved','Резерв' in shown and 'без истории' in shown)
frame();save_frame_png((Q/'reserve021.png'),True)
# Cleanup so the test runner leaves no synthetic stale state.
call('Test_NetworkReset')
(Q/'network_results.json').write_text(json.dumps({'status':'PASS (actual compiled x86 network loop and heartbeat, mocked WinHTTP)','checks':network_checks,'ui_checks':len(checks),'real_one_hour_wait':False,'windows_game_test':False},ensure_ascii=False,indent=2))
print(json.dumps({'network_checks':len(network_checks),'ui_checks':len(checks),'status':'PASS'}))
