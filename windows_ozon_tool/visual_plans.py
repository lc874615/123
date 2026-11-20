"""Offline official-category routing and immutable per-request visual plans.
Rules select presentation, never product facts or technical specifications.
"""
import copy,hashlib,json,re
from pathlib import Path
VERSION=4
STYLES={
 'digital':('精密数码','精确轮廓、接口与材质分区；按商品对比选择浅色或深色摄影背景，不固定蓝色圆台。用柔和侧光分清塑料、金属、玻璃与屏幕；标题短、最多突出1—2个有依据的关键数字，避免顶部排满小标签。克制高光，不虚构电路、芯片、声波效果或内部剖面。'),
 'appliance':('生活电器','干净真实的厨房、浴室或操作空间；产品与实际任务同框，操作与配置清楚。主图可有序展示实际配置，使用页让产品与任务成为主体；文字直接说明用途，不夸大处理效果。'),
 'interior':('家居空间','原创空间、自然光、合理尺度与完整轮廓；家具人物互动自然，灯具等按实际用途展示，不统一套客厅或坐姿。环境陈设克制，商品关键轮廓、落地关系与接触阴影准确；尺寸页和材质页采用相应视角，不每页重复同一整件构图。'),
 'textile':('织物触感','准确颜色、真实织纹、垂坠、褶皱与缝边；不把普通材料美化成丝绸，不用泛金色滤镜代替质感。用柔和侧光显示纤维与边缘，配色由真实织物决定；标题与标签克制，套装数量、各件尺寸清楚。'),
 'engineering':('工程适配','安装位置、作业、接口与连接关系清楚；重要已知规格醒目，标题和数字对比明确，已知接口与固定位置采用大特写或短引线；操作姿势真实，避免统一黑底闪电及虚构强度/性能。'),
 'utility':('实用收纳','清晰有序的实际用途、数量与尺度；道具不冒充随货内容，用真实摆放、开合与尺度说明购买价值，文字优先标数量和尺寸，不堆空泛图标；不猜测容积、密封或食品适用性。'),
 'wearable':('穿戴版型','真实上身/上脚/携带与版型优先；主图允许少字或无大标题，不强制卖点标签，用中性或适配穿搭的背景、自然比例与柔和光线，准确保留颜色、图案、版型与部件，不编造模特身高体重或未见背面设计。'),
 'interaction':('亲和互动','真实使用者与产品的合理尺度；儿童、宠物分别规划，不统一卡通化，用清楚的尺寸、真实互动和产品近景建立信任，不让卡通装饰抢占商品，不写未经证实的安全无毒或益智宣称。'),
 'neutral':('简洁实物','中性清晰摄影背景，完整商品与已确认视角优先；不强加人物、功能情境或行业专属承诺。')}
