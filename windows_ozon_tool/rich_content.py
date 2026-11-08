"""Ozon rich-content v0.3: one full-width image roll per variant, no assets altered."""
import json
from urllib.parse import urlsplit

def is_rich_field(field):
 return field.get('id')==11254 or 'rich-контент' in (field.get('name_ru') or field.get('name','')).casefold() or 'rich-content' in (field.get('name_ru') or field.get('name','')).casefold()

def generate(bundle):
 rows=bundle.get('images') or []
 if len(rows)!=8 or [r.get('order') for r in rows]!=list(range(1,9)):return None
 blocks=[]
 for n,row in enumerate(rows):
  if row.get('role')!=('primary' if n==0 else 'gallery'):return None
  url=row.get('https_url');parsed=urlsplit(url or '')
  if parsed.scheme!='https' or not parsed.hostname or parsed.query or parsed.fragment or parsed.username or not parsed.path.casefold().endswith(('.jpg','.jpeg','.png')):return None
  blocks.append({'img':{'src':url,'srcMobile':url,'alt':('Главное изображение' if n==0 else 'Изображение товара '+str(n+1)),'position':'width_full','positionMobile':'width_full'},'imgLink':''})
 return json.dumps({'content':[{'widgetName':'raShowcase','type':'roll','blocks':blocks}],'version':0.3},ensure_ascii=False,separators=(',',':'))
