import zipfile, os, hashlib, xml.etree.ElementTree as ET

repo = r'C:\Users\user\Workspace\kodi_all_in_one_app\repo.opencode'

addons_content = []

for d in sorted(os.listdir(repo)):
    path = os.path.join(repo, d)
    if not os.path.isdir(path) or d.startswith('.'):
        continue
    axml = os.path.join(path, 'addon.xml')
    if not os.path.exists(axml):
        continue
    
    with open(axml, 'r', encoding='utf-8') as f:
        content = f.read()
    if content.startswith('<?xml'):
        content = content.split('?>', 1)[1].strip()
    addons_content.append(content)
    
    try:
        root = ET.fromstring(content)
        addon_id = root.get('id', d)
        addon_ver = root.get('version', '1.0.0')
    except:
        addon_id, addon_ver = d, '1.0.0'
    
    zip_dir = os.path.join(repo, addon_id)
    os.makedirs(zip_dir, exist_ok=True)
    zip_name = f'{addon_id}-{addon_ver}.zip'
    zip_path = os.path.join(zip_dir, zip_name)
    
    if os.path.exists(zip_path):
        sz = os.path.getsize(zip_path)
        print(f'SKIP: {zip_name} ({sz//1024} KB)')
        continue
    
    print(f'Zipping: {addon_id}...', end=' ', flush=True)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(path):
            for file in files:
                fp = os.path.join(root, file)
                rel = os.path.relpath(fp, path)
                zf.write(fp, os.path.join(addon_id, rel).replace('\\', '/'))
    sz = os.path.getsize(zip_path)
    print(f'{sz//1024} KB')

# Build addons.xml
md = '<?xml version="1.0" encoding="UTF-8"?>\n<addons>\n'
for a in addons_content:
    md += a + '\n'
md += '</addons>'

with open(os.path.join(repo, 'addons.xml'), 'w', encoding='utf-8') as f:
    f.write(md)

h = hashlib.md5(md.encode('utf-8')).hexdigest()
with open(os.path.join(repo, 'addons.xml.md5'), 'w') as f:
    f.write(h)

print(f'addons.xml: {len(addons_content)} addons (MD5: {h})')

# Create root-level repo zip for manual install
root_zip = os.path.join(repo, 'repository.opencode.zip')
src = os.path.join(repo, 'repository.opencode')
with zipfile.ZipFile(root_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(src):
        for file in files:
            fp = os.path.join(root, file)
            rel = os.path.relpath(fp, src)
            zf.write(fp, os.path.join('repository.opencode', rel).replace('\\', '/'))
print(f'Manual install zip: {os.path.getsize(root_zip)} bytes')
print('Done')