# Exact phrases/stems apply to the leaf type, never arbitrary ancestors.
RULES=[
 ('auto_mirror','engineering',('汽车后视镜','зеркал.*(?:автомоб|заднего вида)')),
 ('mirror_mount','engineering',('镜子支架','镜子安装','креплен.*зеркал')),
 ('earphone_case','digital',('耳机壳','耳机保护','чехол.*науш','амбушюр')),
 ('speaker','digital',('音箱','扬声器','колонк.*(?:портатив|акустич)|акустич.*колонк','динамик')),
 ('auto_holder','engineering',('车载支架','车载手机','держател.*автомоб','автомоб.*держател')),
 ('phone_holder','engineering',('手机支架','держател.*телефон','подставк.*телефон')),
 ('charger','digital',('充电器','电源适配器','зарядн.*устройств','адаптер.*питан')),
 ('earphones','digital',('耳机','наушник')),
 ('digital_accessory','digital',('鼠标','键盘','移动电源','路由器','摄像头','мыш[ьи]','клавиатур','внешн.*аккумулятор','роутер','веб.камер')),
 ('power_tool','engineering',('热风枪','工程搅拌器','строительн.*фен','термофен','строительн.*миксер')),
 ('mirror','appliance',('镜子','折叠镜','化妆镜','зеркал')),
 ('haircare','appliance',('吹风机','卷发','直发','理发器','фен(?:ы| для|$)','стайлер','плойк','выпрямител.*волос','машинк.*стриж')),
 ('cleaner','appliance',('吸尘器','清洁电器','扫地机器人','пылесос','пароочистител')),
 ('kitchen_appliance','appliance',('搅拌机','破壁机','料理机','咖啡机','电热水壶','空气炸锅','блендер','миксер','кофемашин','электрочайник','аэрогрил')),
 ('lamp','interior',('台灯','落地灯','灯具','светильник','торшер','настольн.*ламп')),
 ('chair','interior',('椅子','扶手椅','沙发','凳子','кресл','стул','диван','табурет')),
 ('furniture','interior',('桌子','书桌','柜子','衣柜','床架','стол(?:ы|ик| |$)','шкаф','комод','кроват')),
 ('curtain','textile',('窗帘','штор','тюль')),
 ('bedding','textile',('床上用品','床品','被套','毛毯','床单','枕套','постельн','пододеяльник','плед','простын','наволочк')),
 ('power_tool','engineering',('电钻','电动工具','螺丝刀','дрел','шуруповерт','шуруповёрт','отвертк','отвёртк','электроинструмент')),
 ('hardware','engineering',('五金','紧固件','安装支架','门锁','крепеж','крепёж','кронштейн','замок.*двер')),
 ('storage','utility',('收纳','储物','整理盒','органайзер','коробк.*хранен','контейнер.*хранен','корзин')),
 ('kitchenware','utility',('餐具','厨具','锅具','контейнер.*(?:ед|продукт)','кухонн.*принадлеж','посуда','кастрюл','сковород')),
 ('pet','interaction',('猫抓','宠物','猫窝','狗窝','когтеточ','лежанк.*(?:кош|собак)','игрушк.*животн','товар.*животн')),
 ('toy','interaction',('玩具','积木','конструктор','игрушк')),
 ('shoes','wearable',('鞋子','运动鞋','皮鞋','凉鞋','靴子','кроссовк','туфл','ботинк',r'\bобув(?:ь|и|ью)\b')),
 ('bag','wearable',('背包','手提包','рюкзак','сумк')),
 ('clothing','wearable',('服装','衣服','t恤','衬衫','外套','长裤','短裤','裙子','футболк','рубашк','куртк','брюк','плать'))]
# topic key, buyer question, evidence need (None is externally visible facts only).
TOPICS={
 'main':('商品主图',None),'wear':('实际佩戴或握持尺度',None),'controls':('已确认操作方式','operation'),'connection':('连接与适配范围','connection'),
 'charging':('充电或供电说明','charging'),'exterior':('真实外观细节',None),'dimensions':('商品尺寸与摆放','dimensions'),'contents':('实际收到内容',None),
 'use':('主要真实用途',None),'attachments':('已知附件对应用途','accessories'),'care':('已确认护理说明','care'),'structure':('可见外部结构',None),
 'capacity':('已确认容量与尺度','capacity'),'placement':('实际摆放效果',None),'material':('可见表面与已知材质',None),'second_use':('另一合理动作或已确认视角',None),
 'options':('真实选项对比','options'),'seams':('缝边与连接做工',None),'set_sizes':('各件已知尺寸','dimensions'),'fit':('已确认适配范围','fit'),
 'installation':('可证实的安装方式','installation'),'working':('实际作业用途',None),'mount':('可见固定与连接',None),'organize':('已确认整理方式',None),
 'storage':('收纳与携带',None),'opening':('已确认开合与取用','operation'),'front_side':('已确认正面与侧面',None),'back':('已确认背面或替代视角',None),
 'styling':('真实场景搭配',None),'age':('已确认年龄与使用要求','age'),'play':('真实玩法',None),'pieces':('真实零件与连接',None)}
