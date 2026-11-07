"""Check known material conflicts without confusing the body with a lining."""
import re

TERMS={'pp':r'полипропилен|聚丙烯|\bpp\b','paper':r'картон|бумаг|纸板|纸材|纸张'}
def kinds(text):
 return {key for key,pattern in TERMS.items() if re.search(pattern,text or '',re.I)}

def materials(data):
 params=data.get('variant_parameters') or {}
 body=params.get('material','');accessory=params.get('accessory_material','')
 # Older bundles retain labelled form values in facts, including before structured variants existed.
 facts=data.get('facts','')
 if not body:
  m=re.search(r'(?:^|[；;\n])\s*(?:主体材质|材质)\s*[:：]\s*([^；;\n]+)',facts)
  if m:body=m.group(1)
 if not accessory:
  m=re.search(r'(?:^|[；;\n])\s*(?:配件/内衬材质|内衬材质|配件材质)\s*[:：]\s*([^；;\n]+)',facts)
  if m:accessory=m.group(1)
 return kinds(body),kinds(accessory)

ROLE=re.compile(r'(?P<body>корпус\w*|основн\w*\s+материал\w*|материал\s+изделия|主体材质)|(?P<accessory>подклад\w*|вставк\w*|внутренн\w*\s+сло\w*|内衬|配件)',re.I)
def conflict(data,value):
 body,accessory=materials(data)
 for variant in data.get('group_variants',[]):
  other_body,other_accessory=materials(variant);body|=other_body;accessory|=other_accessory
 allowed=body|accessory
 if not allowed:return None
 text=value.get('title_ru','')+'\n'+value.get('description_ru','')
 # Unscoped mentions are valid if that material is present anywhere in the actual product.
 if kinds(text)-allowed:return '文案出现商品资料未包含的材质，请核对主体和配件/内衬'
 for sentence in re.split(r'[.!?。；;\n]',text):
  roles=list(ROLE.finditer(sentence))
  for i,role in enumerate(roles):
   claim=sentence[role.end():roles[i+1].start() if i+1<len(roles) else len(sentence)]
   expected=body if role.lastgroup=='body' else accessory
   if expected and kinds(claim)-expected:
    return ('主体材质' if role.lastgroup=='body' else '配件/内衬材质')+'与商品参数冲突'
 return None

def validate(data,value):
 issue=conflict(data,value)
 if issue:raise ValueError('材质冲突：'+issue)
