"""Concrete Ozon import previews; no product-write API is called here."""
import hashlib,json,time,urllib.parse
from decimal import Decimal,ROUND_CEILING
from pathlib import Path
from attribute_service import category_key,field_key,validate_values,source_fingerprint,review_hash
from asset_audit import inspect
from listing_bundle import copy_complete,copy_hash
from pricing_service import read,write

from assisted_fields import is_pdf
from tag_rules import is_tag_field,is_series_field,normalize_tags
VIDEO_IDS={21841,21837,21845}
def attribute_errors(bundle):
 state=bundle.get('attribute_draft') or {};errors=[]
 try:
  if state.get('category_key')!=list(category_key(bundle)):errors.append('属性尚未按当前类目读取')
 except ValueError as exc:errors.append(str(exc))
 if not state.get('fields'):return errors+['请读取官方必填属性']
 if not 0<=time.time()-state.get('fetched_at',0)<=86400:errors.append('官方属性缓存已超过24小时，请刷新')
 if state.get('source_fingerprint')!=source_fingerprint(bundle):errors.append('参数或文案已变化，请重新读取并核对属性')
 for field in state['fields']:
  if is_pdf(field):
   if field.get('is_required'):errors.append('平台将PDF列为必填；本工具已按要求关闭PDF，请确认类目或在平台补充真实材料')
   continue
  if field['id'] in VIDEO_IDS or field['id']==8229:continue
  values=(state.get('values') or {}).get(field_key(field),[])
  if is_series_field(field) and any(len(v.get('value',''))>255 for v in values):errors.append('组合成类似产品的系列名称不得超过255字符')
  if is_tag_field(field):
   text=' '.join(v.get('value','') for v in values)
   if text!=' '.join(normalize_tags(text)):errors.append('主题标签格式不合规，请刷新参数自动修正')
  from rich_content import is_rich_field,generate
  if is_rich_field(field):
   expected=generate(bundle)
   if not expected or values!=[{'value':expected}]:errors.append('富内容JSON须使用本变体最新的8张已托管图片，请刷新API参数')
  if not values:
   if field_key(field) in (state.get('migration_pending') or {}):errors.append('属性原值待按新类目匹配：'+field.get('name',str(field['id'])))
   if field.get('is_required'):errors.append('必填属性缺失：'+field.get('name',str(field['id'])))
  else:
   if field['id']==85 or (field.get('name_ru') or '').lower().startswith('бренд') or field.get('name')=='品牌':
    if any(str(v.get('value','')).casefold() not in ('нет бренда','без бренда','无品牌','no brand') for v in values):errors.append('本组品牌固定无品牌，请选择官方的无品牌选项')
   try:validate_values(field,values)
   except ValueError as exc:errors.append(field.get('name',str(field['id']))+'：'+str(exc))
 return errors

def public_url(url):
 if not isinstance(url,str):return False
 p=urllib.parse.urlsplit(url)
 return p.scheme=='https' and bool(p.hostname) and not p.username and not p.password and not p.query and not p.fragment

