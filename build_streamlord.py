import zipfile, os, hashlib, re

src = r'C:\Users\user\Workspace\kodi_all_one_app\opencode-repo\repo\plugin.video.streamlord'
dst = r'C:\Users\user\Workspace\kodi_all_one_app\opencode-repo\repo\zips\plugin.video.streamlord'
os.makedirs(dst, exist_ok=True)

with open(os.path.join(src, 'addon.xml'), 'r', encoding='utf-8') as f:
    content = f.read()
    m = re.search(r'<addon[^>]*version="([\d.]+)"', content)
    ver = m.group(1) if m else '3.6.0'
    addon_xml = content

zip_name = 'plugin.video.streamlord-%s.zip' % ver
zip_path = os.path.join(dst, zip_name)

for f in os.listdir(dst):
    if f.startswith('plugin.video.streamlord-'):
        os.remove(os.path.join(dst, f))

with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for file in files:
            fp = os.path.join(root, file)
            rel = os.path.relpath(fp, src)
            zf.write(fp, os.path.join('plugin.video.streamlord', rel).replace('\\', '/'))

sz = os.path.getsize(zip_path)
print('Created: %s (%d KB)' % (zip_name, sz // 1024))

# Update root addons.xml
def write_addons_xml(target_dir, all_addons):
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

repo_root = r'C:\Users\user\Workspace\kodi_all_one_app\opencode-repo'
all_addons = []
for d in sorted(os.listdir(repo_root + r'\repo')):
    ap = os.path.join(repo_root, 'repo', d, 'addon.xml')
    if os.path.exists(ap) and d != 'zips':
        with open(ap, 'r', encoding='utf-8') as f:
            a = f.read()
            if a.startswith('<?xml'):
                a = a.split('?>', 1)[1].strip()
            all_addons.append(a)

h, n = write_addons_xml(repo_root, all_addons)
print('Root addons.xml: %d addons (MD5: %s)' % (n, h))

h2, n2 = write_addons_xml(repo_root + r'\repo\zips', all_addons)
print('Zips addons.xml: %d addons (MD5: %s)' % (n2, h2))
print('Done')
