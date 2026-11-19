"""All-variant original hero references for shared details, within eight attachments."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw,ImageFont
from pricing_service import read

def collect(store,task,limit=8,pack=True):
 leader=task.get('copy_leader',task['sku']);group=[t for t in store.tasks if t.get('set_mode') and t.get('state')!='cancelled' and t.get('copy_leader',t['sku'])==leader]
 refs=[];variants=[];root=(store.folder/'products').resolve()
 for row in group:
  path=root/row['sku']/'listing_bundle.json';b=read(path) if path.exists() else {}
  variants.append({'sku':row['sku'],'facts':b.get('facts',row.get('facts','')),'variant_parameters':b.get('variant_parameters',row.get('variant_parameters') or {})})
  own=row.get('main_references') or [r for r in row.get('references') or [] if r.get('purpose','variant_main')=='variant_main']
  if not own and len(group)>1:raise ValueError(row['sku']+'：缺少变体主图原始参考，不会遗漏该变体继续生成')
  refs.extend(dict(r,sku=row['sku'],purpose='shared_variant') for r in own)
  if row['sku']==leader:refs.extend(dict(r,sku=row['sku'],purpose='shared_detail') for r in row.get('detail_references') or [])
 valid=[];seen=set()
 for ref in refs:
  p=Path(ref['path']).resolve()
  try:p.relative_to(root)
  except ValueError:raise ValueError('全组原图不在商品资料目录内') from None
  if not any(x in p.parts for x in ('references','shared_references')):raise ValueError('全组外观必须使用原始参考图')
  raw=p.read_bytes();digest=hashlib.sha256(raw).hexdigest()
  # Same photograph may represent multiple SKUs; retain the mapping, not just its hash.
  key=(ref['sku'],ref['purpose'],digest)
  if key in seen:continue
  seen.add(key)
  with Image.open(p) as image:image.verify();fmt=image.format
  mime={'PNG':'image/png','JPEG':'image/jpeg','WEBP':'image/webp'}.get(fmt)
  if not mime:raise ValueError('全组原图仅支持PNG/JPG/WEBP')
  valid.append(dict(ref,path=str(p),mime=mime,name=ref['sku']+'_'+p.name))
 return (pack_sources(store,task,valid,limit) if pack else valid),variants


def pack_sources(store,task,references,limit=8):
 """Input-only originals. Preserve mappings and all source hashes, never truncate."""
 root=(store.folder/'products').resolve();valid=[];seen=set()
 for ref in references:
  p=Path(ref.get('path','')).resolve()
  try:parts=p.relative_to(root).parts
  except ValueError:raise ValueError('原始参考不在商品资料目录内') from None
  if len(parts)<3 or parts[1] not in ('references','shared_references'):raise ValueError('作图只允许主图/共用详情原始参考，不能使用AI成图或旧索引页')
  raw=p.read_bytes()
  if len(raw)>3*1024*1024:raise ValueError('单张原始参考超过3MB，请先处理原图')
  with Image.open(p) as image:image.verify();fmt=image.format
  mime={'PNG':'image/png','JPEG':'image/jpeg','WEBP':'image/webp'}.get(fmt)
  if not mime:raise ValueError('原始参考仅支持PNG/JPG/WEBP')
  digest=hashlib.sha256(raw).hexdigest();key=(ref.get('sku'),ref.get('purpose'),digest)
  if key in seen:continue
  seen.add(key);valid.append({**ref,'path':str(p),'mime':mime,'reference_sha256':digest})
 # Add readable regions only within the existing attachment/index budget.
 # Preserve up to two current-variant originals in full when capacity permits.
 from reference_readability import detail_regions
 reserved=min(2,sum(r.get('purpose')=='variant_main' for r in valid))
 capacity=reserved+4*(limit-reserved)
 budget=min(12,max(0,capacity-len(valid)))
 if budget:valid.extend(detail_regions(store,task,valid,budget))
 if len(valid)<=limit:return valid
 # Prefer full-resolution current-variant originals. Each remaining input sheet
 # has at most four images, rather than sixteen tiny unreadable thumbnails.
 protected=[r for r in valid if r.get('purpose')=='variant_main'];others=[r for r in valid if r.get('purpose')!='variant_main']
 keep=next((k for k in range(min(len(protected),limit),-1,-1) if k+(len(valid)-k+3)//4<=limit),None)
 if keep is None:raise ValueError('原始资料超过清晰输入容量，请拆分商品组；不会压成小缩略图或遗漏参考')
 direct=protected[:keep];remaining=protected[keep:]+others;folder=root/task['sku']/'group_reference_sheets';folder.mkdir(parents=True,exist_ok=True);sheets=[]
 try:font=ImageFont.truetype('DejaVuSans.ttf',26)
 except OSError:font=ImageFont.load_default()
 for offset in range(0,len(remaining),4):
  batch=remaining[offset:offset+4];columns=min(2,len(batch));canvas=Image.new('RGB',(1200*columns,1640*((len(batch)+columns-1)//columns)),'white');draw=ImageDraw.Draw(canvas)
  mapping=[]
  for i,r in enumerate(batch):
   x=i%columns*1200;y=i//columns*1640
   with Image.open(r['path']) as image:
    fit=ImageOps.contain(ImageOps.exif_transpose(image).convert('RGB'),(1160,1560));canvas.paste(fit,(x+(1200-fit.width)//2,y+(1560-fit.height)//2))
   draw.text((x+18,y+1580),str(i+1)+': '+str(r.get('sku','')).encode('ascii','replace').decode(),font=font,fill='black')
   mapping.append({'cell':i+1,'sku':r.get('sku'),'purpose':r.get('purpose'),'source_name':r.get('name'),'path':r['path'],'sha256':r['reference_sha256'],**{k:r[k] for k in ('source_path','source_sha256','source_sku','source_name','region','crop_box') if k in r}})
  digest=hashlib.sha256(canvas.tobytes()+json.dumps(mapping,sort_keys=True).encode()).hexdigest();path=folder/(digest+'.jpg')
  for quality in (92,84,76,68):
   canvas.save(path,quality=quality)
   if path.stat().st_size<=3*1024*1024:break
  else:raise ValueError('原始资料索引过大，未降低尺寸强行上传；请拆分商品组')
  canvas.close();sheets.append({'path':str(path),'name':'original_sources_'+str(offset//4+1)+'.jpg','mime':'image/jpeg','purpose':'shared_reference_sheet','sku':task['sku'],'cells':mapping,'reference_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
 return direct+sheets


def compile_references(store,task,scope):
 if scope=='shared':return collect(store,task)[0]
 if scope=='full':
  refs,_=collect(store,task,pack=False)
  refs=[{**r,'purpose':'variant_main' if r['sku']==task['sku'] and r['purpose']=='shared_variant' else r['purpose']} for r in refs]
  refs.sort(key=lambda r:r['purpose']!='variant_main')
 else:
  from image_prompts import main_detail_references
  refs=[{**r,'name':str(r.get('sku') or task['sku'])+'_'+str(r.get('name','original')),'sku':r.get('sku') or task['sku'],'purpose':'shared_information' if r.get('purpose') in ('shared_information','shared_gallery','shared_detail') else 'variant_main'} for r in main_detail_references(task,store.tasks)]
 return pack_sources(store,task,refs)


def verify_sources(references):
 for ref in references:
  checks=[{'path':ref.get('path'),'sha256':ref.get('reference_sha256')}]+[{'path':c.get('path'),'sha256':c.get('sha256')} for c in ref.get('cells') or []]
  checks.extend({'path':r.get('source_path'),'sha256':r.get('source_sha256')} for r in [ref]+list(ref.get('cells') or []) if r.get('source_path'))
  for row in checks:
   if row['sha256'] and (not Path(row['path']).is_file() or hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()!=row['sha256']):raise ValueError('原始参考图已变化，未发送或替换；请停止任务后重新启动')

INFO='【全组原始资料】逐一核对本次全部变体的主图原始参考与共用详情原始参考。只能从这些图片读取商品事实，类目只决定设计方向；参数表、竞品、已生成图片与历史对话均不构成证据。共用图按主题选择真实选项，差异必须分别标注，不将不同变体结构、尺寸、材质合并。原始索引格只是输入资料，不能当成整套输出海报；格号、货号、文件名不印入成品。'
