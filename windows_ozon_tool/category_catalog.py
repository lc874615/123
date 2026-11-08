"""Shop-scoped category tree cache for the interactive selector."""
import hashlib,time
from category_match import leaves
from pricing_service import read,write

def load_catalog(service,merchant,force=False):
 path=service.root/('category-tree-'+hashlib.sha256(str(merchant).encode()).hexdigest()[:16]+'.json')
 if not force and path.exists():
  try:
   cached=read(path)
   if 0<=time.time()-cached['fetched_at']<86400 and isinstance(cached['rows'],list) and cached['rows']:return cached['rows']
  except (OSError,ValueError,KeyError,TypeError):pass
 zh=list(leaves(service.caller('/v1/description-category/tree',{'language':'ZH_HANS'})['result']))
 ru={(r['description_category_id'],r['type_id']):r for r in leaves(service.caller('/v1/description-category/tree',{'language':'RU'})['result'])}
 rows=[{**r,'zh_path':r['path'],'name':ru.get((r['description_category_id'],r['type_id']),r)['name'],'path':ru.get((r['description_category_id'],r['type_id']),r)['path']} for r in zh]
 if not rows:raise ValueError('官方类目列表为空，请稍后刷新')
 write(path,{'fetched_at':time.time(),'rows':rows});return rows

def setup_errors(bundles,merchant):
 errors=[]
 for b in bundles:
  prefix=b.get('sku','')+'：';category=b.get('category') or {};setting=b.get('export_settings') or {};warehouse=b.get('fulfillment') or {}
  if not category.get('confirmed'):errors.append(prefix+'类目未确认：双击“上架类目 / 商品类型”，点击“确认沿用当前类目”。')
  if not warehouse.get('warehouse_id') or warehouse.get('account_id')!=merchant:errors.append(prefix+'仓库未选择：点击右上“刷新仓库”读取店铺全部仓库，再从下拉框选择；仅一个仓库时自动应用到整组；多个时应用到勾选变体。')
  if setting.get('vat') not in ('0','0.05','0.07','0.1','0.2','0.22'):errors.append(prefix+'税率未填写：双击“实际增值税率”设置。')
  if setting.get('currency_code')!='CNY' or not setting.get('currency_confirmed'):errors.append(prefix+'币种未确认：双击“店铺币种”，输入CNY保存。')
 return errors
