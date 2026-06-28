import zipfile, os, hashlib, re

repo_src = r'C:\Users\user\Workspace\kodi_all_one_app\opencode-repo\repo'
repo_zips = r'C:\Users\user\Workspace\kodi_all_one_app\opencode-repo\repo\zips'

all_addons = []
for d in sorted(os.listdir(repo_src)):
    ap = os.path.join(repo_src, d, 'addon.xml')
    if not os.path.exists(ap) or d == 'zips':
        continue
    with open(ap, 'r', encoding='utf-8') as f:
        content = f.read()
        a = content
        if a.startswith('<?xml'):
            a = a.split('?>', 1)[1].strip()
        all_addons.append(a)
        m = re.search(r'<addon[^>]*id="([^"]+)"[^>]*version="([\d.]+)"', content)
        if not m:
            continue
        addon_id, addon_ver = m.group(1), m.group(2)
        zip_name = '%s-%s.zip' % (addon_id, addon_ver)
        zip_dir = os.path.join(repo_zips, addon_id)
        os.makedirs(zip_dir, exist_ok=True)
        zip_path = os.path.join(zip_dir, zip_name)
        for f in os.listdir(zip_dir):
            if f.startswith(addon_id + '-'):
                os.remove(os.path.join(zip_dir, f))
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(os.path.join(repo_src, d)):
                dirs[:] = [dr for dr in dirs if dr != '__pycache__']
                for file in files:
                    fp = os.path.join(root, file)
                    rel = os.path.relpath(fp, os.path.join(repo_src, d))
                    zf.write(fp, os.path.join(addon_id, rel).replace('\\', '/'))
        sz = os.path.getsize(zip_path)
        print('Zipped: %s (%d KB)' % (zip_name, sz // 1024))

def write_addons_xml(target_dir):
    md = '<?xml version="1.0" encoding="UTF-8"?>\n<addons>\n'
    for a in all_addons:
        md += a + '\n'
    md += '</addons>'
    with open(os.path.join(target_dir, 'addons.xml'), 'w', encoding='utf-8') as f:
        f.write(md)
    h = hashlib.md5(md.encode('utf-8')).hexdigest()
    with open(os.path.join(target_dir, 'addons.xml.md5'), 'w') as f:
        f.write(h)
    return h, len(all_addons)

h, n = write_addons_xml(r'C:\Users\user\Workspace\kodi_all_one_app\opencode-repo')
print('Root addons.xml: %d addons (MD5: %s)' % (n, h))

h2, n2 = write_addons_xml(repo_zips)
print('Zips addons.xml: %d addons (MD5: %s)' % (n2, h2))
print('Done')
