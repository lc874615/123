import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from visual_plans import build,route,render,context,save_group_override,shared_compatible
from pricing_service import read,write

def cat(name,typ=20):return {'description_category_id':10,'type_id':typ,'name':name,'confirmed':True}
class VisualPlanTests(unittest.TestCase):
 def test_official_leaf_routes_across_styles_and_subtypes(self):
  samples=[('Наушники','digital','earphones'),('Зарядные устройства','digital','charger'),('Портативная акустическая колонка','digital','speaker'),('Чехол для наушников','digital','earphone_case'),('Фен для волос','appliance','haircare'),('Строительный фен','engineering','power_tool'),('Строительный миксер','engineering','power_tool'),('Зеркало','appliance','mirror'),('Блендеры погружные','appliance','kitchen_appliance'),('Кресло','interior','chair'),('Настольный светильник','interior','lamp'),('Постельное белье','textile','bedding'),('Шторы','textile','curtain'),('Шуруповерт','engineering','power_tool'),('Автомобильный держатель','engineering','auto_holder'),('Подставка для телефона','engineering','phone_holder'),('Зеркало заднего вида','engineering','auto_mirror'),('Коробка для хранения','utility','storage'),('Когтеточка','interaction','pet'),('Детский конструктор','interaction','toy'),('Футболка','wearable','clothing'),('Кроссовки','wearable','shoes'),('Рюкзак','wearable','bag')]
  for name,style,subtype in samples:
   with self.subTest(name=name):p=build(cat(name));self.assertEqual((p['style'],p['subtype']),(style,subtype));self.assertEqual(len(p['pages']),8)
 def test_unknown_leaf_never_guesses_from_ancestor_or_product_title(self):
  p=build({**cat('Новая принадлежность'),'path':'Электроника / Наушники / Новая принадлежность'},{'name':'耳机'})
  self.assertEqual(p['style'],'neutral');self.assertEqual(build({'name':'耳机'})['style'],'neutral')
  self.assertEqual(build({**cat('Наушники'),'confirmed':False})['style'],'neutral')
  self.assertEqual(build(cat('Автомобильный держатель'),{'name':'无线耳机'})['subtype'],'auto_holder')
 def test_known_category_title_conflict_is_visible_without_rewriting_class(self):
  p=build(cat('Автомобильный держатель'),{'name':'耳机'});self.assertTrue(p['warnings']);self.assertEqual(p['style'],'engineering');self.assertEqual(p['category']['name'],'Автомобильный держатель');self.assertIn('方向不一致',render(p,'真实耳机资料'))
 def test_accessory_material_does_not_invent_included_accessories(self):
  p=build(cat('Блендер'),{'accessory_material':'金属','size':'MODEL_A1'})
  self.assertTrue(next(x for x in p['pages'] if x['requested_topic']=='attachments')['fallback'])
  self.assertTrue(next(x for x in build(cat('Зарядные устройства'),{'size':'MODEL_A1'})['pages'] if x['requested_topic']=='fit')['fallback'])
 def test_content_order_differs_by_product_type_not_just_background(self):
  params={'extra':'蓝牙，充电，触控，兼容，护理，安装','length':'10','accessory_material':'配件'}
  plans=[build(cat(n),params,3) for n in ('Наушники','Зарядные устройства','Кресло','Постельное белье','Шуруповерт','Футболка','Когтеточка','Конструктор')]
  orders=[tuple(p['requested_topic'] for p in b['pages']) for b in plans];self.assertEqual(len(set(orders)),len(orders))
  for b in plans:self.assertEqual(b['pages'][0]['filename'],'01_main.jpg');self.assertEqual([p['order'] for p in b['pages']],list(range(1,9)))
 def test_missing_evidence_has_safe_named_replacement(self):
  p=build(cat('Наушники'),{'name':'耳机','size':'MODEL_A1'},1);by={r['requested_topic']:r for r in p['pages']}
  for key in ('connection','charging','controls','dimensions'):self.assertTrue(by[key]['fallback']);self.assertNotIn(key,by[key]['filename'])
  p=build(cat('Кресло'),{'length':'50'},1);options=next(r for r in p['pages'] if r['requested_topic']=='options');self.assertTrue(options['fallback'])
  p=build(cat('Наушники'),{'extra':'蓝牙5.3；USB-C充电；按键控制','length':'3'},2)
  for r in p['pages']:
   if r['requested_topic'] in ('connection','charging','controls','dimensions'):self.assertIsNone(r['fallback'])
 def test_render_scope_separates_main_shared_and_filenames(self):
  plan=build(cat('Наушники'),{'extra':'蓝牙；充电；按键','length':'3'})
  full=render(plan,'CURRENT','OTHER','full');main=render(plan,'CURRENT','OTHER_SECRET','main');shared=render(plan,'CURRENT','OTHER','shared')
  self.assertIn('01_main.jpg',full);self.assertIn('02_wear.jpg',full);self.assertNotIn('OTHER_SECRET',main)
  self.assertIn('当前主图尺寸',main.replace('01主图尺寸','当前主图尺寸'));self.assertNotIn('01_main.jpg',shared);self.assertIn('01_wear.jpg',shared);self.assertIn('07_contents.jpg',shared)
  self.assertIn('不强制两张人物场景',full);self.assertIn('穿戴类可少字',main)
 def test_creation_selection_claim_and_draft_preserve_plan_and_override(self):
  from local_bridge import Store
  from creation_category import selection,apply_task
  from test_image_regeneration import picture
  with tempfile.TemporaryDirectory() as tmp,patch.dict('os.environ',{'OZON_CLIENT_ID':'shop'}):
   store=Store(tmp);ref=Path(tmp)/'ref.png';ref.write_bytes(picture(1));store.create_set('A','耳机',[ref]);task=store.tasks[0];task['variant_parameters']={'name':'耳机','color':'白色','quantity':'1','length':'3'}
   apply_task(task,selection(cat('Наушники'),'shop'),'shop');self.assertEqual(task['visual_plan']['style'],'digital')
   request=store.claim();self.assertEqual(request['visual_plan']['subtype'],'earphones');self.assertIn('02_wear.jpg',request['prompt']);self.assertNotIn('02_dimensions.jpg',request['prompt'])
 def setup_group(self,tmp):
  from test_image_regeneration import ImageRegenerationTests
  store=ImageRegenerationTests().setup(tmp)
  for task in store.tasks:
   path=store.folder/'products'/task['sku']/'listing_bundle.json';b=read(path);b['category']=cat('Наушники');write(path,b)
  return store
 def test_regeneration_uses_latest_category_and_shared_numbering(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=self.setup_group(tmp);sku=store.tasks[0]['sku'];main=store.image_jobs.prompt(sku,'variant_main');shared=store.image_jobs.prompt(sku,'shared_details')
   self.assertIn('精密数码',main);self.assertIn('01_wear.jpg',shared);self.assertNotIn('01_main.jpg',shared)
   for task in store.tasks:
    path=store.folder/'products'/task['sku']/'listing_bundle.json';b=read(path);b['category']=cat('Кресло',30);write(path,b)
   self.assertIn('家居空间',store.image_jobs.prompt(sku,'variant_main'));self.assertNotIn('精密数码',store.image_jobs.prompt(sku,'variant_main'))
 def test_override_preserves_live_images_and_dispatched_request(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict('os.environ',{'OZON_CLIENT_ID':'shop'}),patch('image_regeneration.threading.Thread'):
   store=self.setup_group(tmp);sku=store.tasks[0]['sku'];old=copy.deepcopy(store.tasks[0]['received_images']);store.image_jobs.create(sku,'variant_main',[sku],'');job=store.image_jobs.claim();snapshot=copy.deepcopy(store.image_jobs.get(job['id'])['visual_plan'])
   save_group_override(store,sku,'textile');self.assertEqual(context(store,store.tasks[0])['style'],'textile');self.assertEqual(store.tasks[0]['received_images'],old);self.assertEqual(store.image_jobs.get(job['id'])['visual_plan'],snapshot)
   save_group_override(store,sku,None);self.assertEqual(context(store,store.tasks[0])['style'],'digital')
 def test_draft_preserves_dispatch_plan_and_cross_shop_does_not_inherit_override(self):
  from creation_category import selection,apply_task
  from listing_bundle import prepare
  from shop_state import switch
  with tempfile.TemporaryDirectory() as tmp,patch.dict('os.environ',{'OZON_CLIENT_ID':'shop'}):
   store=self.setup_group(tmp);task=store.tasks[0];chosen=selection(cat('Наушники'),'shop');chosen['visual_style_override']='textile';apply_task(task,chosen,'shop')
   folder=store.folder/'products'/task['sku'];(folder/'listing_bundle.json').unlink();b=read(prepare(folder,task));self.assertEqual(b['visual_plan']['style'],'textile');self.assertEqual(b['visual_style_override'],'textile')
   switch(store.folder,'shop','other')
   with patch.dict('os.environ',{'OZON_CLIENT_ID':'other'}):self.assertEqual(context(store,task)['style'],'neutral')
   switch(store.folder,'other','shop');self.assertEqual(context(store,task)['style'],'textile')
 def test_mixed_group_classes_block_shared_remake_before_any_job(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=self.setup_group(tmp);path=store.folder/'products'/store.tasks[1]['sku']/'listing_bundle.json';b=read(path);b['category']=cat('Кресло',30);write(path,b)
   with self.assertRaisesRegex(ValueError,'不同官方商品类型'):store.image_jobs.create(store.tasks[0]['sku'],'shared_details',[],'')
   self.assertFalse(store.image_jobs.jobs)
