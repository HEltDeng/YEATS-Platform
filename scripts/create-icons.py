from pathlib import Path
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parents[1]/'apps/parent-miniprogram/assets'
root.mkdir(exist_ok=True)
for name in ['home','homework','knowledge','me']:
 for active in [False,True]:
  im=Image.new('RGBA',(64,64));d=ImageDraw.Draw(im);c='#F26A00' if active else '#9C8A76';w=4
  if name=='home':
   d.line([(8,29),(32,9),(56,29)],fill=c,width=w);d.line([(15,25),(15,55),(49,55),(49,25)],fill=c,width=w);d.rectangle((27,37,37,55),outline=c,width=w)
  elif name=='homework':
   d.rounded_rectangle((15,10,49,56),radius=5,outline=c,width=w);d.line((23,26,41,26),fill=c,width=w);d.line((23,36,41,36),fill=c,width=w);d.line((23,46,36,46),fill=c,width=w)
  elif name=='knowledge':
   d.line([(8,12),(28,15),(32,21),(36,15),(56,12),(56,49),(36,52),(32,56),(28,52),(8,49),(8,12)],fill=c,width=w);d.line((32,21,32,55),fill=c,width=w)
  else:d.ellipse((22,9,42,29),outline=c,width=w);d.arc((12,31,52,68),180,360,fill=c,width=w);d.line((12,50,52,50),fill=c,width=w)
  im.save(root/(name+('-on' if active else '')+'.png'))
