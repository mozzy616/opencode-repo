import zipfile, os, hashlib, xml.etree.ElementTree as ET, time, shutil

repo = r'C:\Users\user\Workspace\kodi_all_in_one_app\repo.opencode'
tmp = os.path.join(repo, '_tmp_zips')
os.makedirs(tmp, exist_ok=True)
start = time.time()

addons_content = []
addons = []

# Scan repo/ subdirectory for addon sources
source_path = os.path.join(repo, 'repo')
zips_path = os.path.join(repo, 'repo', 'zips')

for d in sorted(os.listdir(source_path)):
    path = os.path.join(source_path, d)
    if not os.path.isdir(path) or d.startswith('.') or d.startswith('_') or d == 'zips':
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
        addons.append((d, root.get('id', d), root.get('version', '1.0.0')))
    except:
        addons.append((d, d, '1.0.0'))

# Build addons.xml
md = '<?xml version="1.0" encoding="UTF-8"?>\n<addons>\n'
for a in addons_content:
    md += a + '\n'
md += '</addons>\n'

with open(os.path.join(zips_path, 'addons.xml'), 'w', encoding='utf-8') as f:
    f.write(md)

h = hashlib.md5(md.encode('utf-8')).hexdigest()
with open(os.path.join(zips_path, 'addons.xml.md5'), 'w') as f:
    f.write(h)

print('addons.xml: %d addons (MD5: %s)' % (len(addons), h))

# Build zips in temp directory first (avoid zip-including-itself)
for dir_name, addon_id, addon_ver in addons:
    src = os.path.join(source_path, dir_name)
    zip_name = '%s-%s.zip' % (addon_id, addon_ver)
    zip_tmp = os.path.join(tmp, zip_name)
    zip_final = os.path.join(zips_path, addon_id, zip_name)
    os.makedirs(os.path.dirname(zip_final), exist_ok=True)

    if os.path.exists(zip_final):
        sz = os.path.getsize(zip_final)
        print('  SKIP %s (%d KB)' % (zip_name, sz // 1024))
        continue

    t0 = time.time()
    print('  BUILD %s...' % zip_name, end=' ', flush=True)
    try:
        with zipfile.ZipFile(zip_tmp, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            for root, dirs, files in os.walk(src):
                dirs[:] = [d for d in dirs if d != '__pycache__']
                for file in files:
                    if file.endswith(('.pdb', '.ilk', '.exp', '.lib', '.pyc', '.zip')):
                        continue
                    fp = os.path.join(root, file)
                    rel = os.path.relpath(fp, src)
                    zf.write(fp, os.path.join(addon_id, rel).replace('\\', '/'))
        shutil.move(zip_tmp, zip_final)
        sz = os.path.getsize(zip_final)
        print('(%d KB, %.0fs)' % (sz // 1024, time.time() - t0))
    except Exception as e:
        print('ERROR: %s' % e)
        if os.path.exists(zip_tmp):
            os.remove(zip_tmp)

# Root-level repo zip for manual install
root_zp = os.path.join(repo, 'repository.opencode.zip')
repo_src = os.path.join(source_path, 'repository.opencode')
with zipfile.ZipFile(root_zp, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
    for root, dirs, files in os.walk(repo_src):
        for file in files:
            fp = os.path.join(root, file)
            rel = os.path.relpath(fp, repo_src)
            zf.write(fp, os.path.join('repository.opencode', rel).replace('\\', '/'))

# Cleanup temp
shutil.rmtree(tmp, ignore_errors=True)
print('\nALL DONE in %.0fs' % (time.time() - start))
