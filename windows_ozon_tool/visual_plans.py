"""Offline official-category routing and immutable per-request visual plans.
Rules select presentation, never product facts or technical specifications.
"""
import copy,hashlib,json,re
from pathlib import Path
VERSION=1
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
NEEDS={
 'operation':r'开合|折叠|操作|按键|触控|режим|кноп|управлен|склад',
 'connection':r'蓝牙|bluetooth|usb|type.?c|无线|兼容|连接|совмест|подключ',
 'charging':r'充电|电池|供电|usb|type.?c|заряд|питан|аккумулятор',
 'care':r'清洗|护理|洗涤|不可水洗|уход|стирк|мыть|чистк',
 'fit':r'兼容|适配|совмест|подходит|поддержива',
 'installation':r'安装|组装|悬挂|无需组装|креплен|монтаж|сборк|подвес',
 'age':r'适用年龄|岁以上|возраст|лет|год'}
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

def evidence(need,params,count):
 if need=='options':return count>1
 if need=='dimensions':return any(str(params.get(k,'')).strip() for k in ('length','width','height')) or bool(re.search(r'\d+(?:[.,]\d+)?\s*(?:cm|mm|см|мм|厘米|毫米)|\d+\s*[x×]\s*\d+',str(params.get('size','')),re.I))
 if need=='capacity':return bool(re.search(r'容量|容积|毫升|\bml\b|объем|объём|литр',str(params.get('extra','')).casefold()))
 if need=='accessories':
  text=str(params.get('extra','')).casefold()
  return not re.search(r'无配件|无附件|不含配件|без насад|без аксессуар',text) and bool(re.search(r'配件|附件|随附|насад|комплект',text))
 if need in NEEDS:return bool(re.search(NEEDS[need],str(params.get('extra',''))+' '+str(params.get('size',''))+' '+str(params.get('assembly','')),re.I))
 return True

def build(category=None,params=None,group_count=1,override=None):
 params=params if isinstance(params,dict) else {};category=category if isinstance(category,dict) else {}
 subtype,style,reason=route(category);automatic=style
 if override in STYLES:
  style=override
  if style!=automatic:subtype=DEFAULTS[style]
  reason='手动视觉风格；商品事实与官方类目不改变'
 pages=[]
 for n,topic in enumerate(ORDERS[subtype],1):
  title,need=TOPICS[topic];fallback=None
  available=evidence(need,params,group_count)
  if need=='fit' and subtype in ('clothing','shoes'):available=bool(str(params.get('size','')).strip()) or evidence('dimensions',params,group_count)
  if need and not available:
   fallback=FALLBACKS[topic];title=fallback[1]
  pages.append({'order':n,'key':fallback[0] if fallback else topic,'requested_topic':topic,'filename':('01_main.jpg' if n==1 else f"{n:02d}_{fallback[0] if fallback else topic}.jpg"),'title':title,'fallback':fallback,'needs':need})
 warnings=[]
 if automatic!='neutral' and params.get('name'):
  _,named_style,_=route({'description_category_id':1,'type_id':1,'name':params['name'],'confirmed':True})
  if named_style not in ('neutral',automatic):warnings.append('商品名称与所选类目的品类方向不一致，请核对；未自动更改类目或商品事实')
 result={'warnings':warnings,'version':VERSION,'style':style,'style_name':STYLES[style][0],'subtype':subtype,'reason':reason,'source':'manual' if override in STYLES else 'fallback' if subtype=='neutral' else 'official_category','category':{k:category.get(k) for k in ('description_category_id','type_id','name','zh_path')},'pages':pages,'group_count':group_count}
 result['fingerprint']=hashlib.sha256(json.dumps(result,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
 return result

def context(store,task):
 from creation_category import category_for_task
 from pricing_service import read
 path=store.folder/'products'/task['sku']/'listing_bundle.json';bundle=read(path) if path.exists() else {}
 category=bundle.get('category') if isinstance(bundle.get('category'),dict) else category_for_task(task)
 params=bundle.get('variant_parameters') or task.get('variant_parameters') or {}
 from account_context import credentials
 merchant=credentials()[0]
 task_override=task.get('visual_style_override') if task.get('visual_style_account',merchant)==merchant else None
 override=bundle.get('visual_style_override',task_override)
 members=[t for t in store.tasks if t.get('copy_leader',t['sku'])==task.get('copy_leader',task['sku']) and t.get('state')!='cancelled']
 return build(category,params,len(members) or 1,override)

def render(plan,facts,group_facts='',scope='full'):
 from image_prompts import SEQUENTIAL_DELIVERY,FIDELITY,MAIN_DIMENSIONS,EVIDENCE_STYLE,POSTER_RULE,visual_facts
 if scope not in ('full','main','shared'):raise ValueError('未知作图范围')
 pages=plan['pages'] if scope=='full' else plan['pages'][:1] if scope=='main' else plan['pages'][1:]
 count=len(pages);rows=[]
 for i,page in enumerate(pages,1):
  name=page['filename'] if scope!='shared' else f"{i:02d}_{page['key']}.jpg"
  rows.append(name+'：'+page['title']+'。只做这一主题；不同主题不能缩成完整海报塞入本张。')
 main_rules=('01主图优先商品识别及重要购买理由，不强制大标题或同数量标签；穿戴类可少字，其余按商品与风格用简短标题及0—3条已确认信息。'+MAIN_DIMENSIONS) if scope!='shared' else '本任务只重做7张共用详情，不生成主图、不改现有主图；01—07对应商品位置02—08。'
 group_rules=('本次只有当前变体主图，其他详情页不在交付范围。' if scope=='main' else '共用详情可参考全组选项原图与已填参数，但每张须明确选项差异，不把不同结构、尺寸或件数合成一件商品。只有一个选项时不生成色卡。')
 return '\n'.join([SEQUENTIAL_DELIVERY,f'【本次只交付{count}张】范围：{scope}。只交付这些编号最终文件，不增加其他海报。',
 '【类目路由】'+plan['style_name']+' / '+plan['subtype']+'；'+plan['reason']+'。类目只决定呈现，不提供商品事实。',
 '【类目与资料核对】'+('；'.join(plan.get('warnings',[])) if plan.get('warnings') else '无名称与类目方向冲突提示；原图真实性仍需核对')+'。出现真实冲突时不得照类目凭空改造商品，应说明冲突。',
 '【摄影与版式】'+STYLES[plan['style']][1]+'真实照片级画面，大主体、清楚细节，自然俄语；背景和关键部位清楚，不能用虚化隐藏缺失结构。每图选择整体、局部、操作、人物或示意中适用的构图，不统一套圆角卡片。人物/宠物/儿童仅在用途适合且尺度合理时出现，不强制两张人物场景。',
 main_rules,EVIDENCE_STYLE,FIDELITY,POSTER_RULE,group_rules,'【任务清单，不是一张图的分区】',*rows,
 '【证据检查】上述主题只是内容计划，不能暗示未证实功能；参数未覆盖的内容已给替代方向。原图能补充明确依据时可细化；否则按替代主题或已确认外观制作。不能猜测充电、协议、续航、适龄、清洁、承重、兼容或隐藏背面。所有尺寸冲突明确报告。',
 '【当前变体真实资料】'+visual_facts(facts),'【全组选项资料】'+(visual_facts(group_facts or facts) if scope!='main' else '本次只制作当前变体主图，不引入其他变体外观资料'),
 '【交付核对】逐张核对商品、变体、主题、人物与反射、俄语、件数及实际文件。文件名、数量、像素合格不能代替视觉合格；修改只替换当前编号，失败准确说明缺项，不把拼图或旧文件换名。'])

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