def build_item(folder,bundle):
 folder=Path(folder);errors=attribute_errors(bundle)
 from asset_state import pending
 if pending(bundle):
  from asset_state import blocking_reason
  errors.append(blocking_reason(bundle))
 if bundle.get('manual_price') and (bundle.get('manual_pricing') or {}).get('valid') is False:errors.append('手动售价没有适用的费用/物流方案：'+str(bundle['manual_pricing'].get('message','')))
 tasks=folder.parent.parent/'tasks.json'
 if tasks.exists() and not any(t.get('sku')==bundle.get('sku') and t.get('state')!='cancelled' for t in read(tasks)):errors.append('该任务已删除或取消，请重新打开整组草稿')
 category=bundle.get('category') or {};state=bundle.get('attribute_draft') or {};p=bundle.get('variant_parameters') or {};settings=bundle.get('export_settings') or {}
 if not category.get('confirmed'):errors.append('类目待卖家确认')
 if not state.get('confirmed') or state.get('confirmed_values_hash')!=review_hash(state):errors.append('属性内容待卖家确认')
 if not bundle.get('pricing_confirmed_fingerprint') or bundle.get('pricing_confirmed_fingerprint')!=bundle.get('pricing_fingerprint') or str(bundle.get('pricing_confirmed_price', (bundle.get('auto_pricing') or {}).get('price_cny')))!=str(bundle.get('price_cny')):errors.append('售价待确认或已变化')
 if settings.get('currency_code')!='CNY' or not settings.get('currency_confirmed'):errors.append('请确认店铺币种为CNY')
 if settings.get('vat')!='0':errors.append('实际增值税率应按你的固定规则填写0')
 if copy_complete(bundle.get('copy')):
  from material_guard import validate as validate_material
  try:validate_material(bundle,bundle['copy'])
  except ValueError as exc:errors.append(str(exc))
 if not copy_complete(bundle.get('copy')):errors.append('俄文标题、简介和标签不完整')
 else:
  description=bundle['copy']['description_ru'];tags=' '.join(normalize_tags(bundle['copy']['tags_ru']));description_ok=False;tags_ok=not tags
  for field in state.get('fields',[]):
   values=(state.get('values') or {}).get(field_key(field)) or [];text=' '.join(v.get('value','') for v in values)
   if field['id']==4191 or (field.get('name_ru') or '').lower() in ('аннотация','описание товара'):description_ok=text==description
   if is_tag_field(field):tags_ok=text==tags
  if not description_ok:errors.append('俄文简介未完整对应到当前类目的简介属性')
  if not tags_ok:errors.append('俄文标签未完整对应到当前类目的标签属性')
 offer=bundle.get('offer_id') or bundle.get('sku','')
 if not offer or len(offer)>50:errors.append('上架货号为空或超过50字符')
 audit=inspect(folder)
 if not audit['verified']:errors.append('本地8图校验失败：'+audit['reason'])
 images=bundle.get('images') or [];hosting=bundle.get('hosting') or {}
 if len(images)!=8 or [i.get('order') for i in images]!=list(range(1,9)) or any(i.get('role')!=('primary' if n==0 else 'gallery') for n,i in enumerate(images)):errors.append('主图/详情图顺序异常')
 if hosting.get('state')!='done' or len(images)!=8 or any(not public_url(i.get('https_url')) or i.get('hosting_sha256')!=i.get('sha256') or i.get('hosting_target')!=hosting.get('target') or time.time()-i.get('hosting_verified_at',0)>86400 for i in images):errors.append('8张图片COS链接尚未全部校验')
 if any(urllib.parse.urlsplit(i.get('https_url') or '').path.lower().endswith('.webp') for i in images):errors.append('Ozon图片导入要求JPG/PNG，请先转换WEBP并重新校验托管')
 rows=read(folder/'image_manifest.json') if (folder/'image_manifest.json').exists() else []
 if audit['verified'] and (len(rows)!=len(images) or any(i.get('sha256')!=r.get('sha256') for i,r in zip(images,rows))):errors.append('草稿图片与本地生成图清单不一致')
 video=bundle.get('video') or {};video_path=folder/'video'/'product_8s.mp4'
 if (bundle.get('video_hosting') or {}).get('state')!='done' or not public_url(video.get('https_url')) or time.time()-video.get('hosting_verified_at',0)>86400:errors.append('8秒视频COS链接尚未完成')
 elif not video_path.is_file() or hashlib.sha256(video_path.read_bytes()).hexdigest()!=video.get('sha256') or video.get('image_hashes')!=[i.get('sha256') for i in images]:errors.append('视频或生成图已变化，请重新校验视频链接')
 try:
  price=Decimal(str(bundle.get('price_cny')))
  if not price.is_finite() or price<=0:raise ValueError()
 except Exception:errors.append('售价须为有效正数');price=Decimal(0)
 package={}
 try:
  for source,key in [('pack_length','depth'),('pack_width','width'),('pack_height','height')]:
   value=Decimal(str(p.get(source)))*10
   if not value.is_finite() or value<=0 or value!=value.to_integral_value():raise ValueError()
   package[key]=int(value)
  weight=Decimal(str(p.get('pack_weight')))
  if not weight.is_finite() or weight<=0:raise ValueError()
  package['weight']=int(weight.to_integral_value(rounding=ROUND_CEILING))
 except Exception:errors.append('包装尺寸/重量缺失或无效；长宽高按厘米填写，尺寸精确到毫米')
 if errors:return None,list(dict.fromkeys(errors))
 attributes=[];groups={}
 for field in state['fields']:
  if is_pdf(field) or field['id'] in VIDEO_IDS or field['id']==8229:continue
  values=(state.get('values') or {}).get(field_key(field))
  if not values:continue
  complex_id=int(field.get('attribute_complex_id') or 0);row={'id':int(field['id']),'complex_id':complex_id,'values':values}
  if complex_id:groups.setdefault(complex_id,[]).append(row)
  else:attributes.append(row)
 # Ozon /v3/product/import documents this exact complex group for a product video.
 groups.setdefault(100001,[]).extend([{'id':21841,'complex_id':100001,'values':[{'value':video['https_url']}]},{'id':21837,'complex_id':100001,'values':[{'value':bundle['copy']['title_ru'][:100]}]}])
 item={'offer_id':offer,'name':bundle['copy']['title_ru'],'description_category_id':category['description_category_id'],'type_id':category['type_id'],'price':str(price),'currency_code':'CNY','vat':settings['vat'],'images':[i['https_url'] for i in images],'attributes':attributes,'complex_attributes':[{'attributes':groups[key]} for key in sorted(groups)],'dimension_unit':'mm','weight_unit':'g',**package}
 from listing_prices import listing_prices
 try:prices=listing_prices(bundle)
 except Exception:return None,['售价或成本缺失/无效']
 item.update(price=prices['price'],old_price=prices['old_price'])
 return item,[]

