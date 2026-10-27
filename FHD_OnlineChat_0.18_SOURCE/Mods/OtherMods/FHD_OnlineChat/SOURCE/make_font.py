from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',13)
chars=[chr(i) for i in range(32,127)]+[chr(i) for i in range(0x400,0x460)]+[chr(i) for i in [0x0490,0x0491,0x2014,0x2013,0x2026]]
assert len(chars)==196
rows=[]
for ch in chars:
 im=Image.new('L',(16,20),0);d=ImageDraw.Draw(im)
 # Use bbox with bearing: position glyph at x0 y ~ 3, including punctuation
 d.text((0,1),ch,fill=255,font=font,stroke_width=0)
 for y in range(20):
  bits=0
  for x in range(16):
   if im.getpixel((x,y))>75:bits|=1<<(15-x)
  rows.append(bits)
out=Path(__file__).with_name('font16.h')
out.write_text('/* 16x20 bitmap glyph atlas derived from rasterized font, not a font file. */\nstatic const unsigned short glyphs16[] = {\n'+',\n'.join('  '+','.join('0x%04X'%r for r in rows[i:i+20]) for i in range(0,len(rows),20))+'\n};\n#define GLYPH_COUNT '+str(len(chars))+'\n')
print(len(rows),out.stat().st_size)
