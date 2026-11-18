"""Category-schema facts: exact declared labels, typed units and original-photo evidence."""
import hashlib,json,re
from decimal import Decimal,InvalidOperation
from pathlib import Path
from prefill_rules import basis,translate,split
UNITS={}
for family,rows in {
 'length':{'mm':('1','мм','毫米'),'cm':('10','см','厘米'),'m':('1000','м','米')},
 'mass':{'mg':('0.001','мг','毫克'),'g':('1','г','克'),'kg':('1000','кг','公斤','千克')},
 'volume':{'ml':('1','мл','毫升'),'l':('1000','л','升')},
 'power':{'w':('1','вт','瓦'),'kw':('1000','квт','千瓦')},
 'voltage':{'v':('1','в','伏','伏特')},'frequency':{'hz':('1','гц','赫兹')},
 'count':{'pcs':('1','шт','шт.','件','个')},'percent':{'%':('1','％')},
}.items():
 for token,data in rows.items():
  for alias in (token,)+data[1:]:UNITS[alias]=(family,Decimal(data[0]))
BLOCKED=re.compile(r'бренд|brand|штрихкод|barcode|сертифик|декларац|тн\s*вэд|маркиров|гаранти|认证|条码|海关|保修',re.I)
NUMBER_TYPES={'decimal','integer','number','float','int','double'}
def key(field):return str(field.get('attribute_complex_id') or 0)+':'+str(field['id'])
def allowed(field):
 return not field.get('attribute_complex_id') and int(field.get('id',0)) not in (85,9048,4191,8229,23171,21841,21837,21845) and not BLOCKED.search(str(field.get('name',''))+' '+str(field.get('name_ru','')))
def schema(bundle):
 fields=[{k:f.get(k) for k in ('id','attribute_complex_id','name','name_ru','type','dictionary_id','is_required','is_collection','max_value_count')} for f in (bundle.get('attribute_draft') or {}).get('fields',[]) if allowed(f)]
 category=bundle.get('category') or {};context=[category.get('description_category_id'),category.get('type_id')]
 digest=hashlib.sha256(json.dumps([context,fields],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
 return fields,digest

def unit(field):
 for label in (field.get('name_ru'),field.get('name')):
  tail=re.search(r'[,，(（]\s*([^,，()（）]+)[)）]?\s*$',str(label or '').lower())
  if tail and tail[1].strip() in UNITS:return tail[1].strip()
 return None

def numeric_field(field):return str(field.get('type','')).lower() in NUMBER_TYPES or bool(unit(field) and not field.get('dictionary_id'))

def normalized(label):
 text=str(label or '').lower().replace('ё','е').strip()
 text=re.sub(r'\s*[,，(（]\s*([^,，()（）]+)[)）]?\s*$',lambda m:'' if m[1].strip() in UNITS else m[0],text)
 return re.sub(r'\s+',' ',text).strip()

def typed(field,raw):
 if isinstance(raw,list):
  if not field.get('is_collection'):return None
  result=[typed({**field,'is_collection':False},v) for v in raw]
  return result if result and all(v is not None for v in result) else None
 text=str(raw or '').strip()
 if not text:return None
 kind=str(field.get('type','')).lower()
 if numeric_field(field):
  match=re.fullmatch(r'([+\-]?\d+(?:[.,]\d+)?)\s*([^\d]*)',text)
  if not match:return None
  try:
   n=Decimal(match[1].replace(',','.'));source=match[2].strip().lower();target=unit(field)
   if source:
    if source not in UNITS or not target or UNITS[source][0]!=UNITS[target][0]:return None
    n=n*UNITS[source][1]/UNITS[target][1]
   if not n.is_finite() or n<0 or kind in ('integer','int') and n!=n.to_integral_value():return None
   return format(n.normalize(),'f')
  except (InvalidOperation,ZeroDivisionError):return None
 if kind in ('boolean','bool'):
  return {'是':'true','有':'true','да':'true','true':'true','否':'false','无':'false','нет':'false','false':'false'}.get(text.casefold())
 if field.get('is_collection'):
  parts=split(text);values=[translate(v) for v in parts]
  return values if values and all(values) else None
 return translate(text)

def declared(field,bundle):
 labels={normalized(field.get(k)) for k in ('name','name_ru') if field.get(k)}
 extra=(bundle.get('variant_parameters') or {}).get('extra','')
 candidates=[]
 for line in re.split(r'[;；\n]+',str(extra)):
  m=re.match(r'\s*([^:：=]+)\s*[:：=]\s*(.+)',line)
  if m and normalized(m[1]) in labels:candidates.append(typed(field,m[2]))
 values=[v for v in candidates if v is not None]
 if not values or any(v!=values[0] for v in values):return None
 return values[0]

def record(field,bundle):
 observations=bundle.get('reference_category_attributes') or {};fields,digest=schema(bundle)
 if observations.get('schema_basis')!=digest or observations.get('basis')!=basis(bundle.get('variant_parameters')):return None
 for ref in observations.get('references',[]):
  try:s=Path(ref['path']).stat()
  except OSError:return None
  if [s.st_size,s.st_mtime_ns]!=ref.get('stat'):return None
 return (observations.get('records') or {}).get(key(field))

def value_for(field,bundle):
 if not allowed(field):return None
 # Declared structured cells always precede inferred/extra category observations.
 from group_service import binding
 from prefill_rules import field_kind,explicit
 p=bundle.get('variant_parameters') or {};link=binding(field);kind=field_kind(field)
 if link and str(p.get(link[0],'')).strip():return None
 if kind and explicit(bundle,kind):return None
 if kind in ('frame_material','supply_form') and p.get('material' if kind=='frame_material' else 'assembly'):return None
 if normalized(field.get('name_ru') or field.get('name')) in ('размер','размер изделия','规格','规格/型号') and p.get('size'):return None
 value=declared(field,bundle)
 if value is not None:return value
 found=record(field,bundle)
 return found.get('value') if found else None

def annotation(field,bundle):
 if value_for(field,bundle) is None:return None
 value=declared(field,bundle)
 if value is not None:return {'suggested':str(value),'kind':'declared_parameter','confidence':'已填补充参数，按官方字段单位换算','evidence':str((bundle.get('variant_parameters') or {}).get('extra',''))[:400],'note':'同名官方字段精确匹配；未知值不推测。'}
 found=record(field,bundle)
 if found:return {'suggested':str(found['value']),'kind':'reference_image','confidence':'当前类目原始参考图读取','evidence':found['evidence'],'note':'保留原图依据，手动修改优先；字典字段仍需匹配官方选项。'}
 return None
