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

VISUAL_STYLE='视觉参考只借鉴构图、文字层级、留白和特写组织，不借用参考商品的外观、品牌或功能。采用真实商品摄影感，背景与品类/用途相符，优先柔和自然光和中性底色，商品与背景分离清楚；整组统一字体、圆角卡片、图标线条和留白。强调色少量取自实际商品或场景，不固定绿色，不改变变体真实颜色。俄文采用清晰粗体无衬线标题，通常1—2行，标题、卖点、补充说明形成三级层次，避免细小长段文字；手机缩略图中仍应能分清商品和标题。四周保留约5%安全边距，边框、尺寸箭头和文字不压住商品关键轮廓。无品牌商品不加品牌标、仿品牌椭圆徽章或PUREU字样；货号、SKU、任务编号、参考图文件名不得印进图内。'
MAIN_STYLE='【主图设计，仅作用于01主图】大幅照片级商品摄影，背景清楚有真实层次，文字约5%安全边距；只选择一种合适的构图，按品类选择真实使用环境或简洁摄影背景；商品占主体约三分之二，保留关键轮廓、结构及真实销售件数。核心商品名称最大、自然俄语粗体无衬线1—2行；2—4条已确认重要卖点，事实不足则减少，数字带准确单位。配色协调本品，不固定绿色。只可用少量真实局部特写辅助，不把尺寸页、场景页、材质页、变体页的完整海报同时放进主图。原创空间与机位，不复刻样例；需要人物时接触自然、主体结构仍可辨认。无品牌不加品牌/官方店标，不加价格、促销、评价或无依据认证。'
MAIN_DETAIL_INFO='【主图事实选材】从当前变体参数、原图及原始共用详情资料中筛选真实卖点。共用详情成图只作信息索引，不是新增事实来源；shared_information只核对适用信息，不作为本变体外观依据。不挪用其他颜色、尺寸或套装的专属事实，不复制详情布景或拼成主图。'
EVIDENCE_STYLE='【共同事实边界】仅用本次对应原图和已填参数；共同事实才写成全组选项通用，差异分别标注，不能混装。没有清晰细节照片就不臆造纹理，不能据此虚构内部层数、剖面、机构或性能。不得添加未证实的认证、承重、透气、防水、疗效或功能；不自行加入1—3厘米误差，不从示例复制数字。无品牌商品不加品牌标；货号、SKU、任务编号、文件名只供程序关联，不印入画面。'
POSTER_RULE='单张海报可以包含同主题局部特写、尺寸线和少量标签；允许一张独立海报内使用局部特写，不等于把多张完整海报缩进一页。不得把整套拼图裁剪、放大、换名作为独立成品。'
SEQUENTIAL_DELIVERY='【独立成品交付执行协议，先于画面设计】按本任务编号输出独立3:4高清图片；目标1500×2000，工具不支持时采用其高分辨率3:4画幅，每张至少750×1000。一次接收整套任务，不等于一次绘图调用制作整套：每次图像生成/编辑工具调用只制作当前编号的一张完整海报。只向该次绘图工具传入本张主题、适用原图与必要共同规则，不把后续编号内容画进本张。完成并检查当前编号后，继续下一编号，无须逐张征求确认；由当前回复内部连续执行，不要求插件逐张发送请求。不得先做整套预览、联系表或拼图。修改只替换当前编号的最终定稿；内部检查不输出额外试稿。完成全部后只列最终独立文件及真实下载入口，不编造链接、不提供ZIP。'
DETAIL_STYLE='【共用详情摄影设计，作用于详情位置02—08】每张只讲一个既定主题；真实大幅商品摄影、人物使用摄影或材质/结构大特写铺满画面，不能把商品缩进固定卡片、目录页或PPT。商品通常占画面宽65%—85%；人物与商品共同构成主体，手部、尺度、接触与支撑自然，允许必要局部遮挡，关键结构仍可辨。按品类设计原创空间、光线、机位与动作，不复刻示例；适用品类两张场景图必须出现人物实际使用，不能只换上一张背景色。不适合人物操作的商品展示真实环境或手部，不强行安排人物。商品、人物与中后景家具陈设均清晰可辨；不要浅景深、柔焦或涂抹背景，微距只要求目标纹理清楚。大标题用自然俄语粗体无衬线，通常2—5词、1—2行；每图0—3条简短事实说明，标题显著大于标签，5%安全边距仅用于文字。材质页允许大幅分区，真实选项页允许网格；其他页不做多海报网格。配色协调本品，不固定绿色；事实不足少写，不缩小字号。不得用Python/PIL/SVG或占位图片绘制简化商品冒充摄影成品，程序只辅助格式和排版。'
LAYOUTS={'02_dimensions': '一张大幅本品摄影配准确商品尺寸线，不混包装尺寸；未知尺寸不画数字或虚假刻度，全部未知用Общий вид。选项尺寸不同分别标注。', '03_scene': '第一实际使用场景：人物或适用手部真实使用，动作、接触和比例自然；大幅摄影加短标题，不用空房间小商品替代。', '04_scene': '第二实际使用场景：改变合理空间或主要动作，不能只换背景色，不虚构第二功能；反射类商品各镜像须符合视角与同一人物动作。', '05_material': '一至两处大幅本品真实材质特写，分清主体、配件与内衬，不虚构第二材质。材质未知仅展示可见纹理，标题Фактура и отделка。', '06_structure': '仅表现有依据的外部连接、支撑、开合、接口或控制部件，配1—3处大特写与短引线；无原图依据不做内部剖面或功能演示。', '07_details': '优先当前变体真实外观细节；多变体共用且有各自原图时可对比真实选项并逐一标注，未附原图只写已知文字，不虚构颜色或暗示全部随货。', '08_contents': '大幅展示购买一个选项收到的具体商品单位、数量及已确认配件；单件写1 шт.，不把其他选项、道具、重复近景或未声明赠品计入套装。'}

