"""Crop a declared 3x3 original sheet without resizing or redrawing pixels."""
import base64,hashlib,io
from pathlib import Path
from PIL import Image,ImageOps
from pricing_service import write

LAYOUT={'columns':3,'rows':3,'min_tile_width':750,'min_tile_height':1000,'version':1}

def contract(count):
 if count not in (7,8):raise ValueError('拼图只用于7张详情或完整8图')
 return ('【本任务交付方式：只生成一张高分辨率3×3整套拼图】这是最终裁剪母图，不另做逐张下载版。整图3:4，原生像素至少2250×3000，推荐2700×3600或更高；3列3行严格等分，每格均为完整3:4竖版海报。按左到右、上到下放本任务01至'+str(count).zfill(2)+'，剩余格留空。不留外框、行列间隙、阴影分隔、格外标题或序号；所有内容及本格文字安全边距须在各自格内，人物/文字/商品不得跨格。不把白色空白当本格背景补边。只返回这一张原始拼图，可提供同一原图下载链接；不重新排版，不裁切后重绘。实际工具不能输出要求的原生尺寸时明确说明，不用插值放大或标称尺寸冒充原生像素。程序将按固定网格原样裁剪，单格必须至少750×1000。')

def split(raw,count):
 if count not in (7,8):raise ValueError('裁剪数量无效')
 if len(raw)>20*1024*1024:raise ValueError('拼图超过20MB，请提供原始PNG/JPG/WEBP并控制文件大小')
 with Image.open(io.BytesIO(raw)) as im:
  if im.format not in ('PNG','JPEG','WEBP'):raise ValueError('拼图格式不支持')
  im.verify()
 with Image.open(io.BytesIO(raw)) as im:image=ImageOps.exif_transpose(im).convert('RGB')
 width,height=image.size
 if width%3 or height%3:raise ValueError(f'拼图为{width}×{height}，不能精确等分3×3网格；未裁剪或放大，请提供无间隙原图')
 w,h=width//3,height//3
 if w<750 or h<1000:raise ValueError(f'原始拼图仅{width}×{height}，每格{w}×{h}，低于750×1000；已保留原图，未放大冒充清晰成品。需至少2250×3000的原始拼图')
 if w*4!=h*3:raise ValueError(f'拼图每格为{w}×{h}，不符合3:4比例；请提供严格3×3、无间隙和外框的母图')
 values=[];hashes=set()
 for i in range(count):
  x=i%3*w;y=i//3*h;tile=image.crop((x,y,x+w,y+h));pixels=hashlib.sha256(tile.tobytes()).hexdigest()
  if pixels in hashes:raise ValueError('拼图包含重复/空白格，未保存为成品')
  hashes.add(pixels);out=io.BytesIO();tile.save(out,'PNG');values.append(out.getvalue())
 return values,{'width':width,'height':height,'tile_width':w,'tile_height':h,'resized':False}

def accept(store,identifier,encoded):
 task=store.find(identifier)
 if not task.get('sheet_layout'):raise ValueError('该任务未声明整套拼图裁剪模式')
 if store.control.get('paused') or task.get('pause_requested'):raise ValueError('任务已暂停，未裁剪替换现有图片')
 if task['state'] not in ('claimed','sending','waiting','saved'):raise ValueError('当前任务不接受拼图；请先恢复原任务')
 raw=base64.b64decode(encoded,validate=True);digest=hashlib.sha256(raw).hexdigest()
 folder=store.folder/('image_job_staging' if task.get('image_job') else 'contact_sheets')/identifier;folder.mkdir(parents=True,exist_ok=True)
 (folder/(digest+'.source')).write_bytes(raw)
 old=task.get('contact_sheet_sha256')
 if old and old!=digest:raise ValueError('本次拼图与已裁剪母图不同，已有图片保留；不能混用两套拼图')
 count=task.get('expected_images',8);values,info=split(raw,count)
 # Check every crop against originals before writing any result.
 from asset_guard import reject_reference
 for value in values:reject_reference(value,task.get('references') or [])
 task.update(contact_sheet_sha256=digest,contact_sheet_info=info)
 if task.get('image_job'):store.image_jobs.save()
 else:store.save()
 result={}
 for index,value in enumerate(values):result=store.set_result(identifier,index,base64.b64encode(value).decode())
 write(folder/'crop_manifest.json',{'source_sha256':digest,**info,'count':count,'outputs':[hashlib.sha256(v).hexdigest() for v in values]})
 return {**result,'cropped_count':count,'pixels':info}

def plan(task):
 layout=task.get('sheet_layout')
 return {'sheet_layout':layout,'expected_images':task.get('expected_images',8),'delivery_policy':task.get('delivery_policy'),'source_images':1 if layout else task.get('expected_images',8)}

def adopt(store,identifier):
 """Explicit read-only request recovery choice; never create or resend a GPT request."""
 task=store.find(identifier)
 if task.get('expected_images') not in (7,8):raise ValueError('仅7张详情或完整8图可按整套拼图采集')
 if not task.get('sheet_layout') and task.get('received_images'):raise ValueError('旧任务已有部分独立图，不能混入另一套拼图；请保留现有图片并先核对任务')
 if task.get('state') in ('saved','cancelled'):raise ValueError('原任务已结束，请从预览页创建已有图片采集备份任务')
 task.update(sheet_layout=dict(LAYOUT),delivery_policy='generated_originals',message='按用户选择读取现有3×3整套拼图；不重新作图')
 if task.get('image_job'):store.image_jobs.save()
 else:store.save()
 return plan(task)
