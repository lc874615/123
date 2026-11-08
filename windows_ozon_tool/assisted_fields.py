"""Evidence-labelled proposals; never silently confirm inferred or legal attributes."""
import hashlib,json,re
from decimal import Decimal,InvalidOperation
from attribute_service import field_key

def kind(field):
 name=(field.get('name_ru') or field.get('name','')).casefold().replace('ё','е')
 if 'объем главного отделения' in name or '主隔层容积' in name:return 'volume'
 if 'число секций' in name or 'количество отделений' in name or '节数' in name:return 'sections'
 if 'нужен код маркировки' in name or '需要标记代码' in name:return 'marking'
 if 'pdf' in name and not any(w in name for w in ('название файла','文件名称')):return 'pdf'
 return None

def proposals(bundle):
 p=bundle.get('variant_parameters') or {};extra=str(p.get('extra') or '');result=[]
 for f in (bundle.get('attribute_draft') or {}).get('fields',[]):
  k=kind(f)
  if not k:continue
  row={'key':field_key(f),'field':f,'kind':k,'suggested':'','confidence':'待核对','required':bool(f.get('is_required')),'evidence':'','note':''}
  if k=='volume':
   try:
    dimensions=[Decimal(str(p.get('inner_'+x) or '')) for x in ('length','width','height')]
    if not all(x.is_finite() and x>0 for x in dimensions):raise ValueError()
    row.update(suggested=str((dimensions[0]*dimensions[1]*dimensions[2]/1000).normalize()),confidence='有内部尺寸依据',evidence='内部长宽高(cm)：'+' × '.join(map(str,dimensions)),note='仅适用近似长方体，形状不规则时请改为实测容量。')
   except (InvalidOperation,ValueError):
    try:
     dimensions=[Decimal(str(p.get(x) or '')) for x in ('length','width','height')]
     if not all(x.is_finite() and x>0 for x in dimensions):raise ValueError()
     bound=dimensions[0]*dimensions[1]*dimensions[2]/1000
     row['evidence']='外部长宽高乘积为 '+str(bound.normalize())+' L；不是主隔层容量，不自动填入。'
    except (InvalidOperation,ValueError):row['evidence']='缺少内部尺寸或实测容量。'
    row['note']='请核对内尺寸并计算，或填写实测升数。'
  elif k=='sections':
   match=re.search(r'(?:隔层数|独立隔层|节数)\s*[:：=]?\s*([1-9][0-9]*)',extra)
   if match:row.update(suggested=match[1],confidence='参数明确声明',evidence=match[0])
   else:row.update(evidence='现有参数未声明隔层数量；每套件数不代表隔层数。',note='请点开原始参考图核对独立收纳空间；遮挡时需实物确认。')
  elif k=='marking':row.update(evidence='官方类目字段'+('要求必填。' if row['required'] else '未要求必填，可暂留空。'),note='需根据适用商品编码、用途及平台规则核对，不能只凭图片或类目判定无需标记。请从官方选项选择已核实结果。')
  else:row.update(evidence='官方PDF字段'+('要求必填。' if row['required'] else '非必填，无资料可留空。'),note='普通说明书可根据已确认参数生成；证书、检测或合规材料须上传真实文件，不自动制作。')
  result.append(row)
 return result

def create_manual(bundle,path):
 """Raster PDF with Cyrillic font, only known facts. This is not a certificate."""
 from PIL import Image,ImageDraw,ImageFont
 import os
 from pathlib import Path
 p=bundle.get('variant_parameters') or {};font=None
 candidates=[Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/'arial.ttf',Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
 for candidate in candidates:
  if candidate.is_file():font=ImageFont.truetype(str(candidate),26);break
 if font is None:raise ValueError('找不到支持俄文的字体，未生成PDF')
 lines=['Информация о товаре',str((bundle.get('copy') or {}).get('title_ru') or ''),'Артикул: '+str(bundle.get('offer_id') or bundle.get('sku',''))]
 names={'quantity':'Количество в комплекте, шт','length':'Длина изделия, см','width':'Ширина изделия, см','height':'Высота изделия, см','net_weight':'Вес нетто, г'}
 for key,label in names.items():
  if p.get(key):lines.append(label+': '+str(p[key]))
 lines.extend(['','Документ составлен по подтвержденным параметрам товара.','Не является сертификатом или протоколом испытаний.'])
 pages=[];page=Image.new('RGB',(1240,1754),'white');draw=ImageDraw.Draw(page);y=85
 for line in lines:
  words=line.split();wrapped=''
  for word in words+['']:
   trial=(wrapped+' '+word).strip()
   if wrapped and (not word or draw.textlength(trial,font=font)>1070):
    if y>1630:pages.append(page);page=Image.new('RGB',(1240,1754),'white');draw=ImageDraw.Draw(page);y=85
    draw.text((85,y),wrapped,font=font,fill='black');y+=42;wrapped=word
   else:wrapped=trial
  y+=18
 pages.append(page);path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);pages[0].save(path,'PDF',resolution=150,save_all=True,append_images=pages[1:])
 for page in pages:page.close()
 return path

# Inline references are deliberately separate from submitted official values.
def is_pdf(field):
 return 'pdf' in (field.get('name_ru') or field.get('name','')).casefold()

def inline_references(bundle):
 result={};state=bundle.get('attribute_draft') or {};current=state.get('values') or {};decisions=bundle.get('reference_decisions') or {}
 from attribute_service import source_fingerprint
 source=source_fingerprint(bundle)
 for proposal in proposals(bundle):
  if proposal['kind']=='pdf' or current.get(proposal['key']) or proposal['key'] in (state.get('manual_keys') or []):continue
  if (decisions.get(proposal['key']) or {}).get('source')==source:continue
  row=dict(proposal)
  row['display']=row['suggested'] or ('待核实标记要求' if row['kind']=='marking' else '待补充依据')
  result[row['key']]=row
 return result
