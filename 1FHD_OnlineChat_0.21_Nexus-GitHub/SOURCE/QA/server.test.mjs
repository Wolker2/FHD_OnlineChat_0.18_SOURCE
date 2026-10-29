import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname,join} from 'node:path';
const here=dirname(fileURLToPath(import.meta.url));
import {DatabaseSync} from 'node:sqlite';
const path=existsSync(join(here,'../server.js'))?join(here,'../server.js'):'build020/Mods/OtherMods/FHD_OnlineChat/SOURCE/server.js';
const source=readFileSync(path,'utf8').replace('import {DurableObject} from "cloudflare:workers";','const DurableObject=globalThis.TestDurableObject;')+'\nexport {roomDay,dayWindow};';
globalThis.TestDurableObject=class{constructor(ctx,env){this.ctx=ctx;this.env=env;}};
globalThis.Response=class{constructor(body,options={}){this.body=body;Object.assign(this,options)}static json(body){return new this(body,{status:200})}};
globalThis.WebSocketPair=class{constructor(){this[0]={};this[1]=new Socket;}};
globalThis.WebSocketRequestResponsePair=class{constructor(request,response){this.request=request;this.response=response}getRequest(){return this.request}getResponse(){return this.response}};
class Socket {readyState=1;messages=[];serializeAttachment(a){this.attachment=structuredClone(a)}deserializeAttachment(){return structuredClone(this.attachment)}send(raw){this.messages.push(JSON.parse(raw))}close(){this.readyState=3;}}
const {ChatRoom,default:worker,roomDay,dayWindow}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
let now=Date.parse('2026-10-27T21:59:50Z');Date.now=()=>now;
const results=[];
for(const schema of ['sender','nick','both','new']){
 now=Date.parse('2026-10-27T21:59:50Z');const db=new DatabaseSync(':memory:');
 if(schema!=='new'){
  const cols=schema==='both'?'nick TEXT NOT NULL,sender TEXT NOT NULL':`${schema} TEXT NOT NULL`;
  db.exec(`CREATE TABLE messages(id INTEGER PRIMARY KEY AUTOINCREMENT,at INTEGER NOT NULL,${cols},body TEXT NOT NULL)`);
  const names=schema==='both'?'nick,sender':schema,marks=schema==='both'?'?,?,?,?':'?,?,?';
  for(let i=0;i<33;i++)db.prepare(`INSERT INTO messages(at,${names},body) VALUES(${marks})`).run(now-1000,...(schema==='both'?['Old','Old']:['Old']),String(i));
 }
 const sockets=[];
 let alarm=null;const ctx={setWebSocketAutoResponse(pair){this.autoResponse=pair},blockConcurrencyWhile(fn){return fn()},storage:{async getAlarm(){return alarm},async setAlarm(value){alarm=value},sql:{exec(sql,...params){const statement=db.prepare(sql);return statement.columns().length?statement.all(...params):(statement.run(...params),[]);}}},getWebSockets(){return sockets},acceptWebSocket(ws){sockets.push(ws)}};
 const room=new ChatRoom(ctx,{});new ChatRoom(ctx,{});assert.ok(db.prepare('PRAGMA table_info(messages)').all().some(c=>c.name==='sender_id'));const env={CHAT:{getByName(name){assert.equal(name,'global');return room}}};
 const health=await worker.fetch(new Request('https://chat.test/health'),env);
 assert.equal(health.body.storage_ready,true);
 await room.fetch(new Request('https://chat.test/ws?name=Tester'));
 const socket=sockets[0];const hello=socket.messages.find(v=>v.type==='hello');
 assert.equal(hello.version,'0.20');
 assert.equal(ctx.autoResponse.getRequest(),'{"type":"ping"}');assert.equal(ctx.autoResponse.getResponse(),'{"type":"pong"}');
 // Keepalives do not mutate identity, timestamps, rate limit or history.
 const heartbeatBefore=socket.deserializeAttachment(),storedBefore=db.prepare('SELECT count(*) AS n FROM messages').get().n;
 for(let i=0;i<360;i++){
  now+=10000;
  // Model the runtime auto-response without invoking the DO event handler.
  const request='{"type":"ping"}';assert.equal(request,ctx.autoResponse.getRequest());socket.send(ctx.autoResponse.getResponse());
 }
 assert.deepEqual(socket.deserializeAttachment(),heartbeatBefore);assert.equal(db.prepare('SELECT count(*) AS n FROM messages').get().n,storedBefore);
 assert.equal(socket.messages.at(-1).type,'pong');
 // Fallback handler covers spaced JSON ping (runtime auto-response is exact).
 await room.webSocketMessage(socket,'{ "type": "ping" }');assert.equal(socket.messages.at(-1).type,'pong');assert.deepEqual(socket.deserializeAttachment(),heartbeatBefore);
 now=Date.parse('2026-10-27T21:59:50Z');

 assert.equal(hello.history.length,schema==='new'?0:30);
 if(schema!=='new'){assert.equal(hello.history[0].text,'3');assert.equal(hello.history.at(-1).text,'32')}
 await room.webSocketMessage(socket,JSON.stringify({type:'chat',text:'Проверка сохранения'}));
 assert.equal(db.prepare('SELECT body FROM messages ORDER BY id DESC LIMIT 1').get().body,'Проверка сохранения');
 assert.equal(socket.messages.at(-1).text,'Проверка сохранения');
 assert.ok(db.prepare('SELECT count(*) AS n FROM messages').get().n<=30);
 assert.equal(db.prepare('SELECT sender_id FROM messages ORDER BY id DESC LIMIT 1').get().sender_id,socket.deserializeAttachment().id);
 await room.webSocketMessage(socket,JSON.stringify({type:'chat',text:'too fast'}));
 assert.equal(socket.messages.at(-1).type,'error');
 // Real local SQLite + three WebSocket peers: PM must never go to the third peer or DB.
 await room.fetch(new Request('https://chat.test/ws?name=Bee'));
 await room.fetch(new Request('https://chat.test/ws?name=Observer'));
 for(const ws of sockets)ws.messages=[];
 const me=socket.deserializeAttachment();me.last=0;socket.serializeAttachment(me);
 const receiver=sockets[1];const toId=receiver.deserializeAttachment().id;
 const persisted=[...db.prepare('SELECT sender_id AS fromId,body AS text FROM messages ORDER BY id DESC LIMIT 1').all()];assert.equal(persisted[0].fromId,me.id);
 const before=db.prepare('SELECT count(*) AS n FROM messages').get().n;
 await room.webSocketMessage(socket,JSON.stringify({type:'private',toId,text:'Только для Bee'}));
 assert.equal(socket.messages.length,1);assert.equal(receiver.messages.length,1);assert.equal(sockets[2].messages.length,0);
 assert.equal(receiver.messages[0].type,'private');assert.equal(receiver.messages[0].toId,toId);assert.equal(receiver.messages[0].toName,'Bee');
 assert.equal(socket.messages[0].sent,true);assert.equal(db.prepare('SELECT count(*) AS n FROM messages').get().n,before);
 receiver.readyState=2;room.presence();assert.equal(socket.messages.at(-1).online,2);
 const retry=socket.deserializeAttachment();retry.last=0;socket.serializeAttachment(retry);socket.messages=[];sockets[2].messages=[];
 await room.webSocketMessage(socket,JSON.stringify({type:'private',toId,text:'Recipient is closing'}));
 assert.equal(socket.messages.at(-1).message,'Recipient offline');assert.equal(sockets[2].messages.length,0);
 room.webSocketClose(receiver);assert.equal(socket.messages.at(-1).online,2);
 // A later reader gets different IDs for messages from two equal-name players.
 const same=socket.deserializeAttachment();same.name='Same';same.last=0;socket.serializeAttachment(same);await room.webSocketMessage(socket,JSON.stringify({type:'chat',text:'same A'}));
 const other=sockets[2].deserializeAttachment();other.name='Same';other.last=0;sockets[2].serializeAttachment(other);await room.webSocketMessage(sockets[2],JSON.stringify({type:'chat',text:'same B'}));
 await room.fetch(new Request('https://chat.test/ws?name=LateReader'));const history=sockets[3].messages.find(v=>v.type==='hello').history;const dup=history.filter(v=>v.name==='Same');assert.equal(dup.length,2);assert.notEqual(dup[0].fromId,dup[1].fromId);
 assert.ok(!history.some(v=>v.text==='Только для Bee'));
 assert.equal(alarm,Date.parse('2026-10-27T22:00:00Z'));
 now=alarm;for(const s of sockets)s.messages=[];await room.alarm();
 assert.equal(db.prepare('SELECT count(*) AS n FROM messages').get().n,0);
 assert.ok(sockets.filter(s=>s.readyState===1).every(s=>s.messages.some(v=>v.type==='reset'&&v.day==='20261028')));
 const resetCount=socket.messages.filter(v=>v.type==='reset').length;
 now+=2000;await room.webSocketMessage(socket,JSON.stringify({type:'chat',text:'only new day'}));
 await room.alarm();assert.equal(db.prepare('SELECT count(*) AS n FROM messages').get().n,1);assert.equal(socket.messages.filter(v=>v.type==='reset').length,resetCount);
 const restarted=new ChatRoom(ctx,{});await restarted.ready;
 assert.equal(socket.messages.filter(v=>v.type==='reset').length,resetCount);
 await restarted.fetch(new Request('https://chat.test/ws?name=AfterMidnight'));
 const fresh=sockets.at(-1).messages.find(v=>v.type==='hello');assert.equal(fresh.day,'20261028');assert.deepEqual(fresh.history.map(v=>v.text),['only new day']);assert.ok(fresh.history.every(v=>v.day==='20261028'));
 now=Date.parse('2026-10-30T14:00:00Z');await room.webSocketMessage(socket,JSON.stringify({type:'chat',text:'after missed alarm'}));
 assert.deepEqual(db.prepare('SELECT body FROM messages').all().map(v=>v.body),['after missed alarm']);assert.equal(socket.messages.at(-1).day,'20261030');assert.equal(alarm,Date.parse('2026-10-30T22:00:00Z'));
 results.push({schema,status:'PASS: health, preserved history, send/store/broadcast, cap30, rate-limit, PM isolated from third peer and public DB; closing users excluded from online count; identity migration, duplicate-name IDs, 1-hour heartbeat simulation with unchanged ID/history and rate state, daily alarm, idempotent retry, reconnect/hibernation history, missed-alarm recovery'});
 db.close();
}
const spring=dayWindow(Date.parse('2026-03-28T22:30:00Z')),autumn=dayWindow(Date.parse('2026-10-24T21:30:00Z'));
assert.equal(spring.end-spring.start,23*3600000);assert.equal(autumn.end-autumn.start,25*3600000);assert.notEqual(roomDay(spring.end),spring.day);assert.notEqual(roomDay(autumn.end),autumn.day);
results.push({scenario:'Kyiv DST midnight boundaries',status:'PASS: 23-hour and 25-hour calendar days'});
writeFileSync(join(here,'server_results.json'),JSON.stringify({status:'PASS (Node SQLite + mocked WebSockets)',results},null,2));
console.log(JSON.stringify(results));
