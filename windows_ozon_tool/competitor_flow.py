"""Observable official-schema competitor references and a bounded pre-copy gate.
Reference proposals never become own-product claims without explicit adoption.
"""
import hashlib,json,time
from pathlib import Path
from pricing_service import read,write
from attribute_service import field_key

def signal(store):
 store.competitor_revision=getattr(store,'competitor_revision',0)+1
 from automation_wake import notify
 notify(store)

def current_snapshot(bundle):
 from competitor_reference import context
 from account_context import credentials
 try:c=context(bundle,credentials()[0])
 except (ValueError,TypeError):c=None
 s=bundle.get('competitor_reference') or {}
 return s if c and s.get('fingerprint')==c['fingerprint'] else {}

def accepted_records(bundle):
 from competitor_reference import eligible
 snapshot=current_snapshot(bundle);state=bundle.get('attribute_draft') or {};out=[]
 if snapshot.get('state')!='ready':return out
 source=snapshot.get('fingerprint','')+':'+snapshot.get('result_hash','')
 for f in state.get('fields',[]):
  if not eligible(f):continue
  key=field_key(f);decision=(bundle.get('reference_decisions') or {}).get(key) or {};values=(state.get('values') or {}).get(key) or []
  if decision.get('action')!='accepted' or decision.get('source')!=source or not values:continue
  if decision.get('accepted_values') is not None:
   if decision['accepted_values']!=values:continue
  else:
   # Older accepted records have no value snapshot: require the same label.
   original=(snapshot.get('suggestions') or {}).get(key,{})
   if '；'.join(str(v.get('value','')) for v in values)!=original.get('value'):continue
  texts=[str(v.get('value') or '').strip() for v in values]
  if not all(texts):continue
  out.append({'field_key':key,'name':f.get('name_ru') or f.get('name'),'values':texts,'required':bool(f.get('is_required'))})
 return sorted(out,key=lambda r:(not r['required'],r['field_key']))[:40]

def copy_evidence(bundles):
 return [{'sku':b['sku'],'attributes':accepted_records(b)} for b in bundles if accepted_records(b)]

def copy_signature(bundles):
 rows=copy_evidence(bundles)
 return hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False).encode()).hexdigest() if rows else ''

def copy_prompt(bundles):
 from competitor_reference import proposals
 evidence=copy_evidence(bundles)
 candidates=[{'sku':b['sku'],'fields':[{'field_key':r['key'],'name':r['field'].get('name_ru') or r['field'].get('name'),'candidate':r['suggested']} for r in proposals(b).values()][:40]} for b in bundles if proposals(b)]
 reference=('\n【竞品待核验候选，不是商品事实】'+json.dumps(candidates,ensure_ascii=False)+'。这些只用于提示应核对哪些官方字段。必须从本次本商品原始附件或明确已填参数获得独立证据，才可把同值加入文案；不能凭相似外形推断材质、协议、性能或兼容。不确定就不写，并保留missing_facts；如原图明确可读，按现有category_attributes协议记录原图证据，不把竞品作为source。不得在文案写出SKU、field_key、来源或候选状态。') if candidates else ''
 if not evidence:return reference
 return reference+('\n【用户已核对采用的官方字段参数】以下字段来自所选类目的官方schema，值经用户核对后采用并经官方字典校验。只选会影响买家决策且适用于对应选项的信息加入自然俄语标题/简介，避免堆砌；共同信息才能写成全组通用。不要将下列SKU或字段ID写进文案，不增加参数未证明的功效、认证、比较、包装或性能。未知字段留空不编造。\n'+json.dumps(evidence,ensure_ascii=False))