ORDERS={
 'auto_mirror':('main','placement','fit','installation','structure','dimensions','exterior','contents'),
 'phone_holder':('main','placement','fit','mount','controls','dimensions','material','contents'),
 'mirror_mount':('main','placement','fit','installation','structure','dimensions','material','contents'),
 'earphone_case':('main','exterior','fit','opening','material','dimensions','storage','contents'),
 'speaker':('main','placement','controls','connection','charging','structure','dimensions','contents'),
 'earphones':('main','wear','controls','connection','charging','exterior','dimensions','contents'),
 'charger':('main','connection','charging','controls','structure','fit','dimensions','contents'),
 'digital_accessory':('main','use','connection','controls','structure','exterior','dimensions','contents'),
 'mirror':('main','use','dimensions','mount','opening','exterior','second_use','contents'),
 'haircare':('main','use','attachments','controls','structure','care','dimensions','contents'),
 'cleaner':('main','use','attachments','controls','structure','care','capacity','contents'),
 'kitchen_appliance':('main','use','attachments','controls','care','structure','capacity','contents'),
 'chair':('main','use','dimensions','material','structure','second_use','options','contents'),
 'furniture':('main','placement','dimensions','opening','material','structure','options','contents'),
 'lamp':('main','placement','controls','dimensions','installation','exterior','second_use','contents'),
 'bedding':('main','material','seams','set_sizes','placement','options','care','contents'),
 'curtain':('main','placement','material','dimensions','mount','seams','options','contents'),
 'power_tool':('main','working','fit','controls','structure','dimensions','attachments','contents'),
 'auto_holder':('main','placement','fit','installation','mount','controls','dimensions','contents'),
 'hardware':('main','placement','fit','installation','structure','dimensions','material','contents'),
 'storage':('main','dimensions','use','opening','structure','organize','care','contents'),
 'kitchenware':('main','use','capacity','opening','material','dimensions','care','contents'),
 'clothing':('main','front_side','back','material','fit','styling','seams','contents'),
 'shoes':('main','wear','front_side','material','fit','structure','styling','contents'),
 'bag':('main','wear','opening','material','dimensions','structure','styling','contents'),
 'pet':('main','use','dimensions','material','mount','placement','care','contents'),
 'toy':('main','age','play','pieces','second_use','dimensions','storage','contents'),
 'neutral':('main','exterior','dimensions','material','structure','use','second_use','contents')}
DEFAULTS={'digital':'digital_accessory','appliance':'kitchen_appliance','interior':'furniture','textile':'bedding','engineering':'hardware','utility':'storage','wearable':'clothing','interaction':'pet','neutral':'neutral'}
FALLBACKS={'controls':('exterior','真实外部操作部位，不声称未确认功能'), 'connection':('exterior','接口或外观，仅展示原图可见处'),
 'charging':('structure','外部接口或连接细节，不编造供电能力'), 'attachments':('exterior','当前商品另一已确认细节'),
 'care':('material','可见表面与做工，不推测清洗方法'), 'capacity':('placement','整体尺度与摆放，不标猜测容量'),
 'dimensions':('exterior','整体外观：Общий вид，不画未知数字'), 'set_sizes':('placement','实际组成与摆放，不画未知尺寸'),
 'options':('exterior','当前变体重要细节，不虚构其他颜色'), 'fit':('front_side','已确认外形与接触位置，不保证兼容'),
 'installation':('mount','可见安装或连接位置，不虚构步骤'), 'opening':('exterior','已确认外部细节，不演示未知开合'),
 'age':('exterior','实物与使用要求，不猜适龄')}

def leaf_text(category):
 return ' '.join(str(v).strip().casefold().replace('ё','е') for v in (category.get('name',''),str(category.get('zh_path','')).split(' / ')[-1],str(category.get('path','')).split(' / ')[-1]))

