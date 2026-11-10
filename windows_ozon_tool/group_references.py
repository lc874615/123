"""All-variant original hero references for shared details, within eight attachments."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw
from pricing_service import read

def collect(store,task,limit=8):
 leader=task.get('copy_leader',task['sku']);group=[t for t in store.tasks if t.get('set_mode') and t.get('state')!='cancelled' and t.get('copy_leader',t['sku'])==leader]
 refs=[];variants=[];root=(store.folder/'products').resolve()
 for row in group:
  path=root/row['sku']/'listing_bundle.json';b=read(path) if path.exists() else {}
  variants.append({'sku':row['sku'],'facts':b.get('facts',row.get('facts','')),'variant_parameters':b.get('variant_parameters',row.get('variant_parameters') or {})})
  own=row.get('main_references') or [r for r in row.get('references') or [] if r.get('purpose','variant_main')=='variant_main']
  if not own and len(group)>1:raise ValueError(row['sku']+'：缺少变体主图原始参考，不会遗漏该变体继续生成')
  if own:refs.append(dict(own[0],sku=row['sku'],purpose='shared_variant'))
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
 if len(valid)>limit:
  # Reference sheets are input evidence only, never generated listing images.
  folder=root/leader/'group_reference_sheets';folder.mkdir(exist_ok=True);sheets=[]
  for offset in range(0,len(valid),16):
   batch=valid[offset:offset+16];canvas=Image.new('RGB',(2400,840*((len(batch)+3)//4)),'white');draw=ImageDraw.Draw(canvas)
   for i,r in enumerate(batch):
    x=i%4*600;y=i//4*840
    with Image.open(r['path']) as image:
     fit=ImageOps.contain(ImageOps.exif_transpose(image).convert('RGB'),(580,780));canvas.paste(fit,(x+(600-fit.width)//2,y+(780-fit.height)//2))
    draw.text((x+12,y+790),str(offset+i+1)+': '+r['sku'].encode('ascii','replace').decode(),fill='black')
   mapping=[{'cell':i+1,'sku':r['sku'],'purpose':r['purpose'],'source_name':r['name']} for i,r in enumerate(batch)]
   digest=hashlib.sha256(canvas.tobytes()+json.dumps(mapping,sort_keys=True).encode()).hexdigest();path=folder/(digest+'.jpg');canvas.save(path,quality=92)
   sheets.append({'path':str(path),'name':'group_originals_'+str(offset//16+1)+'.jpg','mime':'image/jpeg','purpose':'shared_reference_sheet','sku':leader,'cells':mapping})
  valid=sheets
 if len(valid)>limit:raise ValueError('全组参考资料过多，请拆分商品组；不会悄悄遗漏变体原图')
 return valid,variants

INFO='【全组变体资料调用】本次共用详情读取全部在售变体的主图原始参考和最新已填参数；已生成主图只可作为信息索引，不能成为新增商品事实。逐一核对各变体外观、颜色/花型、材质、尺寸、件数及有依据卖点，区分共同信息与选项差异。共用图可按主题选择真实变体或并列标注选项，不把不同变体结构、尺寸或材质合并到同一件商品上。附件若是原始资料索引页，每格仅为输入参考，不是待交付海报；按格号和货号对应实际商品，货号不得印入成品。'
