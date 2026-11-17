"""Approximate visual aids, never official product color samples."""
from prefill_rules import color_values
PALETTE={'черный':'#24272D','белый':'#F8F8F5','серый':'#92989E','светло-серый':'#CBD0D5','темно-серый':'#50565D','красный':'#D44545','синий':'#3467B5','голубой':'#8CC7E5','зеленый':'#4E865C','светло-зеленый':'#A2CA8E','темно-зеленый':'#254D38','бежевый':'#DBC5A5','коричневый':'#815940','розовый':'#E4A4BA','фиолетовый':'#8A6CB1','оранжевый':'#E69B4E','желтый':'#E4CC64','золотой':'#C2A257','серебристый':'#BCC2CB','хаки':'#8E9471','бордовый':'#813F50','бирюзовый':'#5DAEAD','кремовый':'#EEE1BE','молочный':'#F3ECDD','оливковый':'#8A9552','персиковый':'#E7B79B','лиловый':'#B299CA','графитовый':'#4B535D','антрацит':'#3E454B','шоколадный':'#654636','терракотовый':'#B67555'}
PALETTE.update({'аквамариновый':'#80C7C0','баклажановый':'#60435F','ванильный':'#F2E5AF','васильковый':'#6F8DCE','вишневый':'#8F3447','горчичный':'#BC9C3E','изумрудный':'#3B8C74','коралловый':'#DD8B7A','кофейный':'#947663','лавандовый':'#BAB0D8','лайм':'#BDD66D','лимонный':'#E9E084','малиновый':'#B5476C','медный':'#B27D5A','ментоловый':'#A1D0B8','мятный':'#A3CDBC','морская волна':'#438C91','песочный':'#CFB78F','перламутровый':'#E1DBD0','пудровый':'#DDC0BE','салатовый':'#BCD28D','сиреневый':'#B5A0CA','слоновая кость':'#ECE7CF','фуксия':'#BA4D9B','бронзовый':'#A38760','охра':'#BC924C','мокко':'#9B8474','серо-бежевый':'#B2AA9C','бежево-серый':'#B2AA9C','серо-коричневый':'#887C71','небесно-голубой':'#9EC7E3'})

def swatch(value,size=(52,28)):
 from PIL import Image,ImageDraw
 key=str(value).strip().casefold().replace('ё','е');colors=color_values(value) or [key];rgb=[PALETTE.get(c.casefold().replace('ё','е')) for c in colors]
 if any(x in key for x in ('разноцвет','мультиколор','多色','彩色')):rgb=['#D47E7E','#E0CA78','#79AD99','#7E9FC7']
 im=Image.new('RGB',size,'#EDF0F5');d=ImageDraw.Draw(im)
 if all(rgb):
  for i,c in enumerate(rgb):d.rectangle((i*size[0]//len(rgb),0,(i+1)*size[0]//len(rgb),size[1]),fill=c)
 else:
  for y in range(0,size[1],7):
   for x in range(0,size[0],7):d.rectangle((x,y,x+6,y+6),fill='#E1E6ED' if (x//7+y//7)%2 else '#F9FAFC')
  if 'прозрачн' not in key:d.text((size[0]//2-3,size[1]//2-6),'?',fill='#4F5F75')
 d.rectangle((0,0,size[0]-1,size[1]-1),outline='#B8C2CE')
 return im