def route(category):
 if not isinstance(category,dict) or not category.get('confirmed') or any(type(category.get(k)) is not int or category[k]<=0 for k in ('description_category_id','type_id')):return 'neutral','neutral','类目未确认，使用简洁实物'
 text=leaf_text(category)
 for subtype,style,patterns in RULES:
  if any(re.search(p,text) for p in patterns):return subtype,style,'已按官方商品类型匹配'
 return 'neutral','neutral','当前类型尚无明确映射，使用简洁实物，不靠上级大类猜测'

def build(category=None,params=None,group_count=1,override=None):
 # Product parameter tables intentionally do not influence new image plans.
 category=category if isinstance(category,dict) else {};subtype,style,reason=route(category);automatic=style
 if override in STYLES:
  style=override
  if style!=automatic:subtype=DEFAULTS[style]
  reason='手动视觉风格；商品事实仍只取本次原始参考图'
 pages=[]
 for n,topic in enumerate(ORDERS[subtype],1):
  title,need=TOPICS[topic]
  pages.append({'order':n,'key':topic,'requested_topic':topic,'filename':('01_main.jpg' if n==1 else f"{n:02d}_{topic}.jpg"),'title':title,'fallback':None,'fallback_if_unproven':FALLBACKS.get(topic),'needs':need})
 result={'warnings':[],'version':VERSION,'evidence_policy':'original_references_only','selling_plan_version':2,'style':style,'style_name':STYLES[style][0],'subtype':subtype,'reason':reason,'source':'manual' if override in STYLES else 'fallback' if subtype=='neutral' else 'official_category','category':{k:category.get(k) for k in ('description_category_id','type_id','name','zh_path')},'pages':pages,'group_count':group_count}
 result['fingerprint']=hashlib.sha256(json.dumps(result,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
 return result

def context(store,task):
 from creation_category import category_for_task
 from pricing_service import read
 path=store.folder/'products'/task['sku']/'listing_bundle.json';bundle=read(path) if path.exists() else {}
 category=bundle.get('category') if isinstance(bundle.get('category'),dict) else category_for_task(task)
 from account_context import credentials
 merchant=credentials()[0]
 task_override=task.get('visual_style_override') if task.get('visual_style_account',merchant)==merchant else None
 override=bundle.get('visual_style_override',task_override)
 members=[t for t in store.tasks if t.get('copy_leader',t['sku'])==task.get('copy_leader',task['sku']) and t.get('state')!='cancelled']
 return build(category,group_count=len(members) or 1,override=override)

def render(plan,facts='',group_facts='',scope='full'):
 from selling_plan import EXTRACTION,VALUE_SELECTION,STORYBOARD,VISUAL_PROOF,render_profile,selection_for_scope,storyboard_for_scope
 from original_image_policy import SOURCE_POLICY,EVIDENCE_PASS,PRODUCT_LOCK,ART_DIRECTION,DIMENSIONS,DELIVERY,FINAL_CHECK,GATES,COMPOSITIONS,DIGITAL_DIRECTION,PAGE_EXECUTION
 if scope not in ('full','main','shared'):raise ValueError('未知作图范围')
 # Old saved plans are never trusted as product evidence; rebuild presentation
 # from their category/override rather than carrying parameter-based fallbacks.
 if plan.get('evidence_policy')!='original_references_only' or plan.get('selling_plan_version')!=2:
  category={**(plan.get('category') or {}),'confirmed':True};plan=build(category,override=plan.get('style') if plan.get('source')=='manual' else None)
 pages=plan['pages'] if scope=='full' else plan['pages'][:1] if scope=='main' else plan['pages'][1:]
 rows=[]
 for i,page in enumerate(pages,1):
  name=page['filename'] if scope!='shared' else f"{i:02d}_{page['key']}.jpg"
  rule=GATES.get(page.get('needs'),'只展示本次原图能证实的外观、部件或用途；不生成未见视角与隐藏结构')
  fallback=page.get('fallback_if_unproven')
  alternative=('；证据不足改为'+fallback[1]+'或尚未覆盖的更强图证主题，文件编号与名称保持本清单不变') if fallback else ''
  composition=COMPOSITIONS.get(page['requested_topic'],'用当前原始视角组织大幅实物摄影，与其他编号区分。')
  role='主图任务：以完整商品识别为中心。' if page['requested_topic']=='main' else '详情任务：先选本页专属视觉证据与景别，产品大合集主图构图不作为默认布局。'
  rows.append(name+'：建议'+page['title']+'。'+role+composition+rule+alternative+'。同一张只讲一个核心主题，详情按证据分配规则调整。')
 limits={'full':'只能交付8张独立成品，01为当前变体主图，02—08为全组共用详情。','main':'只能生成和交付1张本变体主图，文件名固定01_main.jpg；不制作其他变体主图与详情。','shared':'只重做7张共用详情；本次01—07分别对应商品详情位置02—08，不生成或修改任何主图。'}
 category=plan.get('category') or {};label=category.get('zh_path') or category.get('name') or '未明确识别的类目'
 return '\n'.join([SOURCE_POLICY,limits[scope],DELIVERY,PAGE_EXECUTION,
  '【已选类目，仅设计路由】'+str(label)+'；'+plan['style_name']+' / '+plan['subtype']+'。类目与原图商品明显冲突时说明，不照类目改造实物。',
  EXTRACTION,selection_for_scope(scope),render_profile(plan['style'],scope),storyboard_for_scope(scope),PRODUCT_LOCK,'【本类摄影方向】'+STYLES[plan['style']][1]+(DIGITAL_DIRECTION if plan['style']=='digital' else ''),ART_DIRECTION,VISUAL_PROOF,
  DIMENSIONS,
  '【范围隔离】当前主图只用当前变体的原始外观；共用原始详情只补能核实适用的信息。重做不以旧AI成图为外观或参数依据。只保留本次范围内的编号，重做与首次执行同一证据和质量规则。',
  '【任务清单，不是一张图的分区】',*rows,FINAL_CHECK])

def shared_compatible(store,task):
 """A shared image set cannot silently mix independently selected product types."""
 from pricing_service import read
 from creation_category import category_for_task
 types=set()
 for member in store.tasks:
  if member.get('copy_leader',member['sku'])!=task.get('copy_leader',task['sku']) or member.get('state')=='cancelled':continue
  path=store.folder/'products'/member['sku']/'listing_bundle.json';b=read(path) if path.exists() else {}
  c=b.get('category') or category_for_task(member) or {}
  if c.get('confirmed') and c.get('type_id'):types.add((c.get('description_category_id'),c['type_id']))
 if len(types)>1:raise ValueError('同组变体存在不同官方商品类型，不能共用同一套详情方案；请先核对整组类目')

def save_group_override(store,sku,override):
 """Local next-request preference only. Live images and active request snapshots stay intact."""
 from pricing_service import read,write
 if override is not None and override not in STYLES:raise ValueError('未知视觉风格')
 if not store.lock.acquire(blocking=False):raise ValueError('后台正在保存素材，请稍后再保存风格；未改动已有方案')
 try:
  from account_context import credentials
  merchant=credentials()[0]
  task=next(t for t in store.tasks if t['sku']==sku);leader=task.get('copy_leader',sku)
  for member in store.tasks:
   if member.get('copy_leader',member['sku'])!=leader or member.get('state')=='cancelled':continue
   if override is None:member.pop('visual_style_override',None)
   else:member['visual_style_override']=override
   member['visual_style_account']=merchant
   path=store.folder/'products'/member['sku']/'listing_bundle.json'
   if path.exists():
    b=read(path)
    if override is None:b.pop('visual_style_override',None)
    else:b['visual_style_override']=override
    write(path,b)
  store.save()

 finally:store.lock.release()
