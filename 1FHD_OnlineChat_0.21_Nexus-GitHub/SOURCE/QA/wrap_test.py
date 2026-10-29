import runpy,io,contextlib,json,re
from pathlib import Path
from datetime import date,timedelta
with contextlib.redirect_stdout(io.StringIO()):ns=runpy.run_path(str(Path(__file__).with_name('emulate_font1.py')))
globals().update({k:v for k,v in ns.items() if k not in ['__name__','__file__','__spec__','__package__','__loader__','__cached__']})
wrap_checks=[]
def test(label,condition):
 assert condition,label;wrap_checks.append(label)
BODY_COLOR=0xffdeeaf5
texts=[('words','Это длинное сообщение в чате. Оно должно полностью переноситься на следующие строки без повторения имени игрока. Проверяем начало середину и самый конец сообщения.'),('solid','Ж'*500),('mixed',('Ranger проверяет message wrap 12345. '*16)[:500])]
nick='ДлинноеИмяПилота123456789'[:24]
case=0
# Decode the actual glyph vertices only within the message area.
def rendered_rows():
 x,y,w,h=bounds();top=52 if call('Test_Tab') else 32;lines=(h-58-top)//20;rows={}
 for texture,b in render[-2:]:
  if not texture:continue
  for off in range(0,len(b),6*28):
   v=struct.unpack_from('<4fI2f',b,off);gx,gy=round(v[0]+.5),round(v[1]+.5)
   if not y+top<=gy<y+top+lines*20:continue
   # Ignore sidebar labels in PM mode.
   if gx<x+(138 if call('Test_Tab') else 10):continue
   if v[4]!=BODY_COLOR and v[4]!=call('Test_Color',wide(nick),zid(A)):continue
   idx=round(v[6]*256/20)*32+round(v[5]*512/16)
   char=chr(idx+32) if idx<95 else chr(0x400+idx-95) if idx<191 else '?'
   row=(gy-y-top)//20;rows.setdefault(row,[]).append((gx,char,v[4]))
 return rows
for preset in range(4):
 for private in (False,True):
  for kind,text in texts:
   case+=1;day=(date(2026,11,1)+timedelta(days=case)).strftime('%Y%m%d')
   call('Test_Transport',0);recv({'type':'hello','id':MY,'day':day,'history':[]});presence([nick,'Боб']);pump()
   recv({'type':'reset','day':day});call('Test_CheckDay')
   # A fresh strictly newer server day clears all prior cases.
   if call('Test_Settings'):cancel()
   gear();size_button(preset);apply()
   x,y,w,h=bounds();click(x+20,y+12)
   if private:choose(A,nick);pm(A,nick,text)
   else:public(A,nick,text)
   pump();frame();total=call('Test_ActiveRows');top=52 if private else 32;visible_lines=(h-58-top)//20;max_scroll=max(0,total-visible_lines)
   seen={};within=True
   for scroll in range(max_scroll+1):
    frame();start=max(0,total-visible_lines-scroll)
    for screenrow,glyphs in rendered_rows().items():
     seen[start+screenrow]=glyphs
     within=within and all(x+(138 if private else 10)<=gx and gx+16<=x+w-16 for gx,c,col in glyphs)
    if scroll<max_scroll:key(0x20a,120<<16,((y+top+5)<<16)|(x+w-30))
   body_rows=[''.join(c for gx,c,col in seen.get(row,[]) if col==BODY_COLOR) for row in range(total)]
   actual=''.join(''.join(body_rows).split());expected=''.join(text.split())
   label=f'{preset}/{"PM" if private else "public"}/{kind}'
   test(label+' all non-space characters remain visible through scrolling',actual==expected)
   test(label+' nickname appears only on the first row',sum(sum(col!=BODY_COLOR for gx,c,col in g) for g in seen.values())==min(len(nick),12 if private else 16) and all(all(col==BODY_COLOR for gx,c,col in seen.get(row,[])) for row in range(1,total)))
   test(label+' rendered glyphs remain inside right and left history edges',within)
   test(label+' history counts messages while scrolling counts wrapped rows',call('Test_ActiveCount')==1 and total>1 and len(seen)==total)
   if not private:
    before_tab=call('Test_Tab');click(x+15,y+top+24,True)
    test(label+' continuation row has no fake nickname click target',call('Test_Tab')==before_tab)
   if kind=='words':
    # Every split lands between words, not inside a word of this fixture.
    test(label+' ordinary words do not split in the middle',[word for row in body_rows for word in row.split()]==text.split())
    save_frame_png(Q/(f'wrap021_{preset}_{"pm" if private else "public"}.png'),True)
   if kind=='words' and not private:
    click(x+15,y+top+4,True);test(label+' first-row nickname still opens exact recipient',readz(call('Test_Target'))==A)
# Ensure the original 30-message retention is not converted to a 30-row cap.
case+=1;day=(date(2026,11,1)+timedelta(days=case)).strftime('%Y%m%d');recv({'type':'reset','day':day});pump()
x,y,w,h=bounds();click(x+20,y+12)
for i in range(35):public(A,nick,'Номер '+str(i)+' '+('продолжение '*12))
pump();frame()
test('Public retention remains thirty whole multi-line messages',call('Test_HistoryCount',0)==30 and call('Test_ActiveRows')>30)
# Check the actual D3D texture filled by the compiled experimental DLL.
atlas=bytes(u.mem_read(pixels,512*256*4))
alpha_values=[];has_gap=True;outside_cell=False
for i in range(196):
 for yy in range(20):
  row=((i//32)*20+yy)*512+(i%32)*16
  values=[atlas[(row+xx)*4+3] for xx in range(16)]
  alpha_values.extend(values[:7]);has_gap=has_gap and values[7]==0
  outside_cell=outside_cell or any(values[8:])
test('Compiled atlas leaves a transparent separator after every glyph',has_gap)
test('No glyph extends into the next fixed character cell',not outside_cell)
test('Font texture retains real grayscale antialiasing',any(0<a<255 for a in alpha_values) and 255 in alpha_values)
# Wide Cyrillic combinations and punctuation are present, not fallback boxes.
characters=[chr(i) for i in range(32,127)]+[chr(i) for i in range(0x400,0x460)]+[chr(i) for i in [0x490,0x491,0x2014,0x2013,0x2026]]
masks=[]
for c in 'шщжмыюийёґ!?':
 idx=characters.index(c);mask=bytes(atlas[(((idx//32)*20+yy)*512+(idx%32)*16+xx)*4+3] for yy in range(20) for xx in range(8));masks.append(mask)
test('Confusable Cyrillic combinations have distinct nonempty glyphs',all(any(m) for m in masks) and len(set(masks))==len(masks))
(Q/'wrap_results.json').write_text(json.dumps({'status':'PASS (compiled x86, actual renderer vertices and input dispatch)','ui_checks':len(checks),'wrap_checks':wrap_checks,'windows_game_test':False},ensure_ascii=False,indent=2))
print(json.dumps({'status':'PASS','ui_checks':len(checks),'wrap_checks':len(wrap_checks),'sizes':4,'channels':['public','private']}))
