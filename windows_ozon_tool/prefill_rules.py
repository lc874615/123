"""Declared facts and seller defaults, independent of category attribute IDs."""
import hashlib,json,re
from decimal import Decimal,InvalidOperation

VERSION=1
COLORS={'金色':'золотой','红色':'красный','灰色':'серый','浅灰色':'светло-серый','深灰色':'темно-серый','黑色':'черный','白色':'белый','蓝色':'синий','浅蓝色':'голубой','绿色':'зеленый','米色':'бежевый','卡其色':'хаки','粉色':'розовый','棕色':'коричневый','咖啡色':'коричневый','银色':'серебристый','紫色':'фиолетовый','橙色':'оранжевый','黄色':'желтый'}
WORDS={'金属':'Металл','铁':'Металл','钢':'Сталь','塑料':'Пластик','实木':'Массив дерева','木':'Дерево','聚丙烯':'Полипропилен','纸板':'Картон','绒面':'Велюр','丝绒':'Бархат','绒布':'Велюр','布料':'Ткань','棉麻':'Льняная ткань','人造皮革':'Искусственная кожа','高弹性泡沫':'Высокоэластичная пена','高弹海绵':'Высокоэластичная пена','海绵':'Пенополиуретан','无填充':'Без наполнителя','拆卸':'В разобранном виде','拆装':'В разобранном виде','需组装':'В разобранном виде','未组装':'В разобранном виде','整装':'В собранном виде','已组装':'В собранном виде','免安装':'В собранном виде','现代':'Современный','北欧':'Скандинавский','复古':'Ретро','纯色':'Однотонный','无图案':'Однотонный','客厅':'Гостиная','餐厅':'Столовая','卧室':'Спальня','厨房':'Кухня','有扶手':'С подлокотниками','有靠背':'Со спинкой','软座':'Мягкое сиденье'}
FIELDS={
 'frame_material':('материал корпуса','материал каркаса','车身材料','框架材质'),
 'upholstery_material':('материал обивки','室内装潢材料','座面材质','面料材质'),
 'fill_material':('материал наполнителя','填充材料'),
 'supply_form':('форма поставки','交货形式'),
 'design_style':('стиль дизайна','设计风格'),
 'cover_pattern':('рисунок на обивке','室内装潢上的图案'),
 'rooms':('назначение (помещение)','用途(房间)','适用房间'),
 'features':('особенности','特点'),
 'execution':('исполнение','执行形','执行形式'),
 'coating':('покрытие корпуса','外壳涂层','表面涂层'),
 'max_load':('макс. нагрузка, кг','максимальная нагрузка, кг','最大承重','最大承重(kg)','最大负载'),
 'seat_height':('высота сиденья, см','座椅高度, cm','座高','座高(cm)'),
 'seat_width':('ширина сиденья, см','座椅宽度，厘米','座宽','座宽(cm)'),
 'seat_depth':('глубина сиденья, см','座椅深度, 厘米','座深','座深(cm)'),
 'back_height':('высота спинки, см','靠背高度，厘米','靠背高','靠背高(cm)'),
 'back_width':('ширина спинки, см','靠背宽度，厘米','靠背宽','靠背宽(cm)'),
}
NUMERIC={'max_load','seat_height','seat_width','seat_depth','back_height','back_width'}
PHOTO_KEYS=set(FIELDS)-{'fill_material','max_load','coating'}

def name(field):return re.sub(r'\s+',' ',str(field.get('name_ru') or field.get('name','')).casefold().replace('ё','е')).strip()
def chair(bundle):
 p=bundle.get('variant_parameters') or {};text=str(p.get('name',''))+' '+str((bundle.get('category') or {}).get('name',''))
 return bool(re.search(r'椅|凳|\bстул\w*|\bкресл\w*|\bтабурет\w*',text,re.I))
