import base64,copy,hashlib,io,json,os,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from asset_state import pending,mark_changes,canonical
from image_format import normalize
from group_service import GroupService
from local_bridge import Store
from pairing import token,InstanceLock
from pipeline_status import stage,group_summary
from pricing_service import read,write
from publication_service import PublicationService
from shop_state import switch
import test_group_publication as fixtures

class FinalWorkflowTests(unittest.TestCase):
 def test_physical_change_only_marks_assets_and_blocks_old_publication(self):
  with tempfile.TemporaryDirectory() as tmp:
   g,a,p=fixtures.GroupTests().setup_group(tmp,True);before=g.load();g.set_parameters([0],'color',['红色'],g.token());after=g.load()
   self.assertTrue(pending(after[0]));self.assertTrue(after[1]['asset_review']['gallery']);self.assertEqual(before[0]['images'],after[0]['images']);self.assertEqual(a.items,{})
   with self.assertRaisesRegex(ValueError,'素材待更新'):p.begin(g,g.token())
 def test_cost_change_does_not_mark_assets(self):
  with tempfile.TemporaryDirectory() as tmp:
   g,a,p=fixtures.GroupTests().setup_group(tmp);g.set_parameters([0],'cost',['30'],g.token());self.assertFalse(pending(g.load()[0]))
 def test_equivalent_dimension_and_color_do_not_mark_assets(self):
  b={'images':[{}],'variant_parameters':{'color':'金色','length':'44'}};after=copy.deepcopy(b);after['variant_parameters'].update(color='золотой',length='44.0');mark_changes([b],[after]);self.assertFalse(pending(after))
 def test_group_description_edit_is_single_source(self):
  with tempfile.TemporaryDirectory() as tmp:
   g,a,p=fixtures.GroupTests().setup_group(tmp,True);text='Общее описание для всех вариантов.';g.set_attributes([1],'0:4191',[[{'value':text}]],g.token())
   self.assertTrue(all(b['copy']['description_ru']==text and b['attribute_draft']['values']['0:4191'][0]['value']==text for b in g.load()))
 def test_group_tag_edit_cleans_and_syncs_all_variants(self):
  with tempfile.TemporaryDirectory() as tmp:
   g,a,p=fixtures.GroupTests().setup_group(tmp,True);g.set_attributes([1],'0:23171',[[{'value':'дом хранение, #уют!'}]],g.token());self.assertTrue(all(b['copy']['tags_ru']==['#дом_хранение','#уют'] for b in g.load()))
 def test_conflicting_bulk_common_text_rejected_atomically(self):
  with tempfile.TemporaryDirectory() as tmp:
   g,a,p=fixtures.GroupTests().setup_group(tmp,True);before=g.load()
   with self.assertRaises(ValueError):g.set_attributes([0,1],'0:4191',[[{'value':'one'}],[{'value':'two'}]],g.token())
   self.assertEqual(g.load(),before)
 def test_editors_share_business_lock(self):
  with tempfile.TemporaryDirectory() as tmp:
   g,a,p=fixtures.GroupTests().setup_group(tmp);other=GroupService(g.paths,g.attributes,g.pricing);self.assertIs(g.mutex,other.mutex)
 def test_manual_price_recomputes_actual_profit(self):
  with tempfile.TemporaryDirectory() as tmp:
   g,a,p=fixtures.GroupTests().setup_group(tmp);old=g.load()[0]['auto_pricing'];g.set_prices([0],['200'],g.token());b=g.load()[0];actual=b['manual_pricing'];self.assertTrue(actual['valid']);self.assertEqual(actual['price_cny'],'200.00');self.assertNotEqual(actual['profit_cny'],old['profit_cny']);self.assertEqual(b['price_cny'],'200.00')
 def test_low_manual_price_warns_but_keeps_user_price(self):
  with tempfile.TemporaryDirectory() as tmp:
   g,a,p=fixtures.GroupTests().setup_group(tmp);g.set_prices([0],['5'],g.token());b=g.load()[0];self.assertEqual(b['price_cny'],'5.00');self.assertTrue(b['manual_pricing']['valid']);self.assertTrue(b['manual_pricing']['warning'])
 def test_manual_price_outside_bands_is_explicitly_invalid(self):
  with tempfile.TemporaryDirectory() as tmp:
   g,a,p=fixtures.GroupTests().setup_group(tmp);g.set_prices([0],['1000000'],g.token());b=g.load()[0];self.assertEqual(b['price_cny'],'1000000.00');self.assertFalse(b['manual_pricing']['valid'])
 def test_webp_ingestion_normalizes_to_jpg_and_retains_original(self):
  with tempfile.TemporaryDirectory() as tmp:
   output=io.BytesIO();Image.new('RGB',(600,800),'orange').save(output,'WEBP');raw=output.getvalue();new,ext=normalize(raw,Path(tmp)/'originals');self.assertEqual(ext,'jpg');self.assertEqual(Image.open(io.BytesIO(new)).format,'JPEG');self.assertEqual(len(list((Path(tmp)/'originals').glob('*.webp'))),1)
   s=Store(Path(tmp)/'data');s.create_set('WEBP','商品事实');t=s.tasks[0];t['state']='waiting';s.set_result(t['id'],0,base64.b64encode(raw).decode());self.assertTrue(s.tasks[0]['received_images'][0]['file'].endswith('.jpg'))
 def test_local_pairing_survives_restart(self):
  with tempfile.TemporaryDirectory() as tmp:self.assertEqual(token(tmp),token(tmp))
 def test_second_instance_is_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   one=InstanceLock(tmp);two=InstanceLock(tmp);one.acquire()
   try:
    with self.assertRaises(ValueError):two.acquire()
   finally:one.release()
   two.acquire();two.release()
 def test_restart_marks_waiting_task_for_read_only_recovery(self):
  with tempfile.TemporaryDirectory() as tmp:
   s=Store(tmp);s.create_set('A','真实资料');s.tasks[0]['state']='waiting';s.save();again=Store(tmp);self.assertEqual(again.tasks[0]['resume_mode'],'inspect_only');self.assertEqual(again.tasks[0]['state'],'needs_attention')
 def test_pause_requires_ack_before_delete(self):
  with tempfile.TemporaryDirectory() as tmp:
   s=Store(tmp);s.create_set('A','真实资料');t=s.tasks[0];t['state']='waiting';s.set_paused(True)
   with self.assertRaises(ValueError):s.delete_task(t['id'])
   t['pause_ack']=True;s.delete_task(t['id']);self.assertEqual(s.tasks,[])
 def test_resume_never_requeues_a_sent_task(self):
  with tempfile.TemporaryDirectory() as tmp:
   s=Store(tmp);s.create_set('A','真实资料');t=s.tasks[0];t['state']='waiting';s.set_paused(True);s.set_paused(False);self.assertEqual(t['state'],'needs_attention');self.assertEqual(t['resume_mode'],'inspect_only')
 def test_shop_switch_preserves_shared_assets_and_restores_settings(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'products'/'A'/'listing_bundle.json';b={'sku':'A','images':[{'sha256':'same'}],'copy':{'title_ru':'Общий'},'category':{'type_id':1,'confirmed':True},'fulfillment':{'account_id':'one','warehouse_id':7},'price_cny':'10'};write(path,b);switch(tmp,'one','two');second=read(path);self.assertNotIn('fulfillment',second);self.assertFalse(second['category']['confirmed']);self.assertEqual(second['images'],b['images'])
   second['fulfillment']={'account_id':'two','warehouse_id':8};write(path,second);switch(tmp,'two','one');self.assertEqual(read(path)['fulfillment']['warehouse_id'],7)
 def test_other_shop_active_task_does_not_block_current_shop(self):
  with tempfile.TemporaryDirectory() as tmp:
   g,a,p=fixtures.GroupTests().setup_group(tmp);job=p.begin(g,g.token());p.account_getter=lambda:'other';self.assertIsNone(p.active([g.load()[0]['sku']]))
   with self.assertRaises(ValueError):p.call_for('test-shop','/v2/products/stocks',{})
 def test_removed_task_stops_followup_before_stock_write(self):
  with tempfile.TemporaryDirectory() as tmp:
   g,a,p=fixtures.GroupTests().setup_group(tmp);sku=g.load()[0]['sku'];tasks=g.paths[0].parent.parent.parent/'tasks.json';write(tasks,[{'sku':sku,'state':'saved'}]);job=p.begin(g,g.token());write(tasks,[]);result=p.step(job['id']);self.assertEqual(result['state'],'cancelled_followup');self.assertFalse(any(x=='/v2/products/stocks' for x,b in a.calls))
 def test_stage_uses_publication_not_stale_image_message(self):
  task={'sku':'A','state':'saved','message':'待上架审核'};job={'state':'on_sale','items':{'A':{'on_sale':True}}};self.assertEqual(stage(task,{},[job]),'已上架');self.assertEqual(group_summary(['已上架','需修改：标签错误']),'已上架 1/2 · 需处理 1')
  self.assertEqual(stage(task,{'asset_review':{'main':True}},[job]),'图片待核对：外观参数已变化')
 def test_long_wait_is_attention_not_automatic_reimport(self):
  with tempfile.TemporaryDirectory() as tmp:
   g,a,p=fixtures.GroupTests().setup_group(tmp);job=p.begin(g,g.token());job['last_progress_at']=time.time()-1000;p._save(job);self.assertTrue(read(p.root/(job['id']+'.json'))['needs_attention']);self.assertEqual(sum(x=='/v3/product/import' for x,b in a.calls),1)

class RebuildAndDeleteTests(unittest.TestCase):
 def test_shared_copy_edit_saves_every_variant_including_pending(self):
  with tempfile.TemporaryDirectory() as tmp:
   g,a,p=fixtures.GroupTests().setup_group(tmp,True);root=g.paths[0].parent.parent.parent;leader=g.load()[0]['sku']
   rows=[{'sku':b['sku'],'facts':'资料','variant_parameters':b['variant_parameters']} for b in g.load()]+[{'sku':'THIRD','facts':'尚未完成素材','variant_parameters':{'color':'灰色'}}]
   tasks=[]
   for n,row in enumerate(rows):
    tasks.append({'id':'T'+str(n),'sku':row['sku'],'state':'queued','set_mode':True,'copy_leader':leader,'group_variants':rows,'facts':row['facts'],'received_images':[]})
   for path in g.paths:
    b=read(path);b['group_variants']=rows;write(path,b)
   write(root/'tasks.json',tasks);store=Store(root);g.store=store
   value={'title_ru':'Общий заголовок','description_ru':'Металлические корзины с картонной вставкой.','tags_ru':['#корзины'],'missing_facts':[]}
   g.set_copy(value,g.token())
   for path in g.paths:
    b=read(path);self.assertEqual(b['copy'],{**value,'sku':b['sku']});self.assertEqual(len(b['group_variants']),3)
   self.assertEqual(read(root/'products'/'THIRD'/'shared_copy.json')['copy'],{**value,'sku':'THIRD'})
   self.assertTrue(all(len(t['group_variants'])==3 for t in store.tasks))
 def test_restore_deleted_record_keeps_sent_work_read_only(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('A','资料');ids=[t['id'] for t in store.tasks];store.delete_tasks(ids)
   backup=next((Path(tmp)/'deleted_tasks').glob('*.json'));self.assertEqual(store.restore_deleted(backup),1)
   self.assertEqual(store.tasks[0]['state'],'needs_attention');self.assertEqual(store.tasks[0]['resume_mode'],'inspect_only')
 def test_manual_update_backs_up_and_only_queues_after_user_action(self):
  with tempfile.TemporaryDirectory() as tmp:
   g,a,p=fixtures.GroupTests().setup_group(tmp,True);root=g.paths[0].parent.parent.parent;leader=g.load()[0]['sku'];tasks=[]
   for n,path in enumerate(g.paths):
    b=read(path);tasks.append({'id':'T'+str(n),'sku':b['sku'],'name':'00_full_set','set_mode':True,'state':'saved','video':str(path.parent/'video'/'product_8s.mp4'),'received_images':read(path.parent/'image_manifest.json'),'copy_state':'done','copy_leader':leader,'model':b['model'],'variant_index':n+1,'references':[],'facts':b.get('facts','资料'),'variant_parameters':b['variant_parameters']})
   write(root/'tasks.json',tasks);store=Store(root);g.store=store;g.set_parameters([0],'color',['红色'],g.token());self.assertTrue(all(t['state']=='saved' for t in store.tasks));stamp=store.rebuild_group(leader);self.assertTrue(all(t['state']=='queued' for t in store.tasks));self.assertEqual([t['expected_images'] for t in store.tasks],[8,1]);self.assertTrue(all((path.parent/'regeneration_backups'/stamp/'images').is_dir() for path in g.paths));self.assertTrue(all(read(path)['regeneration_pending'] for path in g.paths))
 def test_leader_delete_respects_dependents_but_group_delete_works(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);store.create_set('A','资料');store.create_set('B','资料');store.tasks[0]['copy_leader']='A';store.tasks[1]['copy_leader']='A';ids=[t['id'] for t in store.tasks]
   with self.assertRaises(ValueError):store.delete_task(ids[0])
   self.assertEqual(store.delete_tasks(ids),2)
 def test_switch_back_resumes_safe_polling_without_resubmission(self):
  with tempfile.TemporaryDirectory() as tmp:
   g,a,p=fixtures.GroupTests().setup_group(tmp);job=p.begin(g,g.token());saved=read(p.root/(job['id']+'.json'));saved['next_poll_at']=time.time()+500;saved['retry_count']=4;write(p.root/(job['id']+'.json'),saved);p.resume_account('test-shop');new=read(p.root/(job['id']+'.json'));self.assertEqual(new['next_poll_at'],0);self.assertEqual(new['retry_count'],0);self.assertEqual(sum(x=='/v3/product/import' for x,b in a.calls),1)
