"""배포 패치 만들기: 빌드 롬과 원본 롬으로 xdelta 를 만들고, 되돌려 적용해 해시를 맞춘 뒤
README_KO.txt 와 함께 zip 하나로 묶는다(1편 tools/make_release.py 와 같은 방식).
python -X utf8 tools/make_release.py v1.0f"""
from pathlib import Path
import hashlib, json, subprocess, sys, zipfile, zlib

ROOT = Path(__file__).resolve().parents[1]
XD = ROOT / 'tools/bin/xdelta3.exe'
SRC = ROOT / 'Custom Robo V2 (Japan).z64'
OUT = ROOT / 'build/Custom Robo V2 (Japan) [KO test].z64'
CODE = 'NCZJ'


def main(version):
    rep = json.loads((ROOT / 'manifests/full-build.json').read_text(encoding='utf-8'))
    assert not rep.get('off') and not rep.get('korean_wrap_fallback') and not rep.get('desc_overflow') \
        and not rep.get('overwide_lines') and not rep.get('key_dict_collisions'), '빌드 검사 항목이 비어 있지 않음'
    out = OUT.read_bytes()
    assert hashlib.md5(out).hexdigest() == rep['md5'], '빌드 롬이 마지막 빌드 기록과 다름'
    rel = ROOT / 'release' / version
    rel.mkdir(parents=True, exist_ok=True)
    patch = rel / f'{CODE}_KPatch_{version}.xdelta'
    if patch.exists():
        patch.unlink()
    subprocess.run([str(XD), '-9', '-S', 'djw', '-e', '-s', str(SRC), str(OUT), str(patch)], check=True)
    test = rel / '_applied.z64'
    subprocess.run([str(XD), '-d', '-f', '-s', str(SRC), str(patch), str(test)], check=True)
    sha = lambda b: hashlib.sha256(b).hexdigest()
    assert sha(test.read_bytes()) == sha(out)
    test.unlink()
    readme = (ROOT / 'docs/README_KO.txt').read_text(encoding='utf-8')
    readme = (readme.replace('{VERSION}', version).replace('{RESULT_SHA256}', sha(out))
              .replace('{RESULT_MD5}', hashlib.md5(out).hexdigest()).replace('{RESULT_CRC32}', '%08X' % (zlib.crc32(out) & 0xffffffff)))
    (rel / 'README_KO.txt').write_text(readme, encoding='utf-8')
    zp = rel / f'{CODE}_KPatch_{version}.zip'
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in (patch, rel / 'README_KO.txt'):
            z.write(p, p.name)
    print(json.dumps({'zip': str(zp.relative_to(ROOT)), 'patch_bytes': patch.stat().st_size,
                      'zip_bytes': zp.stat().st_size, 'result_md5': hashlib.md5(out).hexdigest()}, ensure_ascii=False))


if __name__ == '__main__':
    main(sys.argv[1])
