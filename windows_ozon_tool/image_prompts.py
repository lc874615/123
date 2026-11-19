"""One delivery contract for initial generation, followers and manual regeneration."""
ROLES=(
 ('01_main','主图：准确展示本变体真实颜色、规格及销售数量；醒目的俄语大标题，旁边清晰罗列2—4条有事实依据的重要卖点，文字简洁、层级清晰、不遮挡商品'),
 ('02_dimensions','商品尺寸图：只采用商品尺寸，不能把包装尺寸写成商品尺寸；全组尺寸不同时明确标注对应选项'),
 ('03_scene','真实使用场景一：环境丰富、自然生活感，优先加入符合商品用途和目标受众的人物正在实际使用，展示明确的使用动作与商品价值'),
 ('04_scene','真实使用场景二：更换合理的空间、人物动作或用途，背景有生活细节；优先人物互动，不重复上一张布景'),
 ('05_material','材质细节：只描述已知主体和配件/内衬材质，局部特写与整体结合，不能混淆材质'),
 ('06_structure','结构展示：仅展示参考图及参数能证实的结构，不臆造折叠、拆装或承重功能'),
 ('07_details','重要细节和变体选择：真实细节特写，颜色/规格对比要清楚标注各选项，不暗示全部选项一起发货'),
 ('08_contents','套装实际内容：明确购买一个变体实际收到的件数、颜色和已知配件，不添加未声明配件'),
)

# Compatibility names point to the new policy; none is assembled twice.
from original_image_policy import ART_DIRECTION as VISUAL_STYLE,ART_DIRECTION as MAIN_STYLE,SOURCE_POLICY as EVIDENCE_STYLE,PRODUCT_LOCK as FIDELITY,ART_DIRECTION as DETAIL_STYLE,EVIDENCE_PASS as MAIN_DETAIL_INFO,DIMENSIONS as MAIN_DIMENSIONS,DELIVERY as SEQUENTIAL_DELIVERY,FINAL_CHECK as FINAL_DETAIL_MATCH
POSTER_RULE='允许单张同主题局部特写；不得将整套海报拼成一张交付。'

def generation_prompt(facts='',group_facts='',expected=8,visual_plan=None):
 if expected not in (1,8):raise ValueError('图片交付数量只能为1或8')
 from visual_plans import build,render
 # Keep the public signature for saved-task compatibility; never serialize facts.
 return render(visual_plan or build(),scope='main' if expected==1 else 'full')

def shared_prompt(group_facts='',visual_plan=None):
 from visual_plans import build,render
 return render(visual_plan or build(),scope='shared')

def reference_contract(task):
 refs=task.get('references') or [];lines=[]
 for i,r in enumerate(refs):
  usage=('对应变体在共用详情中的真实商品外观' if r.get('purpose','variant_main')=='variant_main' else '全组共用细节依据，差异不可写成通用') if task.get('kind')=='shared_details' or task.get('expected_images')==8 else ('仅用于本变体主图外观' if r.get('purpose','variant_main')=='variant_main' else '用于主图筛选并核对可用卖点/材质/重要参数，不作为本变体外观依据')
  if r.get('purpose')=='shared_variant':usage='仅供共用详情核对该选项；不得作为当前变体主图外观依据'
  if r.get('purpose')=='shared_reference_sheet':usage='原始输入索引，逐格按purpose及sku确认角色；只有当前变体variant_main格可作其主图外观依据，shared_information/shared_detail格仅核实适用信息，其他变体格不得影响当前主图'
  if r.get('purpose','variant_main')=='variant_main' and (r.get('sku') or task.get('sku'))==task.get('sku') and task.get('kind')!='shared_details':usage+='；本变体原图内清晰商品尺寸必须保留到01主图，不能省略或仅移到详情图'
  if r.get('cells'):usage+='；以下仅为原始输入资料，绝非成品版式；按从左到右、从上到下格号对应：'+str([{k:c.get(k) for k in ('cell','sku','purpose','source_name','region')} for c in r['cells']])
  if r.get('region'):usage+='；这是同一原始详情的'+r['region']+'，用于读取文字与细节，不能当成新增商品/选项'
  lines.append(str(i+1)+'：'+str(r.get('name','原图'))+'；货号 '+str(r.get('sku') or task.get('sku',''))+'；用途 '+usage)
 from group_references import INFO
 return (INFO+'\n' if task.get('kind')=='shared_details' or task.get('expected_images')==8 else '')+'附件中的局部区域与完整原图属于同一证据，不能重复计入套装或当成新选项；区域编号不代表商品尺寸。附件仅按下列角色使用，不从输入索引页复制整套拼图。\n本次附件对应关系：\n'+'\n'.join(lines)


def main_detail_references(task,tasks):
 """Original shared detail sources, information only; never another variant's hero."""
 leader=task.get('copy_leader') or task['sku']
 source=next((t for t in tasks if t.get('sku')==leader and t.get('state')!='cancelled'),task)
 own=task.get('main_references') or [r for r in task.get('references',[]) if r.get('purpose','variant_main')=='variant_main' and r.get('sku',task['sku'])==task['sku']]
 shared=source.get('detail_references') or [r for r in source.get('references',[]) if r.get('purpose') in ('shared_gallery','shared_detail')]
 seen={r.get('path') for r in own}
 return own+[dict(r,purpose='shared_information',sku=source['sku']) for r in shared if r.get('path') not in seen]


def sheet_prompt(facts,group_facts='',expected=8,shared=False):
 # Never revive the historical contact-sheet delivery path for a new request.
 return shared_prompt() if shared else generation_prompt(expected=expected)


def visual_facts(value):
 import re
 text=str(value or '')
 labels=('包装长(cm)','包装宽(cm)','包装高(cm)','包装总重(g)','每套成本含国内运费(元)','目标净利润率(%)','初始库存（固定1000）','产地')
 for label in labels:text=re.sub(r'(?:^|[；;\n])'+re.escape(label)+r'[:：][^；;\n]*','',text)
 return text.strip('；;\n')

def photo_facts(parameters,fallback=''):
 from variants import FIELDS
 allowed={'name','color','size','quantity','material','accessory_material','length','width','height','net_weight','assembly','extra'}
 if not isinstance(parameters,dict) or not parameters.get('name'):return visual_facts(fallback)
 return '；'.join(label+'：'+str(parameters[k]).strip() for k,label,_ in FIELDS if k in allowed and str(parameters.get(k,'')).strip())+'；品牌：无品牌'

def photo_group(variants):
 return '\n'.join(str(v['sku'])+'：'+photo_facts(v.get('variant_parameters') or v.get('parameters') or {},v.get('facts','')) for v in variants)
