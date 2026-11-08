"""Controls below the media cards; user additions survive thumbnail refreshes."""
def build(parent,bundles,store,start,stop,accept=None):
 import tkinter as tk
 from tkinter import ttk
 from tkinter.scrolledtext import ScrolledText
 from image_prompts import generation_prompt,shared_prompt
 panel=ttk.LabelFrame(parent,text='图片重做 · 原图先备份，新图采集完成后替换');panel.pack(fill='x',padx=8,pady=14)
 ttk.Label(panel,text='共用详情重做7张；变体主图每个单独生成1张。只使用原始参考图。新图替换后自动更新视频、托管链接及富内容；不会自动提交Ozon。',wraplength=850).pack(anchor='w',padx=8,pady=6)
 shared=ttk.LabelFrame(panel,text='1. 全组共用详情图（02—08）');shared.pack(fill='x',padx=8,pady=6)
 ttk.Label(shared,text='基础提示词（自动带入最新全组参数）').pack(anchor='w');shared_base=ScrolledText(shared,height=4,wrap='word');shared_base.pack(fill='x')
 ttk.Label(shared,text='补充要求：可补充文字、排版、场景和人物动作；商品外观与参数仍以原图和已填资料为准。',wraplength=850).pack(anchor='w');shared_add=ScrolledText(shared,height=3,wrap='word');shared_add.pack(fill='x',pady=4)
 current=bundles();shared_add.insert('1.0',((current[0].get('image_regeneration_options') or {}).get('shared_details','')) if current else '')
 shared_button=ttk.Button(shared,text='重新生成7张共用详情图并同步全组',command=lambda:start('shared_details',[],shared_add.get('1.0','end-1c')));shared_button.pack(anchor='e',pady=5)
 main=ttk.LabelFrame(panel,text='2. 所选变体主图（只替换01，不改7张详情）');main.pack(fill='x',padx=8,pady=6);choices=ttk.Frame(main);choices.pack(fill='x');selected={}
 for i,b in enumerate(current):
  var=tk.BooleanVar(value=False);selected[b['sku']]=var;ttk.Checkbutton(choices,text=b['sku']+' · '+str((b.get('variant_parameters') or {}).get('color','')),variable=var).grid(row=i//3,column=i%3,sticky='w',padx=6,pady=3)
 ttk.Label(main,text='基础主图提示词（示例为第一个勾选变体；执行时每个变体分别使用自己的原图与参数）',wraplength=850).pack(anchor='w');main_base=ScrolledText(main,height=4,wrap='word');main_base.pack(fill='x')
 ttk.Label(main,text='给勾选变体追加的要求（可一次选多个，逐个生成并采集）').pack(anchor='w');main_add=ScrolledText(main,height=3,wrap='word');main_add.pack(fill='x',pady=4)
 main_button=ttk.Button(main,text='重新生成所选变体主图',command=lambda:start('variant_main',[s for s,v in selected.items() if v.get()],main_add.get('1.0','end-1c')));main_button.pack(anchor='e',pady=5)
 verification=ttk.Label(panel,text='',wraplength=850);verification.pack(anchor='w',padx=8,pady=4)
 if accept:ttk.Button(panel,text='已检查本组图片无误，沿用并继续',command=accept).pack(anchor='w',padx=8,pady=4)
 state=ttk.Label(panel,text='等待选择重做范围',wraplength=850);state.pack(anchor='w',padx=8,pady=5);ttk.Button(panel,text='停止本组图片重做（保留原图及备份）',command=stop).pack(anchor='e',padx=8,pady=5)
 initialized=[False]
 def update_prompts(*args):
  rows=bundles()
  if not rows:return
  for i,b in enumerate(rows):
   if b['sku'] not in selected:
    var=tk.BooleanVar(value=False);selected[b['sku']]=var;ttk.Checkbutton(choices,text=b['sku']+' · '+str((b.get('variant_parameters') or {}).get('color','')),variable=var).grid(row=i//3,column=i%3,sticky='w',padx=6,pady=3);var.trace_add('write',update_prompts)
  if not initialized[0]:
   initialized[0]=True
   if not shared_add.get('1.0','end-1c'):shared_add.insert('1.0',(rows[0].get('image_regeneration_options') or {}).get('shared_details',''))
  facts='\n'.join(b['sku']+'：'+str(b.get('facts') or '') for b in rows);chosen=next((b for b in rows if selected.get(b['sku']) and selected[b['sku']].get()),rows[0])
  for widget,text in ((shared_base,shared_prompt(facts)),(main_base,generation_prompt(chosen.get('facts') or '',facts,1))):
   if widget.get('1.0','end-1c')==text:continue
   widget.configure(state='normal');widget.delete('1.0','end');widget.insert('1.0',text);widget.configure(state='disabled')
 for var in selected.values():var.trace_add('write',update_prompts)
 def poll():
  if not panel.winfo_exists():return
  rows=bundles();reasons=[]
  for b in rows:
   validation=b.get('asset_validation') or {};changes=validation.get('main_changes',[])+validation.get('gallery_changes',[])
   if changes:reasons.append(b['sku']+'：'+'、'.join(changes))
  verification.configure(text='需核对的图片参数：\n'+'\n'.join(reasons) if reasons else '图片采集与参数校验通过后自动继续；文案缺失或待更新会自动处理，不需要重新作图。')
  skus=[b['sku'] for b in rows];jobs=store.image_jobs.active(skus)
  state.configure(text='\n'.join(('共用详情' if j['kind']=='shared_details' else j['sku']+' 主图' if j['kind']=='variant_main' else '已有图片采集')+'：'+str(len(j.get('received_images') or []))+'/'+str(j['expected_images'])+' · '+j.get('message',j['state']) for j in jobs) or '本组无未完成的图片重做任务。')
  panel.after(1500,poll)
 update_prompts();poll()
 return {'frame':panel,'shared_start':shared_button,'main_start':main_button,'shared_add':shared_add,'main_add':main_add,'selected':selected,'refresh':update_prompts,'status':state}