def basis(parameters):return hashlib.sha256(json.dumps({k:v for k,v in (parameters or {}).items() if k not in ('cost','margin','stock')},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def fixed_settings(bundle):
 old=dict(bundle.get('export_settings') or {});new={**old,'vat':'0'};bundle['export_settings']=new
 return old!=new
def split(value):return [p.strip() for p in re.split(r'[、,，;；/+＋|]+',str(value or '')) if p.strip()]
def color_values(value):
 result=[]
 for token in split(value):
  token=re.sub(r'[（(][^）)]*[）)]','',token).strip()
  token=re.sub(r'^(?:座面|面料|椅腿|框架|颜色)\s*[:：]?\s*','',token)
  converted=COLORS.get(token) or COLORS.get(token+'色')
  if not converted and not re.search(r'[\u4e00-\u9fff]',token):converted=token
  if not converted:return None
  if converted.casefold().replace('ё','е') not in [x.casefold().replace('ё','е') for x in result]:result.append(converted)
 return result or None
def translate(value):
 value=str(value or '').strip()
 if value in WORDS:return WORDS[value]
 return value if value and not re.search(r'[\u4e00-\u9fff]',value) else None
def field_kind(field):
 key=name(field)
 for kind,labels in FIELDS.items():
  if key in (x.casefold().replace('ё','е') for x in labels):return kind
 return None
def explicit(bundle,key):
 p=bundle.get('variant_parameters') or {}
 if str(p.get(key,'')).strip():return str(p[key]).strip()
 labels=(key,)+FIELDS.get(key,())
 for part in re.split(r'[;；\n]+',str(p.get('extra') or '')):
  match=re.match(r'\s*([^:：=]+)\s*[:：=]\s*(.+)',part)
  if match and match[1].strip().casefold() in [x.casefold() for x in labels]:return match[2].strip()
 return None
def photo_record(bundle,key):
 evidence=bundle.get('reference_attributes') or {}
 if evidence.get('basis')!=basis(bundle.get('variant_parameters')):return None
 for ref in evidence.get('references') or []:
  from pathlib import Path
  try:stat=Path(ref['path']).stat()
  except OSError:return None
  if [stat.st_size,stat.st_mtime_ns]!=ref.get('stat'):return None
 return (evidence.get('records') or {}).get(key)
def value_for(field,bundle):
 key=name(field);p=bundle.get('variant_parameters') or {};kind=field_kind(field)
 if key in ('цвет товара','цвет','颜色','商品颜色','название цвета','颜色名称'):
  colors=color_values(p.get('color'))
  if not colors:return None
  return colors if key not in ('название цвета','颜色名称') and (field.get('is_collection') or field.get('dictionary_id')) else ', '.join(colors)
 if key.startswith('количество в комплекте') or key in ('数量在集合中, pcs.','数量在集合中','количество предметов в комплекте'):return p.get('quantity')
 if key=='название модели для шаблона наименования' or key=='名称模板的型号名称':return bundle.get('model')
 if key in ('глубина, см','深度，厘米') and chair(bundle):return p.get('length')
 if kind is None:return None
 raw=explicit(bundle,kind)
 if raw is None and kind=='frame_material':raw=p.get('material')
 if raw is None and kind=='supply_form':raw=p.get('assembly')
 if raw is None and kind=='upholstery_material' and chair(bundle) and p.get('accessory_material') in ('绒面','丝绒','绒布','布料','棉麻','人造皮革'):raw=p['accessory_material']
 if raw:
  if kind in NUMERIC:
   match=re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(cm|厘米|kg|公斤|千克)?\s*',raw,re.I)
   return match[1] if match else None
  if kind in ('features','rooms') and field.get('is_collection'):
   values=[translate(v) for v in split(raw)];return values if values and all(values) else None
  return translate(raw)
 record=photo_record(bundle,kind)
 if record:return record['value']
 if chair(bundle) and kind=='max_load':return '150'
 if chair(bundle) and kind=='fill_material':return 'Высокоэластичная пена'
 return None
def aliases(field,value):
 result={str(value).strip().casefold().replace('ё','е')}
 for zh,ru in WORDS.items():
  if ru.casefold().replace('ё','е') in result:result.add(zh.casefold())
 kind=field_kind(field)
 if kind=='fill_material' and str(value).casefold()=='высокоэластичная пена':result.update(('высокоэластичный пенополиуретан','эластичный пенополиуретан','ппу повышенной эластичности','高弹性泡沫','高弹海绵'))
 if kind=='supply_form':
  if value=='В разобранном виде':result.update(('разобранный','разобранная','拆卸','拆装'))
  elif value=='В собранном виде':result.update(('собранный','собранная','整装'))
 return result
def annotation(field,bundle):
 kind=field_kind(field)
 if not kind:return None
 raw=explicit(bundle,kind);p=bundle.get('variant_parameters') or {}
 if kind=='upholstery_material' and not raw and p.get('accessory_material')=='绒面':
  return {'suggested':'Велюр','kind':'provided_material','confidence':'依据你填写的绒面','evidence':'配件/内衬材质：绒面','note':'按绒面织物匹配官方选项，请审核具体面料；未推断为天然麂皮。'}
 if not raw and not (kind=='frame_material' and p.get('material')) and not (kind=='supply_form' and p.get('assembly')):
  record=photo_record(bundle,kind)
  if record:return {'suggested':str(record['value']),'kind':'reference_image','confidence':'原始参考图读取，供审核','evidence':record['evidence'],'note':'依据原图可见内容或明确标注，手动修改优先。'}
  if chair(bundle) and kind in ('max_load','fill_material'):
   value='150' if kind=='max_load' else 'Высокоэластичная пена'
   return {'suggested':value,'kind':'seller_default','confidence':'你指定的椅子默认值','evidence':'最大承重默认150kg；填充材料默认高弹性泡沫','note':'这是用户默认规则，明确参数及你的手动修改优先。'}
 return None