def describe(bundle,task=None):
 from competitor_reference import context,proposals,eligible
 from account_context import credentials
 url=(bundle.get('variant_parameters') or {}).get('competitor_url') or ((task or {}).get('variant_parameters') or {}).get('competitor_url')
 empty={'state':'none','label':'未填写链接','configured':False,'matched':0,'prefilled':0,'applied':0,'detail':'未填写竞品链接，不读取竞品参数。'}
 if not url:return empty
 try:c=context(bundle,credentials()[0])
 except ValueError as exc:return {**empty,'configured':True,'state':'invalid','label':'链接无效 / 未预填','detail':str(exc)}
 snap=current_snapshot(bundle);gate=(task or {}).get('competitor_wait') or {}
 schema=bundle.get('attribute_draft') or {};official=sum(eligible(f) for f in schema.get('fields',[]));matched=len(snap.get('suggestions') or {});prefilled=len(proposals(bundle));applied=len(accepted_records(bundle));existing=sum(bool((schema.get('values') or {}).get(field_key(f))) for f in schema.get('fields',[]) if eligible(f))
 if not c:state='schema';label='待官方字段 / 未预填'
 elif not snap:state='queued';label='待采集 / 未预填'
 else:
  state=snap.get('state','queued');label={'reading':'采集中 / 未预填','failed':'采集失败 / 未预填','ready':f'已读 · 匹配{matched} · 预填{prefilled} · 采用{applied}'}.get(state,'待采集 / 未预填')
 if state=='ready' and snap.get('read_scope')=='summary':label=f'仅简要 · 匹配{matched} · 预填{prefilled}'
 if state=='failed' and snap.get('retryable'):state='retrying';label='等待自动重试 / 未预填'
 if state=='failed' and snap.get('error_code')=='verification':state='verification';label='需页面验证 / 未预填'
 if gate.get('state')=='timeout' and state in ('schema','queued','reading'):state='timeout';label='采集超时 / 未预填'
 used=bundle.get('copy_competitor_fields') or []
 detail=(str(url)+'\n'+(snap.get('message') or gate.get('message') or '等待官方字段同步与插件读取')+'\n页面读取 '+str(snap.get('raw_count',0))+' 项；自动尝试 '+str(snap.get('attempts',0))+'/3。\n官方可引用字段 '+str(official)+'；匹配 '+str(matched)+'；参考预填 '+str(prefilled)+'（待核对）；已采用 '+str(applied)+'；已填值保留 '+str(existing)+'。未获取字段不补造。\n文案请求中已核对参数 '+str(len(used))+' 项，待原图核验候选 '+str(len(bundle.get('copy_competitor_candidates') or []))+' 项；不代表文案已逐项引用，实际内容请在预览核对。'+('\n未匹配字段示例：'+'、'.join(snap['unmatched_names']) if snap.get('unmatched_names') else ''))
 return {'state':state,'label':label,'configured':True,'matched':matched,'prefilled':prefilled,'applied':applied,'detail':detail}

def group_label(rows):
 configured=[r for r in rows if r['configured']]
 if not configured:return '未填写链接'
 return f"已读{sum(r['state']=='ready' for r in configured)}/{len(configured)} · 失败{sum(r['state'] in ('failed','verification') for r in configured)} · 预填{sum(r['prefilled'] for r in configured)} · 已采用{sum(r['applied'] for r in configured)}"

def before_copy(store,leader,now=None):
 """Wait for configured links to finish, never hold a business lock over IO.
 Failure/timeouts are terminal for this copy attempt and leave references empty.
 """
 from competitor_reference import context
 from account_context import credentials
 now=time.time() if now is None else now;pending=[];configured=0;basis_rows=[];account=credentials()[0]
 for t in store.tasks:
  if t.get('state')=='cancelled' or t.get('copy_leader',t['sku'])!=leader['sku']:continue
  path=store.folder/'products'/t['sku']/'listing_bundle.json'
  if not path.exists():
   if (t.get('variant_parameters') or {}).get('competitor_url'):pending.append('等待变体草稿')
   continue
  b=read(path)
  if not (b.get('variant_parameters') or {}).get('competitor_url'):continue
  configured+=1;basis_rows.append([t['sku'],b['variant_parameters']['competitor_url'],b.get('category')])
  try:c=context(b,account)
  except ValueError:continue  # Invalid link is shown in the status column.
  s=current_snapshot(b)
  if c and (s.get('state')=='ready' or s.get('state')=='failed' and not s.get('retryable')):continue
  pending.append('等待官方字段' if c is None else '等待竞品采集')
 if not pending:
  if leader.pop('competitor_wait',None):store.save()
  return True
 basis=hashlib.sha256(json.dumps([account,basis_rows],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
 prior=leader.get('competitor_wait') or {};started=prior.get('started_at',now) if prior.get('basis')==basis else now
 if now-started>=150:
  leader['competitor_wait']={'state':'timeout','basis':basis,'started_at':started,'message':'竞品参数读取超时，未获取字段留空；文案只使用已有已核实事实'};store.save();return True
 leader['competitor_wait']={'state':'waiting','basis':basis,'started_at':started,'message':'文案前参数准备：'+'、'.join(dict.fromkeys(pending))+'；未获取字段留空'}
 service=getattr(store,'attributes',None)
 if service is not None:service.wake.set()
 store.save();return False
