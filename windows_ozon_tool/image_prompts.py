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

def generation_prompt(facts,group_facts='',expected=8):
 if expected not in (1,8):raise ValueError('图片交付数量只能为1或8')
 common='每张3:4竖版，自然俄语排版，风格统一。严格保持参考图对应变体的外形、颜色、比例和结构。不得虚构参数、认证、承重、防水或功能；卖点不足时减少文字，不编造补足。涉及人物时，人手、姿势、商品使用方式和尺寸比例应合理，商品主体清晰，不被人物或装饰遮挡。'
 if expected==1:
  contract='本任务只能生成和交付1张最终主图，不生成其他图片；文件名固定01_main.jpg。主图要求：'+ROLES[0][1]+'。后7张详情图由本地沿用首变体，不要重复生成。'
 else:
  contract='本任务只能交付8张最终独立图片，必须严格按01到08逐张生成并按该顺序交付；不要多出第9张，不提供额外封面、试稿、备选图或重复版本，不做拼图。需要修改时只将最终定稿纳入交付，不把过程图混入成品列表。固定顺序与用途：'+'；'.join(name+'.jpg：'+brief for name,brief in ROLES)+'。02—08为全组共用详情，涉及颜色或尺寸差异必须标注选项；无法兼容的细节不写成全组通用。'
 return contract+common+FIDELITY+'最终只列出本次'+str(expected)+'张对应编号的独立文件及逐张下载入口，文件数量必须与编号一一对应，不要打包，不提供ZIP。当前变体商品事实：'+facts+('。当前主图只依据本变体资料，其他变体不得作为外观依据：'+facts if expected==1 else '。同组全部变体资料：'+(group_facts or facts))

FIDELITY='商品一致性优先于设计美化：只能使用本次附件中该变体的原始商品参考图作为外观依据，禁止沿用历史对话、其他变体或AI生成图中的商品。优先保留原商品并抠图合成，只改背景和排版，不重新设计或替换成相似款。逐项保持真实轮廓、比例、表面纹理/缝线、靠背与座面形状、腿脚/支架数量和造型、扶手有无、连接结构及颜色分区；原图没有的扶手、脚轮、配件不得增加。参考图看不到的角度沿用可确认视角，不凭空补画隐藏结构。每套件数必须与当前变体参数一致。俄语标题与真实卖点放在留白区，不能为排版压缩或改变商品。'

def shared_prompt(group_facts):
 roles=ROLES[1:]
 return '本任务只重做全组共用的7张详情图，不生成主图、不改任何变体主图。严格交付7张独立3:4竖版JPG，文件按本任务01—07编号，分别对应商品详情位置02—08，不混入第8张或过程图，不做拼图或ZIP。用途顺序：'+'；'.join('%02d_%s.jpg：%s'%(i+1,name.split('_',1)[1],brief) for i,(name,brief) in enumerate(roles))+'。统一自然俄语排版；场景丰富，优先自然的人物实际使用场景。涉及不同颜色、规格、材质或件数必须分别标注选项，不能混装或将不同结构写成全组通用。'+FIDELITY+'未附对应原图的变体只作已知参数的文字说明，不凭空绘制该选项的商品外观。最终仅提供这7个编号文件的逐张下载入口。全组事实：'+group_facts

def reference_contract(task):
 refs=task.get('references') or [];lines=[]
 for i,r in enumerate(refs):
  usage=('对应变体在共用详情中的真实商品外观' if r.get('purpose','variant_main')=='variant_main' else '全组共用细节依据，差异不可写成通用') if task.get('kind')=='shared_details' else ('仅用于本变体主图外观' if r.get('purpose','variant_main')=='variant_main' else '只作共用详情依据，不作为本变体主图外观')
  lines.append(str(i+1)+'：'+str(r.get('name','原图'))+'；货号 '+str(r.get('sku') or task.get('sku',''))+'；用途 '+usage)
 return FIDELITY+'\n本次附件对应关系：\n'+'\n'.join(lines)