FINAL_DETAIL_MATCH='【最后验收与异常处理】每个编号对应一张真实完整成品，主题正确、商品真实、俄语可读、尺寸和销售内容有依据。文件名、像素或比例合格不能替代图片内容合格。若本张有错，先修正本张再推进，不把修改稿重复列入成品。因工具限制无法继续时，准确说明已完成与未完成编号，不把拼图、重复图或旧文件命名为缺失编号，不声称整套完成；保留已完成文件，不要求插件自动补图。'

def role_layout(name,brief):return brief+('；'+LAYOUTS[name] if name in LAYOUTS else '')

MAIN_DIMENSIONS='【01主图尺寸保留】首次及重做都逐一核对本变体全部主图原始参考。原图内清晰商品尺寸必须保留到01主图，保留全部不重复的有效尺寸、单位、测量部位及展开/折叠状态；不能以“详情图已有尺寸”、简洁排版或卖点数量为由省略。预留清晰尺寸模块，可重排测量线但不能改变数字含义、商品比例或混用包装尺寸。不得挪用其他变体、风格样例数字，不从像素比例估算。原图与已填尺寸冲突须明确报告，不静默覆盖；无法确认的数字不猜。'

def generation_prompt(facts,group_facts='',expected=8,visual_plan=None):
 if visual_plan is not None:
  if expected not in (1,8):raise ValueError('图片交付数量只能为1或8')
  from visual_plans import render
  return render(visual_plan,facts,group_facts,'main' if expected==1 else 'full')
 if expected not in (1,8):raise ValueError('图片交付数量只能为1或8')
 common='每张3:4竖版，自然俄语排版，风格统一。严格保持参考图对应变体的外形、颜色、比例和结构。不得虚构参数、认证、承重、防水或功能；卖点不足时减少文字，不编造补足。涉及人物时，人手、姿势、商品使用方式和尺寸比例应合理，人物与商品实际接触自然；允许真实坐姿等必要局部遮挡，但商品仍清楚可辨，关键轮廓、底座或支撑结构可见，不把主体大面积藏住。'
 if expected==1:
  contract='本任务只能生成和交付1张最终主图，不生成其他图片；文件名固定01_main.jpg。主图要求：'+ROLES[0][1]+'。后7张详情图由本地沿用首变体，不要重复生成。'
 else:
  contract='本任务只能交付8张最终独立图片，必须严格按01到08逐张生成并按该顺序交付；不要多出第9张，不提供额外封面、试稿、备选图或重复版本，不把整套海报拼成一张交付。需要修改时只将最终定稿纳入交付，不把过程图混入成品列表。任务清单（下列是8次独立绘图任务，不是一张图的分区）：\n'+'\n'.join(name+'.jpg：'+role_layout(name,brief) for name,brief in ROLES)+'。02—08为全组共用详情，涉及颜色或尺寸差异必须标注选项；无法兼容的细节不写成全组通用。'
 facts=visual_facts(facts);group_facts=visual_facts(group_facts)
 return SEQUENTIAL_DELIVERY+'\n'+(DETAIL_STYLE+'\n' if expected==8 else '')+contract+'\n'+common+EVIDENCE_STYLE+POSTER_RULE+MAIN_STYLE+MAIN_DETAIL_INFO+MAIN_DIMENSIONS+FIDELITY+('座椅类额外核对扶手有无、腿脚数量与底座造型；原商品是平绒就不能变成条绒。' if any(w in facts for w in ('椅','沙发','凳')) else '')+'最终只列出本次'+str(expected)+'张对应编号的独立文件及逐张下载入口，文件数量必须与编号一一对应，不要打包，不提供ZIP。当前变体商品事实：'+facts+('。当前主图只依据本变体资料，其他变体不得作为外观依据。' if expected==1 else '。同组全部变体资料：'+(group_facts if group_facts and group_facts!=facts else '单一选项，沿用上述当前变体事实'))+(FINAL_DETAIL_MATCH if expected==8 else '')

