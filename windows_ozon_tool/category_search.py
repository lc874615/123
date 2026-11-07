"""Search the official bilingual commission workbook without translating IDs."""
def commission_options(config,query=''):
 terms=query.casefold().split();result=[];seen=set()
 for row in config.get('records',[]):
  if row.get('brand','').strip().casefold()!='all':continue
  text=' '.join(str(row.get(k) or '') for k in ('type_zh','type_ru','category_zh','category_ru','market_ru')).casefold()
  if not all(term in text for term in terms):continue
  key=(row['type_ru'],row.get('category_ru',''),tuple(row['rates']))
  if key in seen:continue
  seen.add(key);result.append(row)
 return sorted(result,key=lambda row:(row.get('type_zh') or row['type_ru'],row['type_ru'],row['source_row']))

def category_label(category,config):
 name=category.get('name','')
 matches=[r for r in config.get('records',[]) if r.get('type_ru','').strip().casefold()==name.strip().casefold()]
 chinese=next((r.get('type_zh') for r in matches if r.get('type_zh')),None)
 return ((chinese+'（'+name+'）') if chinese else name or str(category.get('type_id','')))+' | '+category.get('path','')
