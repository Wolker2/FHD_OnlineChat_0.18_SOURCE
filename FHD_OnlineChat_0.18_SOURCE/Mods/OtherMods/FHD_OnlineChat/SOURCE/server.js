export default {
  async fetch(req,env){
    const url=new URL(req.url);
    if(url.pathname==="/health")return env.CHAT.getByName("global").fetch(req);
    if(url.pathname!=="/ws")return new Response("FHD OnlineChat primary — WebSocket: /ws?name=Ranger",{headers:{"content-type":"text/plain;charset=utf-8"}});
    if(req.headers.get("Upgrade")?.toLowerCase()!=="websocket")return new Response("WebSocket required",{status:426});
    let name=(url.searchParams.get("name")||"").trim();
    if(!/^[\p{L}\p{N}_ .-]{1,24}$/u.test(name))return new Response("Invalid name",{status:400});
    const origin=req.headers.get("origin");
    if(origin){try{if(new URL(origin).host!==url.host)return new Response("Origin blocked",{status:403})}catch{return new Response("Origin blocked",{status:403})}}
    return env.CHAT.getByName("global").fetch(req);
  }
};
import {DurableObject} from "cloudflare:workers";
// One room calendar for all primary clients, using IANA DST rules.
const roomClock=new Intl.DateTimeFormat("en-GB",{timeZone:"Europe/Kyiv",year:"numeric",month:"2-digit",day:"2-digit"});
function roomDay(ms){const p=roomClock.formatToParts(ms);return ["year","month","day"].map(k=>p.find(v=>v.type===k).value).join("")}
function dayWindow(ms){
 const day=roomDay(ms);let lo=ms-30*3600000,hi=ms;
 while(lo<hi){const mid=Math.floor((lo+hi)/2);if(roomDay(mid)===day)hi=mid;else lo=mid+1}const start=lo;
 lo=ms+1;hi=ms+30*3600000;while(lo<hi){const mid=Math.floor((lo+hi)/2);if(roomDay(mid)===day)lo=mid+1;else hi=mid}
 return {day,start,end:lo};
}
export class ChatRoom extends DurableObject{
 constructor(ctx,env){super(ctx,env);ctx.storage.sql.exec("CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,at INTEGER NOT NULL,nick TEXT NOT NULL,body TEXT NOT NULL)");
 const columns=new Set([...ctx.storage.sql.exec("PRAGMA table_info(messages)")].map(c=>c.name));
 if(!columns.has("sender_id"))ctx.storage.sql.exec("ALTER TABLE messages ADD COLUMN sender_id TEXT");
 this.nickColumns=["nick","sender"].filter(n=>columns.has(n));
 if(!this.nickColumns.length)throw new Error("Unsupported history schema");
 this.nameExpr=this.nickColumns.length===2?"COALESCE(nick,sender)":this.nickColumns[0];
 ctx.storage.sql.exec("CREATE TABLE IF NOT EXISTS fhd_chat_day(id INTEGER PRIMARY KEY,day TEXT NOT NULL)");
 this.ready=ctx.blockConcurrencyWhile(async()=>{this.rollDay();if(await ctx.storage.getAlarm()===null)await ctx.storage.setAlarm(this.dayEnd)});
 }
 rollDay(){
  const now=Date.now(),day=roomDay(now);if(this.day===day)return false;
  const previous=[...this.ctx.storage.sql.exec("SELECT day FROM fhd_chat_day WHERE id=1")][0]?.day;
  const window=dayWindow(now);
  this.ctx.storage.sql.exec("DELETE FROM messages WHERE at < ?",window.start);
  this.ctx.storage.sql.exec("INSERT INTO fhd_chat_day(id,day) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET day=excluded.day",day);
  this.day=day;this.dayStart=window.start;this.dayEnd=window.end;
  if(previous!==day)this.broadcast({type:"reset",day});return true;
 }
 async checkDay(){await this.ready;if(this.rollDay())await this.ctx.storage.setAlarm(this.dayEnd)}
 async alarm(){await this.ready;this.rollDay();await this.ctx.storage.setAlarm(this.dayEnd)}
 send(ws,obj){try{ws.send(JSON.stringify(obj))}catch{}}
 users(){return this.ctx.getWebSockets().filter(w=>w.readyState===1).map(w=>w.deserializeAttachment()).filter(v=>v?.id)}
 broadcast(v){for(const w of this.ctx.getWebSockets())this.send(w,v)}
 presence(){const users=this.users();this.broadcast({type:"presence",online:users.length,users:users.map(u=>({id:u.id,name:u.name}))})}
 async fetch(req){
 await this.checkDay();
 if(new URL(req.url).pathname==="/health"){
  this.ctx.storage.sql.exec(`SELECT ${this.nameExpr} AS name,body FROM messages ORDER BY id DESC LIMIT 1`);
  return Response.json({ok:true,service:"FHD_OnlineChat",role:"primary",version:"0.18",storage_ready:true,day:this.day,time_zone:"Europe/Kyiv",next_reset:this.dayEnd});
 }
 if(this.ctx.getWebSockets().length>=120)return new Response("Room full",{status:503});
 const name=new URL(req.url).searchParams.get("name");const pair=new WebSocketPair();const a=pair[0],b=pair[1];this.ctx.acceptWebSocket(b);const id=crypto.randomUUID();b.serializeAttachment({id,name,last:0});
 const history=[...this.ctx.storage.sql.exec(`SELECT id,at,${this.nameExpr} AS name,body AS text,sender_id AS fromId FROM messages WHERE at >= ? ORDER BY id DESC LIMIT 30`,this.dayStart)].reverse().map(m=>({...m,day:this.day}));
 this.send(b,{type:"hello",id,name,version:"0.18",day:this.day,history});this.presence();return new Response(null,{status:101,webSocket:a})}
 async webSocketMessage(ws,raw){await this.ready;const me=ws.deserializeAttachment();if(!me?.id)return;let data;try{data=JSON.parse(raw)}catch{return}
 if(typeof data?.text!=="string"||data.text.trim().length===0||data.text.length>500||!["chat","private"].includes(data.type))return;
 await this.checkDay();const now=Date.now();if(now-me.last<1200){this.send(ws,{type:"error",message:"Rate limit"});return}
 me.last=now;ws.serializeAttachment(me);
 const msg={type:data.type,id:crypto.randomUUID(),at:now,name:me.name,fromId:me.id,day:this.day,text:data.text.trim()};
 if(data.type==="private"){const peer=this.ctx.getWebSockets().find(w=>w.readyState===1&&w.deserializeAttachment()?.id===data.toId);if(!peer){this.send(ws,{type:"error",message:"Recipient offline"});return}const direct={...msg,toId:data.toId,toName:peer.deserializeAttachment().name};this.send(peer,direct);if(peer!==ws)this.send(ws,{...direct,sent:true});return}
 this.ctx.storage.sql.exec(`INSERT INTO messages(at,${this.nickColumns.join(",")},body,sender_id) VALUES(${Array(this.nickColumns.length+3).fill("?").join(",")})`,now,...this.nickColumns.map(()=>me.name),msg.text,me.id);
 this.ctx.storage.sql.exec("DELETE FROM messages WHERE id NOT IN(SELECT id FROM messages ORDER BY id DESC LIMIT 30)");this.broadcast(msg)
 }
 webSocketClose(ws){try{ws.close()}catch{}this.presence()}
 webSocketError(ws){try{ws.close(1011,"Socket error")}catch{}this.presence()}
}