FIDELITY='【商品锁定】商品一致性优先于设计美化：仅以当前变体原始商品参考作外观依据，优先抠图合成，保持轮廓、比例、纹理、部件数量、连接结构和颜色分区；不借用历史对话、其他变体或AI成图的外观。看不到的角度沿用可确认视角，不凭空补画隐藏结构，不新增配件；每套件数与参数一致。'

def shared_prompt(group_facts,visual_plan=None):
 if visual_plan is not None:
  from visual_plans import render
  return render(visual_plan,'当前主图不在本次重做范围',group_facts,'shared')
 roles=ROLES[1:]
 group_facts=visual_facts(group_facts)
 return SEQUENTIAL_DELIVERY+'\n'+DETAIL_STYLE+'\n'+'本任务只重做全组共用的7张详情图，不生成主图、不改任何变体主图。严格交付7张独立3:4竖版JPG，文件按本任务01—07编号，分别对应商品详情位置02—08，不混入第8张或过程图，不把整套海报合成一张，不提供ZIP。用途顺序：'+'；'.join('%02d_%s.jpg：%s'%(i+1,name.split('_',1)[1],role_layout(name,brief)) for i,(name,brief) in enumerate(roles))+'。7张图各自的用途和顺序固定，视觉参考不能改变这些用途。统一自然俄语排版；人物互动重点用于原定的两张使用场景图，不把每一张都变成人物广告。涉及不同颜色、规格、材质或件数必须分别标注选项，不能混装或将不同结构写成全组通用。'+EVIDENCE_STYLE+POSTER_RULE+FIDELITY+'未附对应原图的变体只作已知参数的文字说明，不凭空绘制该选项的商品外观。最终仅提供这7个编号文件的逐张下载入口。全组事实：'+group_facts+FINAL_DETAIL_MATCH

def reference_contract(task):
 refs=task.get('references') or [];lines=[]
 for i,r in enumerate(refs):
  usage=('对应变体在共用详情中的真实商品外观' if r.get('purpose','variant_main')=='variant_main' else '全组共用细节依据，差异不可写成通用') if task.get('kind')=='shared_details' or task.get('expected_images')==8 else ('仅用于本变体主图外观' if r.get('purpose','variant_main')=='variant_main' else '用于主图筛选并核对可用卖点/材质/重要参数，不作为本变体外观依据')
  if r.get('purpose') in ('shared_variant','shared_reference_sheet'):usage='仅供7张共用详情核对全组选项；不得作为当前变体主图外观依据'
  if r.get('purpose','variant_main')=='variant_main' and (r.get('sku') or task.get('sku'))==task.get('sku') and task.get('kind')!='shared_details':usage+='；本变体原图内清晰商品尺寸必须保留到01主图，不能省略或仅移到详情图'
  if r.get('cells'):usage+='；按从左到右、从上到下格号对应：'+str(r['cells'])
  lines.append(str(i+1)+'：'+str(r.get('name','原图'))+'；货号 '+str(r.get('sku') or task.get('sku',''))+'；用途 '+usage)
 return '附件仅按下列角色使用，不从输入索引页复制整套拼图。\n本次附件对应关系：\n'+'\n'.join(lines)


def main_detail_references(task,tasks):
 """Original shared detail sources, information only; never another variant's hero."""
 leader=task.get('copy_leader') or task['sku']
 source=next((t for t in tasks if t.get('sku')==leader and t.get('state')!='cancelled'),task)
 own=[r for r in task.get('references',[]) if r.get('purpose')!='shared_information']
 shared=source.get('detail_references') or [r for r in source.get('references',[]) if r.get('purpose') in ('shared_gallery','shared_detail')]
 seen={r.get('path') for r in own}
 return own+[dict(r,purpose='shared_information',sku=source['sku']) for r in shared if r.get('path') not in seen]


def sheet_prompt(facts,group_facts='',expected=8,shared=False):
 from contact_sheet import contract
 if shared:
  roles=ROLES[1:];style=DETAIL_STYLE
 else:
  roles=ROLES if expected==8 else ROLES[:1];style=DETAIL_STYLE+MAIN_STYLE+MAIN_DETAIL_INFO+MAIN_DIMENSIONS
 if expected==1:return generation_prompt(facts,group_facts,1)
 # Assemble only the sheet contract; never append conflicting independent-file rules.
 return contract(expected)+style+EVIDENCE_STYLE+FIDELITY+'各格用途顺序：'+'；'.join(str(i+1)+'：'+role_layout(n,b) for i,(n,b) in enumerate(roles))+'。当前变体事实：'+facts+'。全组选项事实：'+(group_facts or facts)


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
