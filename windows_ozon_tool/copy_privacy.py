"""Keep internal offer identifiers out of customer-facing copy, retaining JSON metadata."""
import copy,re

def identifiers(context):
 found=set()
 for row in [context]+list(context.get('group_variants') or []):
  for key in ('sku','offer_id','base_article'):
   value=str(row.get(key) or '').strip()
   if value:found.add(value)
 for value in list(found):
  base=re.sub(r'\([1-9]\d*\)$','',value)
  if base!=value:found.add(base)
 return found

def clean(value,context):
 result=copy.deepcopy(value);ids=identifiers(context);standalone=set();labelled=set(ids)
 for identifier in ids:
  distinctive=bool(re.search(r'[-_(]',identifier) or re.search(r'[A-Za-zА-Яа-я]',identifier) and re.search(r'\d',identifier) or identifier.isdigit() and len(identifier)>=6)
  if distinctive:
   standalone.add(re.escape(identifier))
   tag=re.sub(r'[^\w]+','_',identifier,flags=re.U).strip('_')
   if tag:standalone.add(re.escape(tag))
 if not ids:return result
 label=r'(?:货号|卖家代码|SKU|offer[_ ]?id|артикул|код\s+продавца)\s*[:：#—-]?\s*'
 labelled_pattern=re.compile(label+'(?:'+'|'.join(re.escape(i) for i in sorted(labelled,key=len,reverse=True))+r')(?![\w])',re.I)
 raw_pattern=re.compile(r'(?<![\w])(?:'+'|'.join(sorted(standalone,key=len,reverse=True))+r')(?![\w])',re.I) if standalone else None
 def text(raw):
  raw=labelled_pattern.sub('',str(raw or ''))
  if raw_pattern:raw=raw_pattern.sub('',raw)
  lines=[]
  for line in raw.splitlines():
   line=re.sub(r'[ \t]{2,}',' ',line).strip();line=re.sub(r'^[\s:：;,，；—–-]+','',line).strip()
   if line in ('#','•','-','—','()','[]'):line=''
   lines.append(line)
  return re.sub(r'\n{3,}','\n\n','\n'.join(lines)).strip()
 for key in ('title_ru','description_ru'):
  if isinstance(result.get(key),str):result[key]=text(result[key])
 if isinstance(result.get('tags_ru'),list):
  aliases=[re.sub(r'[^\w]+','_',i,flags=re.U).strip('_') for i in ids if re.escape(i) in standalone]
  def private_tag(raw):
   tag=re.sub(r'[^\w]+','_',str(raw).lstrip('#'),flags=re.U).strip('_')
   return any(re.search(r'(?:^|_)'+re.escape(i)+r'(?:_|$)',tag,re.I) for i in aliases if i)
  result['tags_ru']=[v for raw in result['tags_ru'] if not private_tag(raw) and (v:=text(raw)) and v!='#']
 return result