def export_preview(folders,output,lock=None):
 from contextlib import nullcontext
 items=[];report=[];titles=set();copy_hashes=set();checksums=[];models=set()
 with lock if lock is not None else nullcontext():
  for folder in folders:
   folder=Path(folder)
   try:
    bundle=read(folder/'listing_bundle.json')
    if not isinstance(bundle,dict):raise ValueError('草稿不是对象')
   except (OSError,ValueError):
    report.append({'offer_id':folder.name,'ready':False,'missing':['商品草稿不可读，原文件保留']});continue
   try:item,errors=build_item(folder,bundle)
   except (OSError,ValueError,KeyError,TypeError,AttributeError):item=None;errors=['本地草稿或素材结构异常，请检查该货号']
   report.append({'offer_id':bundle.get('offer_id',bundle.get('sku')),'ready':not errors,'missing':errors})
   if item:
    items.append(item);titles.add(item['name']);copy_hashes.add(copy_hash(bundle['copy']))
    for row in item['attributes']:
     if row['id']==9048:models.add(json.dumps(row['values'],ensure_ascii=False,sort_keys=True))
    checksums.append({'bundle_file':str((folder/'listing_bundle.json').resolve()),'sha256':hashlib.sha256((folder/'listing_bundle.json').read_bytes()).hexdigest()})
  if len(items)>100:report.append({'offer_id':'整组','ready':False,'missing':['超过100变体，需拆批导出']})
  if len(models)>1:report.append({'offer_id':'整组','ready':False,'missing':['同组型号/合并属性不一致，请核对各变体']})
  if len(titles)>1 or len(copy_hashes)>1:report.append({'offer_id':'整组','ready':False,'missing':['同组标题、简介或标签不一致，请先同步共用文案']})
  if not report:report.append({'offer_id':'整组','ready':False,'missing':['当前没有未取消且可预览的变体任务']})
  ready=all(r['ready'] for r in report)
  if ready:
   from publish import validate
   try:validate({'items':items})
   except (ValueError,TypeError,KeyError):report.append({'offer_id':'整组','ready':False,'missing':['提交载荷结构检查未通过，请核对属性、单位和类目ID']});ready=False
  output=Path(output);output.mkdir(parents=True,exist_ok=True)
  review={'ready':ready,'submitted':False,'items':report,'checked_at':time.time(),'note':'仅本地提交预览；视频是否被平台抓取及变体是否合并仍须实际导入后核验'}
  payload=output/'ozon_import_preview.json'
  if ready:
   write(payload,{'items':items});review['payload_sha256']=hashlib.sha256(payload.read_bytes()).hexdigest();review['source_checksums']=checksums
  elif payload.exists():payload.unlink() # Prevent an old successful preview being mistaken for this failed validation.
  write(output/'review_report.json',review)
 return review

def validate_saved_preview(payload_path,payload):
 """Reject stale app-generated exports before an explicitly invoked CLI submission."""
 payload_path=Path(payload_path);report=read(payload_path.parent/'review_report.json')
 if not report.get('ready') or time.time()-report.get('checked_at',0)>86400:raise ValueError('提交预览已过期或未通过，请在工具中重新导出')
 if hashlib.sha256(payload_path.read_bytes()).hexdigest()!=report.get('payload_sha256'):raise ValueError('载荷已被修改，请在工具中重新核对并导出')
 rebuilt=[]
 for source in report.get('source_checksums',[]):
  path=Path(source['bundle_file'])
  if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:raise ValueError('上架草稿已变化，请重新导出预览')
  item,errors=build_item(path.parent,read(path))
  if errors:raise ValueError(path.parent.name+'：'+'；'.join(errors))
  rebuilt.append(item)
 if not rebuilt or rebuilt!=payload.get('items'):raise ValueError('当前资料与提交预览不一致，请重新导出')
 return True
