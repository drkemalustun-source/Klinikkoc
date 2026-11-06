#!/usr/bin/env python3
"""Açık lisanslı görselleri lisans bilgisiyle birlikte indirir.

    python3 tools/acik-gorsel-indir.py <ders-kimligi>

Okur:   lessons/<id>/kaynaklar/acik-gorsel-istek.json
          { "commons": ["File:Ad.jpg", ...],
            "pmc": [{"pmcid": "PMC123", "kisa": "Yazar ve ark. 2024"}] }
Yazar:  lessons/<id>/assets/acik/<dosya>        (görseller, en çok 1600 px genişlik)
        lessons/<id>/kaynaklar/acik-gorseller.json (her görselin lisansı, yazarı, kaynağı, açıklaması)

Yalnız CC0, kamu malı, CC BY ve CC BY-SA kabul edilir. NC (ticari olmayan) ve ND (türetilemez)
lisanslar ile lisansı okunamayanlar atlanır ve raporda nedeniyle listelenir.
Bağımlılık yok; Python 3.8+ yeterli. İnternet erişimi gerekir.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = 'AkilliTahta/1.0 (acik kaynakli egitim uygulamasi; lisans denetimli indirme)'
GENISLIK = 1600


def get(url, binary=False):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    time.sleep(0.5)  # sunuculara nazik davran
    return data if binary else data.decode('utf-8')


def duz(html):
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', html or ''))).strip()


def lisans_uygun(ad):
    a = (ad or '').lower().replace('-', ' ')
    if not a:
        return False, 'lisans okunamadı'
    if ' nc' in f' {a}' or 'noncommercial' in a or 'non commercial' in a:
        return False, 'ticari olmayan (NC) lisans'
    if ' nd' in f' {a}' or 'noderiv' in a or 'no deriv' in a:
        return False, 'türetilemez (ND) lisans'
    if 'cc0' in a or 'public domain' in a or a.startswith('pd') or 'kamu' in a:
        return True, ''
    if 'cc by' in a or 'attribution' in a:
        return True, ''
    return False, f'tanınmayan lisans: {ad}'


def guvenli_ad(s):
    s = re.sub(r'[^A-Za-z0-9._-]+', '-', s).strip('-')
    return s[:80] or 'gorsel'


def commons(baslik, hedef):
    q = urllib.parse.urlencode({'action': 'query', 'format': 'json', 'titles': baslik, 'prop': 'imageinfo',
                                'iiprop': 'url|extmetadata|size|mime', 'iiurlwidth': GENISLIK})
    d = json.loads(get('https://commons.wikimedia.org/w/api.php?' + q))
    sayfa = next(iter(d['query']['pages'].values()))
    if 'imageinfo' not in sayfa:
        return None, 'dosya bulunamadı'
    ii = sayfa['imageinfo'][0]
    m = {k: v.get('value', '') for k, v in ii.get('extmetadata', {}).items()}
    lis = m.get('LicenseShortName', '')
    ok, neden = lisans_uygun(lis)
    if not ok:
        return None, neden
    url = ii.get('thumburl') or ii['url']
    uz = Path(urllib.parse.urlparse(url).path).suffix or '.jpg'
    ad = guvenli_ad(Path(baslik.split(':', 1)[-1]).stem) + uz
    (hedef / ad).write_bytes(get(url, binary=True))
    return {
        'dosya': 'assets/acik/' + ad, 'kaynak': 'Wikimedia Commons', 'baslik': baslik,
        'yazar': duz(m.get('Artist')), 'lisans': lis, 'lisans_url': m.get('LicenseUrl', ''),
        'sayfa': ii.get('descriptionurl', ''), 'aciklama': duz(m.get('ImageDescription'))[:600],
    }, ''


def pmc(girdi, hedef, rapor):
    pmcid = girdi['pmcid']
    q = urllib.parse.urlencode({'query': f'PMCID:{pmcid}', 'resultType': 'core', 'format': 'json'})
    d = json.loads(get('https://www.ebi.ac.uk/europepmc/webservices/rest/search?' + q))
    sonuc = (d.get('resultList', {}).get('result') or [{}])[0]
    lis = sonuc.get('license', '')
    ok, neden = lisans_uygun(lis)
    if not ok:
        rapor.append(f'{pmcid}: atlandı ({neden})')
        return []
    atif = f"{sonuc.get('authorString', '')} {sonuc.get('title', '')} {sonuc.get('journalInfo', {}).get('journal', {}).get('isoabbreviation', '')} {sonuc.get('pubYear', '')}. doi:{sonuc.get('doi', '')}"
    xml = get(f'https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML')
    kok = ET.fromstring(xml)
    XL = '{http://www.w3.org/1999/xlink}href'
    cikti = []
    for fig in kok.iter('fig'):
        g = fig.find('.//graphic')
        if g is None or not g.get(XL):
            continue
        href = g.get(XL)
        etiket = ''.join(fig.findtext('label') or '').strip()
        alt = duz(ET.tostring(fig.find('caption'), encoding='unicode')) if fig.find('caption') is not None else ''
        veri = None
        for aday in (f'https://europepmc.org/articles/{pmcid}/bin/{href}.jpg',
                     f'https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/bin/{href}.jpg'):
            try:
                veri = get(aday, binary=True)
                if veri[:3] == b'\xff\xd8\xff':
                    break
                veri = None
            except Exception:
                veri = None
        if not veri:
            rapor.append(f'{pmcid} {etiket or href}: görsel indirilemedi')
            continue
        ad = guvenli_ad(f'{pmcid}-{etiket or href}') + '.jpg'
        (hedef / ad).write_bytes(veri)
        cikti.append({'dosya': 'assets/acik/' + ad, 'kaynak': 'Europe PMC', 'baslik': f'{girdi.get("kisa", pmcid)}, {etiket}'.strip(', '),
                      'yazar': sonuc.get('authorString', ''), 'lisans': lis.upper(),
                      'atif': atif.strip(), 'sayfa': f'https://europepmc.org/article/PMC/{pmcid}', 'aciklama': alt[:600]})
    return cikti


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    ders = ROOT / 'lessons' / sys.argv[1]
    istek = json.loads((ders / 'kaynaklar' / 'acik-gorsel-istek.json').read_text(encoding='utf-8'))
    hedef = ders / 'assets' / 'acik'
    hedef.mkdir(parents=True, exist_ok=True)
    kayit, rapor = [], []
    for b in istek.get('commons', []):
        try:
            k, neden = commons(b, hedef)
            if k:
                kayit.append(k); print('✓', b, '·', k['lisans'])
            else:
                rapor.append(f'{b}: atlandı ({neden})')
        except Exception as e:
            rapor.append(f'{b}: hata ({e})')
    for g in istek.get('pmc', []):
        try:
            ks = pmc(g, hedef, rapor)
            kayit += ks; print('✓', g['pmcid'], '·', len(ks), 'şekil')
        except Exception as e:
            rapor.append(f"{g['pmcid']}: hata ({e})")
    (ders / 'kaynaklar' / 'acik-gorseller.json').write_text(
        json.dumps({'gorseller': kayit, 'atlananlar': rapor}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'\n{len(kayit)} görsel indirildi → {hedef.relative_to(ROOT)}')
    for r in rapor:
        print('  –', r)


if __name__ == '__main__':
    main()
