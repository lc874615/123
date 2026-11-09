"""Track business changes without silently regenerating approved assets."""
import copy
from decimal import Decimal,InvalidOperation
VISUAL={'name','color','size','quantity','material','accessory_material','length','width','height','assembly','extra'}
COPY=VISUAL|{'net_weight','pack_length','pack_width','pack_height','pack_weight','origin'}

def legacy_canonical(key,value):
 text=str(value or '').strip().casefold()
 if key=='color' and not any(s in text for s in ('座面','椅腿','框架',':','：')):
  from prefill_rules import color_values
  colors=color_values(text)
  if colors:return ','.join(sorted(c.casefold().replace('ё','е') for c in colors))
 if key in ('material','accessory_material','assembly'):
  from prefill_rules import translate
  translated=translate(text)
  if translated:text=translated.casefold().replace('ё','е')
 if key in ('quantity','length','width','height','net_weight','pack_length','pack_width','pack_height','pack_weight'):
  try:return str(Decimal(text).normalize())
  except InvalidOperation:return text
 aliases={'金色':'золотой','红色':'красный','浅灰色':'светло-серый','聚丙烯':'полипропилен','纸板':'картон','金属':'металл','塑料':'пластик'}
 return aliases.get(text,text)

def canonical(key,value):
 if key in ('material','accessory_material'):
  from prefill_rules import split,translate
  tokens=split(value)
  translated=[translate(token) for token in tokens]
  if tokens and all(translated):return '；'.join(sorted(set(' '.join(token.casefold().replace('ё','е').split()) for token in translated)))
 if key=='origin':
  text=str(value or '').strip().casefold()
  if text in ('中国','китай','china','cn'):return 'китай'
 return legacy_canonical(key,value)

def differs(a,b,keys):return any(canonical(k,a.get(k))!=canonical(k,b.get(k)) for k in keys)

def mark_changes(before,after):
 changed=set()
 for old,new in zip(before,after):
  a=old.get('variant_parameters') or {};b=new.get('variant_parameters') or {}
  changed.update(k for k in COPY if canonical(k,a.get(k))!=canonical(k,b.get(k)))
  if changed and old.get('images') and not new.get('asset_basis'):new['asset_basis']=copy.deepcopy(a)
 if not changed:return
 visual=bool(changed&VISUAL)
 for old,new in zip(before,after):
  if old.get('images'):new.setdefault('asset_basis',copy.deepcopy(old.get('variant_parameters') or {}))
 visual=any(differs(b.get('asset_basis') or {},b.get('variant_parameters') or {},VISUAL) for b in after if b.get('images'))
 for old,new in zip(before,after):
  if not old.get('images'):continue
  basis=new.setdefault('asset_basis',copy.deepcopy(old.get('variant_parameters') or {}));p=new.get('variant_parameters') or {}
  own=differs(basis,p,VISUAL)
  prior=new.get('asset_review') or {}
  new['asset_review']={'main':own,'gallery':visual,'copy':True,'fields':sorted(set(prior.get('fields') or [])|changed),'message':'商品参数已改变；请核对旧素材，手动启动更新，不会自动重新作图'}

def pending(bundle):
 state=bundle.get('asset_review') or {}
 return bool(bundle.get('image_regeneration_jobs') or bundle.get('regeneration_pending') or any(state.get(k) for k in ('main','gallery','copy')))

def blocking_reason(bundle):
 if bundle.get('image_regeneration_jobs'):return '图片重做仍在生成或采集中，请等待自动替换完成'
 review=bundle.get('asset_review') or {};validation=bundle.get('asset_validation') or {}
 if bundle.get('regeneration_pending') or review.get('main') or review.get('gallery'):
  changes=list(dict.fromkeys(validation.get('main_changes',[])+validation.get('gallery_changes',[])))
  if not changes:
   from asset_reconcile import LABELS
   changes=[LABELS.get(k,k) for k in review.get('fields',[]) if k in VISUAL]
  return '素材待更新：图片参数待核对'+('（'+'、'.join(changes)+'）' if changes else '')+'；图片无误可点击预览底部“图片无误，沿用本组”；确需改图时到图片视频页手动重做'
 if review.get('copy'):return '整组文案待同步/更新；可点击“保存并同步全组文案”；已有完整文案提交时自动沿用，缺失时再自动补全，无需重新作图'
 return ''
