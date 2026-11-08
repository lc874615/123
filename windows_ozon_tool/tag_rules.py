"""Ozon hashtag text: space-separated #tokens, letters/digits/underscore only."""
import re,unicodedata

def normalize_tags(value):
 entries=value if isinstance(value,list) else [value] if isinstance(value,str) else []
 result=[];seen=set()
 for entry in entries:
  if not isinstance(entry,str):continue
  entry=unicodedata.normalize('NFKC',entry)
  for segment in re.split(r'[,;；，\n]+',entry):
   pieces=segment.split('#') if '#' in segment else [segment]
   for piece in pieces:
    word=''.join(c if c.isalpha() or c.isdecimal() or c=='_' else '_' for c in piece.strip())
    word=re.sub('_+','_',word).strip('_')[:29].rstrip('_')
    if not word:continue
    tag='#'+word
    if tag.casefold() not in seen:result.append(tag);seen.add(tag.casefold())
    if len(result)>=30:return result
 return result

def is_tag_field(field):
 name=(field.get('name_ru') or field.get('name','')).casefold().replace('#','').strip()
 return field.get('id')!=22390 and (field.get('id')==23171 or name in ('хэштеги','хештеги','主题标签','标签'))

def is_series_field(field):
 name=(field.get('name_ru') or field.get('name','')).casefold()
 return field.get('id')!=23171 and (field.get('id')==22390 or 'объединить в похожие' in name or 'название серии' in name or '组合成类似' in name)
