# Peri-implantitis pilot dersini üretir: ornek-dersler/peri-implantitis-cerrahi/ders.json (paketle.mjs --ornek ile denetlenir)
# Kaynak: Ramanauskaite A, Zhou W, Cafferata EA, Schwarz F. Periodontol 2000. 2026. doi:10.1111/prd.70052 (CC BY 4.0)
# Alt hedefler: ALT_HEDEFLER.json (v3.0, donmuş) — kimlikler ve etiketler aynen.
import json, sys

import os
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', '..', 'ornek-dersler', 'peri-implantitis-cerrahi', 'ders.json')
ALT = os.path.join(HERE, 'ALT_HEDEFLER.json')

CREDIT = 'Ramanauskaite ve ark., Periodontol 2000, 2026 · CC BY 4.0 · makaleden kırpılmıştır'

def say(text, *board, src=None, basis=None, sid=None, pause=None):
    st = {'id': sid, 'say': text}
    if board: st['board'] = list(board)
    if src: st['sourceRef'] = src
    if basis: st['basis'] = basis
    if pause is not None: st['pauseAfter'] = pause
    return st

def q(sid, goal, prompt, options=None, *, type='single', answer=None, expl=None, src=None,
      probe=False, kind=None, scenario=None, hints=None, targets=None):
    qq = {'type': type, 'goal': goal, 'prompt': prompt}
    if probe: qq['probe'] = True
    if kind: qq['kind'] = kind
    if scenario: qq['scenario'] = scenario
    if options is not None: qq['options'] = options
    if answer is not None: qq['answer'] = answer
    if hints: qq['hints'] = hints
    if targets: qq['targets'] = targets
    if expl: qq['explanation'] = expl
    if src: qq['sourceRef'] = src
    return {'id': sid, 'question': qq}

def o(text, correct=False, why=None, mis=None):
    d = {'text': text}
    if correct: d['correct'] = True
    if why: d['why'] = why
    if mis: d['misconception'] = mis
    return d

T = lambda text, sub=None: ({'type': 'title', 'text': text, 'subtitle': sub} if sub else {'type': 'title', 'text': text})
B = lambda items, title=None, cue=None: {k: v for k, v in {'type': 'bullets', 'items': items, 'title': title, 'cue': cue}.items() if v is not None}
P = lambda text, cue=None: {k: v for k, v in {'type': 'point', 'text': text, 'cue': cue}.items() if v is not None}
X = lambda text, style='note', cue=None: {k: v for k, v in {'type': 'text', 'text': text, 'style': style, 'cue': cue}.items() if v is not None}
TERM = lambda term, d, cue=None: {k: v for k, v in {'type': 'term', 'term': term, 'definition': d, 'cue': cue}.items() if v is not None}
IMG = lambda a, cap=None: {k: v for k, v in {'type': 'image', 'asset': a, 'caption': cap}.items() if v is not None}
def HL(region, label=None, cue=None, color=None, id=None, shape=None):
    d = {'type': 'highlight', 'region': [round(v, 3) for v in region]}
    for k, v in (('label', label), ('cue', cue), ('color', color), ('id', id), ('shape', shape)):
        if v is not None: d[k] = v
    return d
UNHL = lambda cue=None, id=None: {k: v for k, v in {'type': 'unhighlight', 'cue': cue, 'id': id}.items() if v is not None}
ZOOM = lambda r, cue=None: {k: v for k, v in {'type': 'zoom', 'region': r, 'cue': cue}.items() if v is not None}
UNZOOM = lambda cue=None: {k: v for k, v in {'type': 'unzoom', 'cue': cue}.items() if v is not None}
TABLE = lambda headers, rows, title=None, caption=None, cue=None: {k: v for k, v in {'type': 'table', 'headers': headers, 'rows': rows, 'title': title, 'caption': caption, 'cue': cue}.items() if v is not None}
FLOW = lambda nodes, title=None, direction=None, cue=None: {k: v for k, v in {'type': 'flow', 'nodes': nodes, 'title': title, 'direction': direction, 'cue': cue}.items() if v is not None}
CMP = lambda cols, title=None, cue=None: {k: v for k, v in {'type': 'compare', 'columns': cols, 'title': title, 'cue': cue}.items() if v is not None}
CLEAR = {'type': 'clear'}

# ---------- Şekil bölgeleri (kırpılmış görsele oranla, 0–1) ----------
# Şekil 1: altı çalışma sütunu
F1_COLS = [0.103, 0.252, 0.400, 0.550, 0.698, 0.847, 0.995]
def f1col(i, y0=0.02, y1=0.995):
    return [F1_COLS[i], y0, F1_COLS[i + 1] - F1_COLS[i], y1 - y0]
F1_CRIT = [0.0, 0.725, 1.0, 0.18]
# Şekil 2: 3 × 2 panel
def f2(i):
    c, r = i % 3, i // 3
    return [c / 3 + 0.005, r * 0.5 + 0.005, 1 / 3 - 0.01, 0.49]
# Şekil 3A tablo satır grupları, 3B sütunlar
F3A = {'tutarli': [0.04, 0.037, 0.955, 0.118], 'tutarsiz': [0.04, 0.155, 0.955, 0.455], 'belirsiz': [0.04, 0.61, 0.955, 0.388]}
F3B = {'tutarli': [0.14, 0.64, 0.22, 0.31], 'tutarsiz': [0.40, 0.17, 0.225, 0.78], 'belirsiz': [0.66, 0.17, 0.225, 0.78]}
# Şekil 4: PDF\'teki görsel kutularından hesaplandı (sayfa 8)
F4 = {'A': [0.012, 0.008, 0.49, 0.223], 'B': [0.525, 0.008, 0.463, 0.223], 'C': [0.012, 0.246, 0.49, 0.208],
      'D': [0.525, 0.246, 0.463, 0.208], 'E': [0.012, 0.459, 0.49, 0.2], 'F': [0.525, 0.459, 0.463, 0.2],
      'G': [0.316, 0.692, 0.352, 0.30]}
# Şekil 5 (sayfa 9)
F5 = {'A': [0.008, 0.016, 0.312, 0.495], 'B': [0.339, 0.016, 0.165, 0.495], 'C': [0.517, 0.016, 0.216, 0.495],
      'D': [0.741, 0.016, 0.243, 0.495], 'E': [0.008, 0.538, 0.235, 0.446], 'F': [0.253, 0.538, 0.285, 0.446],
      'G': [0.549, 0.538, 0.259, 0.446], 'H': [0.819, 0.538, 0.173, 0.446]}
# Şekil 6 üç panel
F6 = {'tani': [0.0, 0.0, 0.35, 1.0], 'cerrahi': [0.36, 0.0, 0.29, 1.0], 'ihk': [0.665, 0.0, 0.335, 1.0]}

assets = {
    'sekil1': {'src': 'assets/sekil1.jpg', 'alt': 'Altı karşılaştırmalı çalışmada rekonstrüktif tedavinin ve açık flep debridmanının başarısı yüzdelerini gösteren sütun grafiği; altında her çalışmanın izlem süresi ve başarı ölçütü.',
               'caption': 'Şekil 1. Birleşik başarı ölçütleri kullanan karşılaştırmalı çalışmalarda rekonstrüktif tedavinin ve açık flep debridmanının başarısı', 'credit': CREDIT + ' (s. 4)'},
    'sekil2': {'src': 'assets/sekil2.jpg', 'alt': 'Peri-implantitis kemik defekti sınıflaması: okluzal görünümde Ia, Ib, Ic, Id, Ie ve vestibül görünümünde Sınıf II.',
               'caption': 'Şekil 2. Peri-implantitise bağlı kemik defekti konfigürasyonlarının sınıflaması (Schwarz ve ark.)', 'credit': CREDIT + ' (s. 6)'},
    'sekil3a': {'src': 'assets/sekil3a.jpg', 'alt': 'Rekonstrüktif çalışmaların defekt konfigürasyonu tanımlarını tutarlı, tutarsız ve belirsiz diye gruplayan tablo.',
                'caption': 'Şekil 3A. Rekonstrüktif peri-implantitis çalışmalarında defekt konfigürasyonu tanımları', 'credit': CREDIT + ' (s. 7)'},
    'sekil3b': {'src': 'assets/sekil3b.jpg', 'alt': 'Sütun grafiği: çalışmaların %14,2\'si tutarlı, %42,9\'u tutarsız, %42,9\'u belirsiz.',
                'caption': 'Şekil 3B. Çevrili defekt yaklaşımıyla tutarlı çalışmaların sıklığı', 'credit': CREDIT + ' (s. 7)'},
    'sekil4': {'src': 'assets/sekil4.jpg', 'alt': '36 numaralı bölgedeki implantta rekonstrüktif tedavi olgusu: A–G panelleri.',
               'caption': 'Şekil 4. Rekonstrüktif cerrahi peri-implantitis tedavisi olgusu (bölge 36)', 'credit': CREDIT + ' (s. 8)'},
    'sekil5': {'src': 'assets/sekil5.jpg', 'alt': '13 numaralı bölgedeki implantta 3 duvarlı defektin rekonstrüktif tedavisi: A–H panelleri.',
               'caption': 'Şekil 5. Rekonstrüktif cerrahi işlem olgusu (bölge 13)', 'credit': CREDIT + ' (s. 9)'},
    'sekil6': {'src': 'assets/sekil6.jpg', 'alt': 'Makrofaj polarizasyonu analizinin iş akışı: tanı, cerrahi tedavi ve granülasyon dokusu eksizyonu, CD80 ve CD206 immünohistokimyasal boyama.',
               'caption': 'Şekil 6. Makrofaj polarizasyonu analizinin iş akışı', 'credit': CREDIT + ' (s. 14)'},
}

misconceptions = [
    {'id': 'Y1', 'goal': 'H1.b', 'text': 'Retrospektif bir çalışmada bulunan anlamlı odds oranı, o faktörün başarısızlığa yol açtığını kanıtlar.'},
    {'id': 'Y2', 'goal': 'H2.a', 'text': 'Rekonstrüktif tedavi, enflamasyonun klinik bulgularını açık flep debridmanından daha iyi giderir.'},
    {'id': 'Y3', 'goal': 'H2.b', 'text': '5 mm sondlama derinliği eşiği her klinik durumda katı biçimde uygulanmalıdır.'},
    {'id': 'Y4', 'goal': 'H6.b', 'text': 'Ksenogreft her defekt ve her hastada koşulsuz olarak en iyi greft materyalidir.'},
    {'id': 'Y5', 'goal': 'H6.d', 'text': 'Bariyer membran, rekonstrüktif tedavide her defekt tipinde belirgin klinik yarar sağlar.'},
    {'id': 'Y6', 'goal': 'H6.f', 'text': 'Cerrahi peri-implantitis tedavisinde sistemik antibiyotik rutin olarak verilmelidir.'},
    {'id': 'Y7', 'goal': 'H5.a', 'text': 'Periodontitis öyküsü ve sigara, cerrahi tedavi sonucunu tutarlı biçimde kötüleştirdiği kanıtlanmış faktörlerdir.'},
    {'id': 'Y8', 'goal': 'H4.g', 'text': 'Makrofaj polarizasyonunun cerrahi başarıyı belirlediği kanıtlanmıştır ve bugün tedavi hedefi olarak kullanılır.'},
]

sections = []
def section(id, title, goals, steps):
    for i, s in enumerate(steps):
        if s.get('id') is None: s['id'] = f'{id}-{i + 1}'
    sections.append({'id': id, 'title': title, 'goals': goals, 'steps': steps})

# =====================================================================
# G1 — Makaleyi ve başarıyı birlikte okuma (H1, H2)
# =====================================================================
section('giris', 'Bu makale nasıl bir çalışma?', ['H1.a'], [
    say('Bu derste tek bir makaleyi birlikte okuyacağız: Ramanauskaite ve arkadaşlarının 2026\'da Periodontology 2000\'de yayımlanan derlemesi. Konu, peri-implantitiste cerrahi tedavinin etkinliğini hangi faktörlerin etkilediğidir. {1}Makale bunları üç başlıkta toplar: cerrahi faktörler, implant bölgesine ait lokal faktörler ve hastaya bağlı faktörler.',
        T('Peri-implantitiste cerrahi tedavinin etkinliği', 'Ramanauskaite, Zhou, Cafferata, Schwarz · Periodontol 2000 · 2026'),
        FLOW(['Cerrahi faktörler', 'Lokal (implant bölgesi) faktörler', 'Hastaya bağlı faktörler'], title='Makalenin üç ekseni', cue=1),
        src='s. 1 · Özet'),
    say('Önce şunu bilmek gerekir: Bu bir anlatı derlemesidir, yani narrative review. {1}Yazarlar PubMed, EMBASE ve Cochrane Library\'de Ocak 2010 ile Kasım 2025 arasında yayımlanan çalışmaları taramıştır. {2}En az 6 ay izlemli randomize kontrollü çalışmalar, prospektif kontrollü çalışmalar ve prospektif ya da retrospektif olgu serileri, en az 10 hasta şartıyla derlemeye alınmıştır. Olgu sunumları, uzman görüşleri ve hayvan çalışmaları dışarıda bırakılmıştır.',
        CLEAR, T('Derlemenin tasarımı'),
        TERM('Anlatı derlemesi (narrative review)', 'Çalışmaları seçip anlatarak özetler; tüm verileri birleştiren yeni bir meta-analiz değildir.'),
        B(['3 veri tabanı: PubMed, EMBASE, Cochrane Library', 'Ocak 2010 – Kasım 2025'], title='Arama', cue=1),
        B(['RKÇ, prospektif KÇ, prospektif/retrospektif olgu serisi', 'İzlem ≥6 ay · ≥10 hasta (kontrollü çalışmada grup başına ≥5)', 'Dışlanan: olgu sunumu, uzman görüşü, preklinik, İngilizce olmayan'], title='Dahil etme', cue=2),
        src='s. 2–3 · 2, 2.1'),
    say('Taramada 916 kayıt bulunmuştur. {1}Başlık ve özet elemesinden sonra 76 makalenin tam metni değerlendirilmiş, sonunda 39 özgün çalışmayı bildiren 54 makale derlemeye alınmıştır. {2}Bu çalışmalar tedavi türüne göre gruplanmıştır: rekonstrüktif olmayan ya da rezektif tedavi 12 çalışma, rekonstrüktif tedavi 22 çalışma, farklı yöntemleri birlikte analiz eden 5 çalışma. Bunlardan yalnızca 4 randomize kontrollü çalışma iki yaklaşımı doğrudan karşılaştırır.',
        FLOW(['916 kayıt', '76 tam metin', '54 makale · 39 çalışma'], title='Seçim akışı', cue=1),
        TABLE(['Grup', 'Makale / çalışma', 'Tasarım'], [
            ['Rekonstrüktif olmayan / rezektif', '15 / 12', '4 RKÇ, 6 retrospektif, 2 prospektif'],
            ['Rekonstrüktif', '34 / 22', '13 RKÇ, 3 retrospektif, 6 prospektif'],
            ['Birlikte analiz eden', '5 / 5', '5 retrospektif'],
            ['İki yaklaşımı doğrudan karşılaştıran', '—', '4 RKÇ']], title='Dahil edilen çalışmalar', cue=2),
        src='s. 3 · 2.1'),
    q('giris-q1', 'H1.a', 'Bu makalenin tasarımı için hangisi doğrudur?', [
        o('Çalışmaları seçip özetleyen bir anlatı derlemesidir.', True),
        o('Tüm çalışmaların verilerini birleştiren yeni bir meta-analizdir.', why='Makale yeni bir meta-analiz yapmaz; yer yer başka meta-analizlerin sonuçlarını aktarır.'),
        o('Yazarların yürüttüğü tek bir randomize kontrollü çalışmadır.', why='Makale 39 çalışmayı derler; kendisi bir klinik çalışma değildir.')],
      probe=True, expl='Makale bir anlatı derlemesidir: 2010–2025 arasındaki 39 çalışmayı derler ve başka meta-analizlerin bulgularını aktarır.', src='s. 1–3 · Özet, 2'),
])

section('kanit', 'Kanıt çeşitliliği ve genelleme sınırı', ['H1.b'], [
    say('Dahil edilen çalışmalar birbirine benzemez. {1}Randomize çalışmalarla retrospektif analizler yan yana durur. İzlem süreleri 6 aydan 10 yıla kadar uzanır. {2}Daha önemlisi, her çalışma "başarı"yı kendi ölçütüyle tanımlar. Örneğin dört randomize çalışmada başarı, farklı birleşik tanımlara göre bildirilmiştir.',
        T('Kanıt neden tek bir sayıya inmez?'),
        B(['RKÇ + prospektif + retrospektif tasarımlar', 'İzlem: 6 ay – 10 yıl', 'Örneklem birimi: kimi hasta, kimi implant'], title='Heterojenlik', cue=1),
        X('Başarı ölçütü çalışmadan çalışmaya değişir; oranlar doğrudan karşılaştırılamaz.', 'key', cue=2),
        src='s. 2–3 · 2.1, 3.2'),
    say('Bu yüzden derlemedeki ilişkileri dikkatle okumak gerekir. {1}Pek çok bulgu retrospektif analizlerdeki odds oranlarından gelir. Bu oranlar bir faktörün kötü sonuçla ilişkili olduğunu gösterir; o faktörün sonucu doğurduğunu tek başına kanıtlamaz. {2}Bir de şunu not edelim: Tüm çalışmaları özetleyen Ek Tablo S1, ders paketimizde yoktur. Derlemenin S1\'e gönderme yaptığı yerlerde ayrıntıyı biz göremiyoruz.',
        TERM('İlişki ≠ nedensellik', 'Retrospektif bir analizde anlamlı odds oranı, faktör ile sonuç arasında ilişki olduğunu gösterir; nedeni kanıtlamaz.', cue=1),
        X('Ek Tablo S1 bu pakette yok. Ders yalnızca makalenin ana metnine ve şekillerine dayanır.', 'warn', cue=2),
        src='s. 3 · 2.1, 3.2', basis='inference'),
    q('kanit-q1', 'H1.b', 'Retrospektif bir analizde "maksiller implantlarda nüks riski anlamlı olarak daha yüksek (OR 9,69)" bulunmuş olsun. Bu bulgudan en doğru çıkarım hangisidir?', [
        o('Maksiller konum ile nüks arasında bir ilişki gözlenmiştir; bu tek başına nedensellik kanıtı değildir.', True),
        o('Maksiller konum nükse yol açar; maksillaya implant yerleştirmekten kaçınılmalıdır.', why='Retrospektif bir ilişki nedensellik kanıtı değildir; ayrıca makale konum etkisini tutarsız bulur.', mis='Y1'),
        o('OR 9,69 olduğu için her maksiller implant tedaviden sonra nüks eder.', why='Odds oranı her olguda sonucun gerçekleşeceği anlamına gelmez.')],
      probe=True, targets=['Y1'], hints=['Bulgu hangi çalışma tasarımından geliyor?', 'İlişki ile neden arasındaki farkı düşünün.'],
      expl='Retrospektif analizler ilişki gösterir. Makale de implant konumunun etkisinin yeterince incelenmediğini ve bulguların tutarsız olduğunu vurgular.', src='s. 12 · 4.3; s. 17 · 6'),
])

section('basari', 'Başarı nasıl tanımlanır?', ['H2.b'], [
    say('Cerrahi tedavinin ana amacı peri-implant doku sağlığını yeniden kurmak, sert ve yumuşak dokuların uzun süreli stabilitesini sağlamaktır. {1}Güncel klinik uygulama kılavuzuna göre başarı, tedavi yöntemi ne olursa olsun, şu üç koşulla tanımlanır: sondlamada kanamanın en fazla bir bölgede olması, süpürasyon olmaması ve sondlama derinliğinin 5 milimetre veya altında olması.',
        T('Tedavi başarısı'),
        B(['BOP ≤1 bölge', 'Süpürasyon (Sup) yok', 'PD ≤5 mm'], title='Kılavuz tanımı', cue=1),
        src='s. 2 · 1'),
    say('Ancak yazarlar bir uyarı ekler. {1}5 milimetrelik eşiği katı uygulamak bazı durumlarda yanıltıcı olabilir. İmplant derine yerleştirilmişse ya da suprakrestal yumuşak dokular kalınsa, 6 ile 7 milimetrelik derinlikler de peri-implant sağlıkla bağdaşabilir. {2}Rekonstrüktif işlemlerin ise ek amaçları vardır: kaybedilen kemiği rejenere etmek, yeniden osseointegrasyonu desteklemek ve yumuşak doku seviyesini korumak.',
        X('PD 6–7 mm; derin yerleştirilmiş implantta veya kalın suprakrestal yumuşak dokuda sağlıkla bağdaşabilir.', 'warn', cue=1),
        B(['Kemik rejenerasyonu', 'Yeniden osseointegrasyon', 'Yumuşak doku seviyesinin korunması'], title='Rekonstrüktif tedavinin ek amaçları', cue=2),
        src='s. 2 · 1'),
    say('Başarı oranları neden bu kadar dağınık? {1}Farklı ölçütlere dayanan oranlar, 1 ile 7 yıllık izlemde, rekonstrüktif olmayan yaklaşımlarda hastaların yüzde 33\'ü ile 75\'i, rekonstrüktif yaklaşımlarda yüzde 11\'i ile 66,6\'sı arasında değişir. {2}Bu aralıklar, iki yaklaşımdan birinin "daha başarılı" olduğunu söylemeye yetmez; ölçütler farklıdır.',
        TABLE(['Yaklaşım', 'Başarı (hasta yüzdesi)', 'İzlem'], [['Rekonstrüktif olmayan', '%33 – %75', '1–7 yıl'], ['Rekonstrüktif', '%11 – %66,6', '1–7 yıl']], title='Bildirilen başarı oranları', caption='Oranlar farklı başarı ölçütlerine dayanır.', cue=1),
        X('Farklı tanımlarla elde edilmiş oranlar doğrudan karşılaştırılmaz.', 'key', cue=2),
        src='s. 2–3 · 1'),
    q('basari-q1', 'H2.b', 'Kılavuz tanımına göre aşağıdaki bulgulardan hangisi cerrahi tedavi başarısıyla bağdaşmaz?', [
        o('Bir bölgede sondlamada kanama'),
        o('Süpürasyon', True),
        o('4 mm sondlama derinliği')],
      probe=True, expl='Kılavuz tanımı: BOP en fazla bir bölgede, süpürasyon yok, PD ≤5 mm. Süpürasyonun varlığı başarı tanımını karşılamaz.', src='s. 2 · 1'),
    q('basari-q2', 'H2.b', 'Bu implant için hangi değerlendirme makalenin uyarısına en uygundur?', [
        o('PD 5 mm\'nin üstünde olduğu için tedavi kesinlikle başarısızdır.', why='Makale, 5 mm eşiğinin katı uygulanmasının bu tür durumlarda yanıltıcı olabileceğini söyler.', mis='Y3'),
        o('Derin yerleştirilmiş implantta enflamasyon bulgusu yoksa 6 mm derinlik peri-implant sağlıkla bağdaşabilir.', True),
        o('Sondlama derinliğinin hiçbir önemi yoktur; yalnız radyografiye bakılır.', why='Sondlama derinliği başarı tanımının bir parçasıdır; makale yalnızca eşiğin bağlama göre okunmasını önerir.')],
      kind='application', targets=['Y3'],
      scenario='Kurgusal bir olgu: Derin yerleştirilmiş bir implantta cerrahi tedaviden 12 ay sonra sondlamada kanama ve süpürasyon yok, en derin sondlama derinliği 6 mm.',
      expl='Makaleye göre derin yerleştirilmiş implantlarda ya da kalın suprakrestal yumuşak dokuda 6–7 mm derinlik sağlıkla bağdaşabilir. Eşik bağlamla birlikte okunur.', src='s. 2 · 1'),
])

section('sonuc-turu', 'Klinik ve radyografik sonuç ayrı şeyler', ['H2.a'], [
    say('Şimdi makalenin ilk şekline bakalım. {1}Şekil 1, iki yaklaşımı doğrudan karşılaştıran dört randomize çalışmanın altı yayınını gösterir: rekonstrüktif tedavi kırmızı, açık flep debridmanı mavi. {2}Başarı, 12 ay ile 3 yıl arasında, rekonstrüktif tedavide implantların yüzde 13,5\'i ile 85\'i, açık flep debridmanında yüzde 5\'i ile 90\'ı arasında değişmiştir.',
        T('Rekonstrüktif tedavi ve açık flep debridmanı'),
        IMG('sekil1'),
        HL([0.07, 0.03, 0.93, 0.62], 'Test (kırmızı) · Kontrol (mavi)', cue=1, id='bar'),
        UNHL(cue=2, id='bar'),
        HL(f1col(2, 0.05, 0.66), '%42,9 / %5', cue=2, id='hi'),
        HL(f1col(5, 0.03, 0.66), '%85 / %90', cue=2, color='ok', id='hi2'),
        src='s. 3–4 · 3.2, Şekil 1'),
    say('Sütunların altına bakın. {1}Her çalışmanın başarı ölçütü farklıdır. Kimi çalışma yalnızca klinik ölçütler kullanır, kimisi ek kemik kaybı olmamasını ya da radyografik defekt dolumunu da şart koşar. {2}Radyografik defekt dolumunu ölçüte katan iki Renvert çalışmasında oranlar rekonstrüktif grup lehinedir; dolumu şart koşmayan dört çalışmada ise oranlar sayısal olarak açık flep debridmanı lehinedir.',
        UNHL(),
        HL(F1_CRIT, 'Başarı ölçütleri', cue=1, id='crit'),
        UNHL(cue=2, id='crit'),
        ZOOM([0.36, 0.3, 0.38, 0.62], cue=2),
        HL([0.4, 0.725, 0.298, 0.18], 'Radyografik dolum', cue=2, color='warn', id='r1'),
        src='s. 4 · Şekil 1', basis='inference'),
    say('Makalenin sonucu açıktır. {1}12 aylık iki randomize çalışmada rekonstrüktif gruplar anlamlı olarak daha fazla radyografik defekt dolumu göstermiştir; klinik parametreler ise, yani sondlamada kanama, sondlama derinliği ve orta-bukkal çekilmedeki azalma, gruplar arasında benzer kalmıştır. {2}Meta-analizler de aynı tabloyu destekler: daha fazla radyografik dolum, benzer enflamasyon azalması. {3}Bir meta-analizde rekonstrüktif tedavi yumuşak doku seviyesini korumada avantajlı bulunmuştur; çekilmede ağırlıklı ortalama fark eksi 1,35 milimetredir. Ancak bir randomize çalışmada 12. ayda görülen daha az çekilme 3. yılda sürmemiştir.',
        CLEAR, T('Ne değişiyor, ne değişmiyor?'),
        CMP([
            {'title': 'Rekonstrüktif lehine', 'color': 'ok', 'items': ['Radyografik defekt dolumu', 'Yumuşak doku seviyesinin korunması (−1,35 mm çekilme farkı; meta-analiz)']},
            {'title': 'Benzer', 'color': 'accent', 'items': ['BOP azalması', 'PD azalması', 'Enflamasyonun giderilmesi']}], cue=1),
        X('Bir RKÇ\'de 12. aydaki yumuşak doku avantajı 3. yılda sürmemiştir.', 'warn', cue=3),
        src='s. 3 · 3.2'),
    say('Klinik açıdan bunun anlamı şudur: {1}Rekonstrüktif ya da rezektif yaklaşım seçilirken defekt dolumu hedefi, işlemin karmaşıklığı ve maliyetiyle birlikte tartılır. Sondlama derinliğinin azalması ve kanamanın giderilmesi gibi klinik iyileşmelerin iki yaklaşımda benzer olması beklenir.',
        X('Seçim: defekt dolumu hedefi ↔ karmaşıklık ve maliyet. Klinik iyileşme büyük olasılıkla benzer.', 'key', cue=1),
        src='s. 3 · 3.2'),
    q('sonuc-q1', 'H2.a', 'Rekonstrüktif tedaviyi açık flep debridmanıyla karşılaştıran çalışmalarda tutarlı olarak hangi sonuç rekonstrüktif tedavi lehinedir?', [
        o('Radyografik defekt dolumu', True),
        o('Sondlamada kanamanın daha fazla azalması', why='BOP ve PD azalması iki yaklaşımda benzer bulunmuştur.', mis='Y2'),
        o('Her izlem süresinde daha az yumuşak doku çekilmesi', why='Bir RKÇ\'de 12. aydaki avantaj 3. yılda sürmemiştir.')],
      probe=True, expl='Rekonstrüktif önlemler daha fazla radyografik defekt dolumu sağlar; enflamasyonun giderilmesi açık flep debridmanıyla benzerdir.', src='s. 3 · 3.2'),
    q('sonuc-q2', 'H2.a', 'Hangi beklenti makaleyle en uyumludur?', [
        o('Rekonstrüktif tedavi kanamayı belirgin biçimde daha iyi giderir; bu yüzden seçilmelidir.', why='Makaleye göre enflamasyonun giderilmesinde iki yaklaşım arasında belirgin fark gösterilmemiştir.', mis='Y2'),
        o('Enflamasyon azalması büyük olasılıkla benzer olur; rekonstrüktif tedavi daha fazla radyografik dolum sağlayabilir.', True),
        o('Açık flep debridmanı radyografik dolumda da rekonstrüktif tedaviye eşittir.', why='Radyografik dolum, rekonstrüktif önlemlerle tutarlı olarak daha fazladır.')],
      kind='application', targets=['Y2'],
      scenario='Kurgusal bir olgu: Hasta, rekonstrüktif tedavi önerilince "Böylece kanama açık flebe göre çok daha iyi geçer, değil mi?" diye soruyor.',
      hints=['Makale klinik ve radyografik sonuçları ayrı ayrı değerlendirir.'],
      expl='Klinik enflamasyon bulgularının giderilmesi iki yaklaşımda benzerdir. Rekonstrüktif tedavinin tutarlı avantajı radyografik defekt dolumundadır.', src='s. 3 · 3.2; s. 17 · 6'),
])

# =====================================================================
# G2 — Defekt ve cerrahi tercihlerin gerekçesi (H3, H6)
# =====================================================================
section('flep', 'Flep tasarımı', ['H6.a'], [
    say('Flep tasarımı, cerrahi travmayı ve hastanın ağrısını en aza indirirken defekte yeterli erişim sağlamalıdır. {1}Rekonstrüktif olmayan çalışmaların çoğunda geleneksel tam kalınlık erişim flebi kullanılmıştır: genellikle krestin ortasından bir insizyon, çoğu kez dikey rahatlatıcı insizyonlarla birlikte. Flepler cebi ortadan kaldırmak için apikale konumlandırılmış ya da sekonder iyileşmeye bırakılmıştır. {2}Rekonstrüktif çalışmalarda da çoğunlukla geniş erişimli tam kalınlık flepler kullanılmış, amaç ogmentasyon yapılan defektin üzerinde gerilimsiz primer kapanış olmuştur. Bu çoğu zaman periostu serbestleştiren insizyon gerektirmiştir.',
        T('Flep tasarımı'),
        CMP([
            {'title': 'Rekonstrüktif olmayan', 'items': ['Tam kalınlık erişim flebi', 'Orta-krestal insizyon ± dikey rahatlatıcı insizyon', 'Apikal konumlandırma / sekonder iyileşme']},
            {'title': 'Rekonstrüktif', 'color': 'ok', 'items': ['Geniş erişimli tam kalınlık flep', 'Gerilimsiz primer kapanış', 'Çoğu kez periost serbestleştirici insizyon']}], cue=1),
        src='s. 3 · 3.1'),
    say('Periodontitis tedavisinde papil koruyucu flepler gibi minimal invaziv tasarımlar öne çıkmıştır. {1}Ancak derlemedeki peri-implantitis çalışmalarının hiçbiri minimal invaziv flep tasarımı kullandığını açıkça bildirmemiştir. Peri-implantitis lezyonları genellikle çok daha geniştir ve çoğu zaman implantın çevresine tam erişim gerektirir. {2}Yeni bir flepsiz yaklaşım da denenmiştir: 117 hasta ve 338 implantlık büyük bir prospektif olgu serisinde flep kaldırmadan cep küretajı, 5 yılda implantların yüzde 54,4\'ünde hastalığın gerilemesini sağlamıştır. Bu orta düzeyde bir başarıdır ve kontrollü çalışmalarla doğrulanması gerekir.',
        X('Peri-implantitis çalışmalarında minimal invaziv flep tasarımı açıkça bildirilmemiştir.', 'note', cue=1),
        X('Flepsiz erişim: 117 hasta / 338 implant · 5 yılda implantların %54,4\'ünde gerileme · kontrollü çalışma gerekli', 'warn', cue=2),
        X('Sonuç: en uygun flep tasarımı konusunda kesin bir sonuca varılamamaktadır.', 'key', cue=2),
        src='s. 3 · 3.1; s. 1 · Özet'),
    q('flep-q1', 'H6.a', 'Peri-implantitis cerrahisinde flep tasarımı için makalenin vardığı sonuç hangisidir?', [
        o('Papil koruyucu minimal invaziv flep en iyi sonuçları vermiştir.', why='Derlemedeki çalışmaların hiçbiri minimal invaziv flep tasarımını açıkça bildirmemiştir.'),
        o('En uygun flep tasarımı konusunda kesin sonuca varılamaz.', True),
        o('Flepsiz yaklaşım, flepli yaklaşımdan üstün bulunmuştur.', why='Flepsiz yaklaşım yalnızca bir olgu serisinde orta düzeyde başarı göstermiştir; kontrollü karşılaştırma yoktur.')],
      probe=True, expl='Makale en uygun flep tasarımı konusunda kesin sonuca varılamadığını belirtir. Peri-implantitis lezyonları genellikle geniştir ve çevresel erişim gerektirir.', src='s. 1 · Özet; s. 3 · 3.1'),
])

section('defekt', 'Defekt morfolojisi', ['H3.a'], [
    say('Cerrahi yaklaşım seçimini büyük ölçüde peri-implant kemik defektinin morfolojisi belirler. {1}Şekil 2\'deki sınıflamaya göre Sınıf I, kemik duvarıyla çevrili kemik içi defekttir; okluzal görünümde bir a\'dan bir e\'ye kadar alt tipler gösterilmiştir. {2}Sınıf II, krestin üstünde yatay kemik kaybıdır. {3}Sınıf III ise kemik içi ve suprakrestal bileşenlerin birlikte olduğu kombine defekttir.',
        T('Peri-implant kemik defekti sınıflaması'),
        IMG('sekil2'),
        HL([0.0, 0.0, 1.0, 0.5], 'Sınıf I · Ia–Ie (okluzal görünüm)', cue=1, id='s1', color='ok'),
        HL([0.0, 0.5, 0.665, 0.5], cue=1, id='s1b', color='ok'),
        UNHL(cue=2, id='s1'),
        UNHL(cue=2, id='s1b'),
        HL(f2(5), 'Sınıf II (vestibül görünüm)', cue=2, color='warn', id='s2'),
        src='s. 5–6 · 3.5.1, Şekil 2'),
    say('Klinik verilere göre peri-implantitis bölgelerinin yaklaşık yüzde 79\'u kombine defekttir, yani Sınıf III\'tür. {1}Saf kemik içi lezyonlarda en sık görülen biçim, bukkal ve lingual duvarların korunduğu gerçek 4 duvarlı çembersel defekttir; kemik içi olguların yaklaşık yüzde 55\'i bu tiptedir. Onu fasiyal dehisens tipi 3 duvarlı defektler izler. {2}Saf yatay defektler ise görece nadirdir; oranları yaklaşık yüzde 2\'ye kadar düşebilir.',
        UNHL(id='s2'),
        HL(f2(4), 'Ie: çembersel', cue=1, color='ok', id='ie'),
        HL(f2(5), 'Sınıf II: ~%2', cue=2, color='warn', id='s2b'),
        src='s. 5 · 3.5.1'),
    say('Defekt morfolojisi neden önemli? {1}Bir randomize çalışmada anorganik sığır kemiği ve kolajen membranla yapılan rekonstrüktif tedavi, 6 ayda 4 duvarlı defektlerde 2 ya da 3 duvarlı defektlere göre anlamlı olarak daha fazla cep azalması ve ataşman kazancı sağlamıştır. {2}3 yıllık bir randomize çalışmada 4 duvarlı defektlerde başarı odds\'u 6 ila 7 kat yüksek bulunmuş, 7 yıllık izlem de bunu doğrulamıştır. {3}Defekt açısı da önemlidir: yaklaşık 40 derecelik dar defektlerde yaklaşık 1,85 milimetre radyografik kemik kazancı elde edilmiş; açı genişledikçe kazanç azalmıştır.',
        CLEAR, T('Duvar sayısı ve sonuç'),
        B(['RKÇ, 6 ay: 4 duvar > 2–3 duvar (PD azalması, ataşman kazancı)'], title='Çevrili defektler daha iyi', cue=1),
        P('RKÇ, 3 yıl: 4 duvarda başarı odds\'u 6–7 kat · 7 yılda doğrulandı', cue=2),
        P('Dar defekt açısı (~40°) → ~1,85 mm radyografik kemik kazancı', cue=3),
        src='s. 5 · 3.5.1'),
    say('Biyolojik gerekçe de bunu destekler. {1}Üç ya da dört kemik duvarı olan ve en az 3 milimetre derin defektler, pıhtı stabilizasyonu ve yeniden damarlanma için 1 ya da 2 duvarlı defektlerden daha elverişli bir ortam sağlar. Bu nedenle rejenerasyona daha uygun kabul edilir. {2}Şekil 4\'te 36 numaralı bölgede 4 milimetre derinliğinde çembersel kemik içi defekt görülür. {3}Defekt kolajenli sığır kemik mineraliyle homojen biçimde doldurulmuş, 12 ay sonra peri-implant doku sağlığı ve radyografik iyileşme izlenmiştir.',
        CLEAR, T('Olgu: 4 duvarlı defekt (bölge 36)'),
        IMG('sekil4'),
        TERM('Elverişli defekt', '3–4 duvar ve ≥3 mm derinlik: pıhtı stabilizasyonu ve yeniden damarlanma için daha uygun', cue=1),
        HL(F4['C'], 'C: 4 mm çembersel defekt', cue=2, id='c'),
        HL(F4['D'], 'D: greftle dolum', cue=3, color='ok', id='d'),
        HL(F4['G'], 'G: 12. ay radyografi', cue=3, color='ok', id='g'),
        src='s. 6 · 3.5.1; s. 8 · Şekil 4'),
    say('Şekil 5\'te ise 13 numaralı bölgede 3 duvarlı bir kemik içi defekt vardır. {1}Başlangıçta sondlamada yoğun kanama, süpürasyon ve 9 milimetreye varan sondlama derinlikleri görülür. {2}Defekt kolajenli sığır kemik mineraliyle yeniden yapılandırılmış, {3}iyileşme sonrası yumuşak doku yeniden şekillenmesini dengelemek için aynı seansta bağ dokusu grefti eklenmiştir. {4}12 ay sonra dokular sağlıklıdır ve radyografide defekt dolmuştur.',
        CLEAR, T('Olgu: 3 duvarlı defekt (bölge 13)'),
        IMG('sekil5'),
        HL(F5['A'], 'A: BOP, Sup, PD 9 mm', cue=1, color='warn', id='a'),
        HL(F5['C'], 'C: 3 duvarlı defekt', cue=2, id='c'),
        HL(F5['D'], 'D: dolum', cue=2, id='d'),
        HL(F5['E'], 'E: bağ dokusu grefti', cue=3, id='e'),
        HL(F5['G'], 'G: 12. ay', cue=4, color='ok', id='g'),
        HL(F5['H'], 'H: dolum', cue=4, color='ok', id='h'),
        src='s. 8–9 · Şekil 5'),
    q('defekt-q1', 'H3.a', 'Makaleye göre rekonstrüktif tedaviye en elverişli defekt hangisidir?', [
        o('1 duvarlı, geniş açılı defekt'),
        o('4 duvarlı, en az 3 mm derin, dar açılı defekt', True),
        o('Saf yatay (Sınıf II) kemik kaybı', why='Yatay defektte rejenerasyonu destekleyecek kemik duvarı yoktur; makaledeki avantajlar çevrili kemik içi defektler içindir.')],
      probe=True, hints=['Pıhtıyı ne tutar?'],
      expl='3–4 duvarlı ve en az 3 mm derin defektler pıhtı stabilizasyonu ve yeniden damarlanma için daha elverişlidir; dar açı da daha fazla kemik kazancıyla ilişkilidir.', src='s. 5–6 · 3.5.1'),
    q('defekt-q2', 'H3.a', 'Hangi değerlendirme makalenin gerekçesiyle en uyumludur?', [
        o('A daha elverişlidir; çünkü 4 duvar pıhtıyı tutar ve yeniden damarlanmayı destekler.', True),
        o('B daha elverişlidir; çünkü geniş defektte daha çok greft materyali yerleştirilebilir.', why='Makaleye göre geniş açılı defektlerde kemik kazancı daha azdır.'),
        o('İkisi arasında fark beklenmez; defekt morfolojisinin sonuçla ilişkisi yoktur.', why='Çalışmaların çoğu morfolojiyi rekonstrüktif sonucun temel belirleyicilerinden biri olarak bulmuştur.')],
      kind='application',
      scenario='Kurgusal iki implant: A implantında 4 mm derin, 4 duvarlı dar bir çembersel defekt; B implantında geniş açılı, yalnız 1 duvarı kalmış bir kemik içi defekt var. İkisine de rekonstrüktif tedavi düşünülüyor.',
      expl='3–4 duvarlı ve en az 3 mm derin defektler rejenerasyon için daha elverişlidir; dar açı da daha fazla kemik kazancıyla ilişkilidir.', src='s. 5–6 · 3.5.1'),
])

section('secim', 'Olgu seçimi ve materyal bağlamı', ['H3.b'], [
    say('Bütün veriler aynı yönde değildir. {1}Hacmi stabil kolajen matrikse gömülü bir kemik dolgusuyla yapılan 3 yıllık bir randomize çalışmada defekt konfigürasyonu ile sonuç arasında ilişki bulunmamış; aynı materyalin 5 yıllık değerlendirmesi de bunu doğrulamıştır. {2}Yazarlar bu farkın greft materyalinden kaynaklanabileceğini düşünür: Hacmi stabil iskeleler çevrili olmayan defektlerde de boşluğu koruyabilir; partiküllü greftler ise stabilite için defekt duvarlarına daha çok dayanır.',
        T('Morfoloji etkisi her materyalde aynı mı?'),
        X('Hacmi stabil kolajen matriks + kemik dolgusu: 3 ve 5 yılda defekt şekliyle ilişki yok', 'warn', cue=1),
        CMP([
            {'title': 'Hacmi stabil iskele', 'items': ['Çevrili olmayan defektte de boşluğu koruyabilir']},
            {'title': 'Partiküllü greft', 'items': ['Stabilite için defekt duvarlarına daha çok dayanır']}], title='Olası açıklama', cue=2),
        src='s. 5–6 · 3.5.1'),
    say('Şekil 3, rekonstrüktif çalışmaların hangi defektleri tedavi ettiğini gösterir. {1}Tabloda yalnızca üst bölümdeki birkaç çalışma, çevrili defekt yaklaşımıyla tutarlı tanımlar kullanır. {2}Ortadaki geniş grup bu yaklaşımla tutarsızdır; çevrili olmayan defektleri de almıştır ya da dışlamamıştır. {3}Alttaki grupta ise seçim ölçütü belirsizdir.',
        CLEAR, T('Rekonstrüktif çalışmalar hangi defektleri seçti?'),
        IMG('sekil3a'),
        HL(F3A['tutarli'], 'Tutarlı', cue=1, color='ok', id='t'),
        HL(F3A['tutarsiz'], 'Tutarsız', cue=2, color='warn', id='ts'),
        HL(F3A['belirsiz'], 'Belirsiz', cue=3, id='b'),
        src='s. 6–7 · 3.5.1, Şekil 3A'),
    say('Grafik olarak bakarsak: {1}çalışmaların yalnızca yüzde 14,2\'si tutarlıdır. {2}Yüzde 42,9\'unda seçim ölçütü çevrili defekt yaklaşımıyla tutarsızdır, yüzde 42,9\'unda ise belirsizdir. {3}Yani etkinlik çalışmalarında rekonstrüktif teknikler sıklıkla elverişsiz defekt morfolojilerinde denenmiştir. Yazarlara göre bu, sonuçların neden bu kadar değişken olduğunu kısmen açıklayabilir.',
        CLEAR, T('Seçim ölçütleri'),
        IMG('sekil3b'),
        HL(F3B['tutarli'], '%14,2', cue=1, color='ok', id='t'),
        HL(F3B['tutarsiz'], '%42,9', cue=2, color='warn', id='ts'),
        HL(F3B['belirsiz'], '%42,9', cue=2, id='b'),
        X('Rekonstrüktif teknikler sıklıkla elverişsiz morfolojide denenmiş → sonuçlardaki değişkenliğin bir kısmını açıklayabilir.', 'key', cue=3),
        src='s. 6 · 3.5.1, Şekil 3B'),
    q('secim-q1', 'H3.b', 'Rekonstrüktif tedavi sonuçları çalışmalar arasında neden bu kadar değişkendir? Makalede ileri sürülen açıklamalardan biri hangisidir?', [
        o('Çalışmaların çoğu yalnızca 4 duvarlı defektleri tedavi etmiştir.', why='Tersine: yalnız %14,2 tutarlı biçimde çevrili defekt yaklaşımı kullanmıştır.'),
        o('Pek çok çalışmada olgu seçimi belirsizdir ya da çevrili olmayan defektler de dahil edilmiştir.', True),
        o('Tüm çalışmalar aynı greft materyalini kullanmıştır.', why='Materyaller farklıdır; makale materyal farkını da olası bir açıklama olarak anar.')],
      probe=True, expl='Seçim ölçütleri %42,9 belirsiz, %42,9 çevrili defekt yaklaşımıyla tutarsızdır; bu durum değişkenliği kısmen açıklayabilir.', src='s. 6 · 3.5.1, Şekil 3'),
    q('secim-q2', 'H3.b', 'Hacmi stabil kolajen matriks içeren bir kemik dolgusuyla yapılan çalışmada defekt konfigürasyonu sonuçla ilişkili bulunmamıştır. Bu bulgu en doğru nasıl okunur?', [
        o('Defekt morfolojisi hiçbir durumda önemli değildir.', why='Bu genelleme yanlıştır; makaledeki çalışmaların çoğu morfolojiyi önemli bulmuştur.'),
        o('Morfolojinin etkisi kullanılan materyale göre değişebilir; bulgu o materyal bağlamında okunmalıdır.', True),
        o('Bu çalışma hatalıdır; dikkate alınmamalıdır.', why='Makale bu bulguyu dışlamaz, materyal farkıyla açıklamayı önerir.')],
      expl='Yazarlar farkı greft materyaliyle açıklamayı önerir: Hacmi stabil iskeleler çevrili olmayan defektlerde de boşluğu koruyabilir.', src='s. 5–6 · 3.5.1'),
])

section('greft', 'Greft materyali', ['H6.b'], [
    say('Greft materyalinin türü sonucu etkileyebilir. {1}3 ila 5 yıllık izlemli karşılaştırmalı bir çalışmada, ksenojen partiküllü dolguyla, yani deproteinize sığır kemik mineraliyle yapılan yönlendirilmiş kemik rejenerasyonu, otojen kemik parçacıklarına göre daha fazla cep ve kanama azalmasının yanı sıra daha fazla radyografik dolum sağlamıştır. {2}4 yılda ksenojen dolgu, alloplastik dolguya göre de daha iyi cep ve kanama azalması göstermiştir. {3}İki farklı ksenojen dolgu ise 12 ayda benzer sonuç vermiştir. {4}Titanyum granülleri, ksenojen partiküllere göre anlamlı olarak daha fazla radyografik dolum sağlamış; ancak klinik sonuçlar benzer kalmıştır.',
        T('Greft materyali seçimi'),
        TABLE(['Karşılaştırma', 'İzlem', 'Bulgu'], [
            ['DBBM (ksenojen) ↔ otojen kemik', '3–5 yıl', 'Ksenojen lehine: PD ve BOP azalması, radyografik dolum'],
            ['Ksenojen ↔ alloplastik', '4 yıl', 'Ksenojen lehine: PD ve BOP azalması'],
            ['Sığır HA ↔ DBBM', '12 ay', 'Benzer'],
            ['Titanyum granül ↔ ksenojen', '—', 'Titanyum: daha fazla radyografik dolum; klinik benzer']], cue=1),
        src='s. 4–5 · 3.3.1'),
    say('5 çalışmanın 12 aylık verisine dayanan bir ağ meta-analizi, ksenojen kemik kullanan protokollerin otojen kemiğe göre enflamasyonu anlamlı olarak daha iyi giderdiğini göstermiştir. {1}Yazarlar buradan şu sonuca varır: Yavaş rezorbe olan ksenojen ya da düşük rezorpsiyonlu greftler, orta vadede otojen kemiğe göre daha olumlu sonuç verebilir. {2}Ancak uzun dönem karşılaştırmalara hâlâ ihtiyaç vardır; defekt morfolojisi ve hasta faktörleri de belirleyici olabilir.',
        CLEAR, T('Yavaş rezorbe olan greftler'),
        X('Yavaş rezorbe olan ksenojen / düşük rezorpsiyonlu greftler → orta vadede otojen kemiğe göre daha olumlu sonuç **verebilir**.', 'key', cue=1),
        X('Sınır: uzun dönem karşılaştırma yok; defekt morfolojisi ve hasta faktörleri de rol oynayabilir.', 'warn', cue=2),
        src='s. 4–5 · 3.3.1'),
    q('greft-q1', 'H6.b', 'Makaleye göre greft materyali hakkında en doğru ifade hangisidir?', [
        o('Ksenogreft, her defekt ve her hastada koşulsuz olarak en iyi materyaldir.', why='Makale uzun dönem karşılaştırmaların eksik olduğunu ve morfoloji ile hasta faktörlerinin de rol oynayabileceğini vurgular.', mis='Y4'),
        o('Yavaş rezorbe olan greftler orta vadede otojen kemiğe göre daha olumlu sonuç verebilir; uzun dönem veri eksiktir.', True),
        o('Otojen kemik, biyolojik olduğu için en iyi sonucu verir.', why='Karşılaştırmalı veriler ksenojen dolguyu otojen kemiğe göre daha olumlu bulmuştur.')],
      probe=True, targets=['Y4'],
      expl='Yavaş rezorbe olan greftler orta vadede daha olumlu sonuç verebilir; ancak bu koşulsuz bir üstünlük değildir.', src='s. 4–5 · 3.3.1'),
    q('greft-q2', 'H6.b', 'Arkadaşınızın yorumu hakkında hangisi makaleyle en uyumludur?', [
        o('Doğrudur; ksenogreftin üstünlüğü her defekt tipinde ve uzun dönemde gösterilmiştir.', why='Uzun dönem karşılaştırmalar hâlâ gereklidir; morfoloji ve hasta faktörleri de rol oynayabilir.', mis='Y4'),
        o('Kısmen doğrudur; ksenojen greft orta vadede daha olumlu sonuç verebilir, ama defekt 1 duvarlıysa morfolojinin etkisi de hesaba katılmalıdır.', True),
        o('Yanlıştır; greft türünün sonuca etkisi yoktur.', why='Karşılaştırmalı çalışmalar greft türünün sonucu etkileyebileceğini gösterir.')],
      kind='application', targets=['Y4'],
      scenario='Kurgusal bir tartışma: Bir arkadaşınız, 1 duvarlı geniş bir defekt için "Ksenogreft koyarsak sonuç her durumda en iyisi olur; defektin şekli önemli değil" diyor.',
      hints=['Greft bulgusu hangi süreyi kapsıyor?', 'Defekt morfolojisi bölümünü hatırlayın.'],
      expl='Ksenojen greftin avantajı orta vadeli verilere dayanır ve koşulsuz değildir. Defekt morfolojisi ayrı ve önemli bir faktördür.', src='s. 4–6 · 3.3.1, 3.5.1'),
])

section('biyolojik', 'Biyolojik yardımcılar', ['H6.c'], [
    say('Biyolojik ajanların, yani mine matriks türevi, büyüme faktörleri ve trombosit konsantrelerinin, rekonstrüktif tedaviye ek katkısı konusunda kanıt sınırlıdır. {1}Bir randomize çalışmada ksenojen kemik ve kolajen membranla yapılan rejeneratif cerrahiye mine matriks türevi eklenmiş; 12. ayda cep azalması ve başarı oranı benzer kalmıştır. 5 yılda da açık flep debridmanıyla benzer sonuç alınmıştır. {2}Bir çalışmada trombositten zengin fibrin, 6. ayda cep azalmasında, ataşman kazancında ve keratinize dokuda ılımlı bir artış göstermiştir. {3}Hiyalüronik asit ise radyografik dolumu artırmış, ama cep ve kanama sonuçlarını değiştirmemiştir.',
        T('Biyolojik yardımcılar'),
        TABLE(['Ajan', 'Bulgu'], [
            ['Mine matriks türevi (EMD)', '12 ay: PD azalması ve başarı benzer · 5 yıl: AFD ile benzer'],
            ['Trombositten zengin fibrin (PRF)', '6 ay: PD, CAL, keratinize dokuda ılımlı kazanç (olası yarar)'],
            ['Hiyalüronik asit', 'Radyografik dolum ↑ · PD ve BOP farkı yok']], cue=1),
        src='s. 5 · 3.3.1'),
    say('Sonuç olarak, veriler sınırlı ve kısa dönemli olduğu için biyolojik ajanların eklenmesinin yararı hakkında kesin sonuç çıkarılamaz. {1}Makalenin son bölümü de aynı şeyi söyler: Kontrollü çalışmalarda anlamlı ek yarar gösterilmediği için büyüme faktörü, mine matriks türevi ya da trombositten zengin fibrinin rutin kullanımını destekleyecek kanıt yetersizdir.',
        X('Rutin kullanımı destekleyecek kanıt yetersiz.', 'key', cue=1),
        src='s. 5 · 3.3.1; s. 17 · 6'),
    q('biyo-q1', 'H6.c', 'Rekonstrüktif peri-implantitis tedavisinde biyolojik ajanlar (EMD, PRF, büyüme faktörleri) için makalenin vardığı sonuç hangisidir?', [
        o('Rutin kullanımlarını destekleyecek kanıt yetersizdir.', True),
        o('Mine matriks türevi, 12 ayda başarı oranını anlamlı olarak artırmıştır.', why='EMD eklenen ve eklenmeyen bölgelerde 12 ayda başarı oranı benzer bulunmuştur.'),
        o('Hiyalüronik asit, sondlama derinliğini belirgin biçimde azaltmıştır.', why='Hiyalüronik asit radyografik dolumu artırmış, PD ve BOP sonuçlarını değiştirmemiştir.')],
      probe=True, expl='Veriler sınırlı ve kısa dönemlidir; kontrollü çalışmalarda anlamlı ek yarar gösterilmemiştir.', src='s. 5 · 3.3.1; s. 17 · 6'),
])

section('membran', 'Bariyer membran', ['H6.d'], [
    say('Yönlendirilmiş kemik rejenerasyonunun ilkesi, greftin üzerine bir bariyer membran yerleştirip kemik rejenerasyonu için alan yaratmaktır. Membran greftin stabil kalmasına da yardım eder. {1}Ancak peri-implantitiste membranın klinik önemi tartışmalıdır. 4 yıllık bir çalışmada greft ve kolajen membran birlikte kullanıldığında daha fazla cep ve kanama azalması bildirilmiştir. {2}Buna karşılık birçok çalışma, 5 yıla kadar membranın ek klinik yararını gösterememiştir. Örneğin 12 aylık bir randomize çalışmada başarı, membranlı grupta yaklaşık yüzde 75, membransız grupta yüzde 79\'dur.',
        T('Bariyer membran'),
        CMP([
            {'title': 'Yarar bildiren', 'color': 'ok', 'items': ['4 yıl: ksenojen greft + doğal kolajen membran → daha fazla BOP ve PD azalması']},
            {'title': 'Ek yarar görmeyen', 'color': 'warn', 'items': ['Birçok çalışma, 5 yıla kadar', 'RKÇ 12 ay: başarı ~%75 (membranlı) / %79 (membransız)', '3 yıl: fark anlamlı değil']}], cue=1),
        src='s. 5 · 3.4'),
    say('Membranın bedeli de vardır. {1}Bir randomize çalışmada membran grubunda ağrı ve komplikasyon daha fazla görülmüştür: yüzde 19 yumuşak doku dehisensi, yüzde 9,5 membran açığa çıkması, yüzde 4,8 greft açığa çıkması. {2}Ayrıca bu çalışmaların çoğu 2, 3 ve 4 duvarlı defektleri birlikte analiz etmiştir. Yazarlara göre 1 ya da 2 duvarlı defektte membran daha kritik bir rol oynayabilir; 4 duvarlı defektte ise ek yararı az olabilir.',
        X('Membran grubunda: %19 yumuşak doku dehisensi · %9,5 membran açığa çıkması · %4,8 greft açığa çıkması', 'warn', cue=1),
        CMP([
            {'title': '1–2 duvarlı defekt', 'items': ['Membran daha gerekçeli olabilir']},
            {'title': '4 duvarlı defekt', 'items': ['Ek yarar az, belki gereksiz']}], title='Morfolojiye göre karar', cue=2),
        src='s. 5–6 · 3.4; s. 17 · 6', basis='source'),
    q('membran-q1', 'H6.d', 'Makaleye göre bariyer membran kullanımı için en doğru ifade hangisidir?', [
        o('Membran, her defekt tipinde belirgin klinik yarar sağlar.', why='Genel olarak açık bir klinik yarar gösterilmemiştir.', mis='Y5'),
        o('Genel olarak açık bir klinik yarar gösterilmemiştir; kullanımı defekt morfolojisine göre tartılmalıdır.', True),
        o('Membranın hiçbir yan etkisi yoktur; bu yüzden her olguda kullanılabilir.', why='Membran grubunda daha fazla ağrı ve komplikasyon bildirilmiştir.')],
      probe=True, targets=['Y5'],
      expl='Membranın genel bir klinik yararı gösterilmemiştir; morbiditeyi artırabilir. Çevrili olmayan defektlerde daha gerekçeli olabilir.', src='s. 5–6 · 3.4; s. 17 · 6'),
    q('membran-q2', 'H6.d', 'Membran kararı için makaleyle en uyumlu gerekçe hangisidir?', [
        o('Membran kullanılmalıdır; çünkü her olguda kanamayı belirgin biçimde azaltır.', why='Birçok çalışma membranın ek klinik yararını gösterememiştir.', mis='Y5'),
        o('Membranın ek yararı bu defektte az olabilir; komplikasyon riski de göz önünde tutularak membransız tedavi düşünülebilir.', True),
        o('4 duvarlı defektte greft de gereksizdir.', why='Soru membranla ilgilidir; 4 duvarlı defekt rekonstrüktif tedaviye en elverişli morfolojidir.')],
      kind='application', targets=['Y5'],
      scenario='Kurgusal bir olgu: 4 duvarlı, 4 mm derin çembersel bir defekte ksenojen greftle rekonstrüktif tedavi planlanıyor. Hasta komplikasyonlardan çekiniyor.',
      expl='4 duvarlı defektte membranın ek yararı az olabilir; membran grubunda dehisens ve açığa çıkma daha sık bildirilmiştir.', src='s. 5–6 · 3.4'),
])

section('iyilesme', 'Flep adaptasyonu ve iyileşme modu', ['H6.e'], [
    say('Ameliyat sırasında ve sonrasında kritik bir karar, bölgenin kapalı mı yoksa transmukozal mı iyileşeceğidir. {1}Kapalı, yani submerged iyileşmede implant tamamen örtülür. Transmukozal iyileşmede ise implant ağız ortamına açık kalır. {2}Periodontal cerrahideki ilkeler burada da uygulanabilir: Rekonstrüktif olmayan tedavide flepleri apikale konumlandırmak cep azalmasını en üst düzeye çıkarabilir. Rekonstrüktif tedavide ise primer kapanışın ve mümkünse kapalı iyileşmenin daha öngörülebilir kemik rejenerasyonu sağladığı düşünülür.',
        T('İyileşme modu'),
        CMP([
            {'title': 'Rekonstrüktif olmayan', 'items': ['Flepleri apikale konumlandır', 'İmplant tamamen örtülmez', 'Amaç: cep azalması, drenaj']},
            {'title': 'Rekonstrüktif', 'color': 'ok', 'items': ['Primer kapanış', 'Mümkünse kapalı (submerged) iyileşme', 'Amaç: öngörülebilir rejenerasyon']}], cue=2),
        TERM('Kapalı (submerged) iyileşme', 'Defekt, erken iyileşme döneminde ağız ortamından yalıtılır; implant tamamen örtülür.', cue=1),
        src='s. 6–7 · 3.6'),
    say('Kanıt neler? {1}Bir köpek çalışmasında 3 ay kapalı tutulan defektlerde kemik-implant teması, transmukozal iyileşenlere göre anlamlı olarak daha yüksektir. {2}İki prospektif çalışmanın yeniden analizinde kapalı iyileşme grubunda, yaklaşık 8. ayda klinik defekt dolumu yaklaşık 0,9 milimetre, 12. ayda radyografik dolum yaklaşık 1,7 milimetre, cep azalması yaklaşık 1,3 milimetre daha fazladır; kanama azalması ise benzerdir. {3}Ancak iki grupta kullanılan membranlar da farklıdır: kapalı grupta emilmeyen, açık grupta emilebilen membran.',
        CLEAR, T('Kapalı iyileşmenin kanıtı'),
        B(['Köpek çalışması (preklinik): 3 ay kapalı → kemik-implant teması ↑'], title='Kanıt', cue=1),
        P('Yeniden analiz: defekt dolumu +0,9 mm (≈8. ay) · radyografik dolum +1,7 mm · PD azalması +1,3 mm · BOP benzer', cue=2),
        X('Gruplar membran türünde de farklı: kapalıda emilmeyen PTFE, açıkta emilebilen membran.', 'warn', cue=3),
        src='s. 7–8 · 3.6'),
    say('Kapalı iyileşmenin pratik bedeli de vardır. {1}Tam örtme çoğu zaman protezin çıkarılmasını ve geçici bir restorasyon yapılmasını gerektirir; bu da süreyi, maliyeti ve protetik komplikasyon riskini artırır. {2}Ayrıca implant üzerinde primer kapanış tekniğe duyarlıdır ve erken yara açılmasına eğilimlidir; bir çalışmada primer kapanış denenmesine rağmen 36 bölgenin 25\'inde dehisens görülmüştür. {3}Sonuçta kapalı iyileşme rejeneratif sonuç için avantajlı görünse de karmaşıklık ve komplikasyon riskiyle birlikte tartılmalıdır. En uygun iyileşme protokolü konusunda kesin bir uzlaşı yoktur. Osseointegrasyon Akademisi ile Amerikan Periodontoloji Akademisinin uzlaşı konferansı da bu önerilerin kontrollü çalışmalarla desteklenmesi gerektiğini vurgular.',
        CLEAR, T('Kapalı iyileşmenin bedeli'),
        B(['Protezin çıkarılması, geçici restorasyon', 'Süre, maliyet, protetik komplikasyon ↑'], title='Pratik yük', cue=1),
        X('Erken yara dehisensi: 36 bölgenin 25\'inde', 'warn', cue=2),
        X('Kesin uzlaşı yok; olgu bazında klinik karar gerekir.', 'key', cue=3),
        src='s. 8 · 3.6; s. 17 · 6'),
    q('iyilesme-q1', 'H6.e', 'Kapalı (submerged) iyileşme hakkında makaleyle en uyumlu ifade hangisidir?', [
        o('Rekonstrüktif tedavide rejeneratif sonuç için avantajlı görünür; ancak karmaşıklık ve dehisens riski nedeniyle olgu bazında tartılmalıdır.', True),
        o('En uygun iyileşme modu olduğu uzlaşıyla kabul edilmiştir.', why='Makale en uygun protokol konusunda kesin bir uzlaşı olmadığını söyler.'),
        o('Rekonstrüktif olmayan tedavide de implant tamamen örtülmelidir.', why='Rekonstrüktif olmayan tedavide fleplerin apikale konumlandırılması önerilir.')],
      probe=True, hints=['Karşılaştırılan iki grupta başka ne farklıydı?'],
      expl='Kapalı iyileşme bazı çalışmalarda daha iyi rejeneratif sonuçla ilişkilidir; ancak teknik olarak zordur, dehisens sıktır ve kesin uzlaşı yoktur.', src='s. 6–8 · 3.6; s. 17 · 6'),
])

section('antibiyotik', 'Sistemik antibiyotik', ['H6.f'], [
    say('Peri-implantitisin bakteriyel etiyolojisi düşünülerek sistemik antibiyotikler cerrahiye ek olarak araştırılmıştır. {1}Rekonstrüktif olmayan tedavide, bir randomize çalışmada azitromisin klinik sonucu anlamlı olarak iyileştirmemiştir. Başarı yüzde 46,7\'ye karşı yüzde 25 olsa da fark anlamlı değildir. {2}Başka bir çalışmada amoksisilin, yüzeyi modifiye implantlarda 12. ayda başarıyı artırmış, ancak bu yarar 3. yılda sürmemiştir. Modifiye olmayan yüzeylerde ise hiçbir izlem döneminde yarar görülmemiştir. {3}Üç kollu bir randomize çalışmada 12. ayda klinik parametreler plaseboyla benzer kalmış, ancak radyografik kemik stabilitesi ve hastalığın gerilemesi antibiyotik gruplarında daha sık görülmüştür.',
        T('Sistemik antibiyotik'),
        TABLE(['Çalışma', 'Bulgu'], [
            ['Azitromisin + açık flep (RKÇ, 12 ay)', 'Başarı %46,7 / %25 · fark anlamlı değil (p = 0,20)'],
            ['Amoksisilin, rezektif (12 ay → 3 yıl)', 'Modifiye yüzeyde 12. ayda yarar · 3. yılda sürmedi · modifiye olmayan yüzeyde yarar yok'],
            ['Amoksisilin/penisilin + metronidazol (3 kollu RKÇ)', 'Klinik benzer · radyografik stabilite ve gerileme: %68 ve %66 / %28 plasebo']], cue=1),
        src='s. 8–9 · 3.7.1'),
    say('Rekonstrüktif tedavide tek bir retrospektif analiz vardır ve gruplar arasında anlamlı fark bulunmamıştır. {1}Farklı yöntemleri birlikte analiz eden bir meta-analiz kısa dönemde daha yüksek başarı bildirmiştir; ancak bu analiz heterojen cerrahi yaklaşımları ve farklı antibiyotik rejimlerini birleştirdiği için sonuçlar karışık olabilir. {2}Süperenfeksiyon, mikrobiyom disbiyozu ve antibiyotik direnci riskleri nedeniyle güncel klinik uygulama kılavuzları, peri-implant hastalıklarının tedavisinde sistemik antibiyotiklerin rutin kullanımını önermez.',
        CLEAR, T('Sonuç'),
        X('Meta-analiz: kısa dönemde başarı ↑ (OR 2,73) · ama heterojen yöntem ve rejimler birleştirilmiş', 'warn', cue=1),
        X('Kılavuz: rutin sistemik antibiyotik **önerilmez** (süperenfeksiyon, disbiyoz, direnç).', 'key', cue=2),
        src='s. 9 · 3.7.2, 3.7.3'),
    q('ab-q1', 'H6.f', 'Güncel klinik uygulama kılavuzlarının sistemik antibiyotik konusundaki tutumu nedir?', [
        o('Cerrahi peri-implantitis tedavisinde rutin olarak verilmesi önerilir.', why='Kılavuzlar rutin kullanımı önermez.', mis='Y6'),
        o('Peri-implant hastalıklarının tedavisinde rutin kullanımı önerilmez.', True),
        o('Yalnızca rekonstrüktif tedavide zorunludur.', why='Rekonstrüktif tedavide tek bir retrospektif analiz vardır ve anlamlı fark bulunmamıştır.')],
      probe=True, targets=['Y6'],
      expl='Bazı kısa dönemli yararlar gözlense de sonuçlar tutarsızdır; direnç ve disbiyoz riskleri nedeniyle rutin kullanım önerilmez.', src='s. 9 · 3.7.3; s. 17 · 6'),
    q('ab-q2', 'H6.f', 'Hangi değerlendirme makaleyle en uyumludur?', [
        o('Meta-analiz OR 2,73 gösterdiği için her hastaya antibiyotik verilmelidir.', why='Meta-analiz heterojen yöntem ve rejimleri birleştirmiştir; kılavuzlar rutin kullanımı önermez.', mis='Y6'),
        o('Kısa dönemli yarar bildirilmiştir, ama sonuçlar tutarsızdır; direnç ve disbiyoz riski nedeniyle rutin kullanım önerilmez.', True),
        o('Antibiyotiklerin hiçbir çalışmada hiçbir etkisi görülmemiştir.', why='Bazı çalışmalarda kısa dönemli yarar ve radyografik stabilite bildirilmiştir.')],
      kind='application', targets=['Y6'],
      scenario='Kurgusal bir durum: Klinikte bir meslektaşınız "Meta-analiz başarıyı artırdığını gösterdi; bundan sonra her peri-implantitis cerrahisinde antibiyotik yazalım" diyor.',
      expl='Antibiyotiklerin bazı kısa dönemli yararları görülse de sonuçlar tutarsızdır ve kılavuzlar rutin kullanımı önermez.', src='s. 9 · 3.7; s. 17 · 6'),
])

section('operator', 'Operatörle ilişkili faktörler', ['H6.g'], [
    say('Dahil edilen çalışmaların 20\'si cerrahların deneyim düzeyini belirtmiştir. {1}Tek bir üniversite merkezinde dört deneyimli cerrahın sonuçları karşılaştırıldığında, işlemler büyük ölçüde standart olduğu hâlde 12. ayda başarı oranları cerrahlar arasında anlamlı olarak değişmiştir. Daha az deneyimli cerrahların yaptığı işlemler daha düşük başarı oranıyla ilişkili bulunmuştur. {2}Rezektif tedavide de bir öğrenme eğrisi görülmüştür: gözlem döneminin başında tedavi edilen hastalarda başarısızlık daha sıktır. {3}Aynı seansta iki implantın cerrahi tedavisi ise başarısızlık olasılığını belirgin biçimde artırmıştır.',
        T('Operatör faktörleri'),
        B(['Dört deneyimli cerrah, standart işlem → başarı yine de farklı (OR 0,12, az deneyimli)'], title='Bulgular', cue=1),
        P('Öğrenme eğrisi: dönemin başında tedavi edilenlerde başarısızlık ↑', cue=2),
        P('Aynı seansta iki implant: başarısızlık odds\'u ↑ (OR 31,68)', cue=3),
        src='s. 9–10 · 3.8'),
    say('Yazarlar şu sonuca varır: {1}Deneyim, ameliyat içi karar verme ve olgunun karmaşıklığı, örneğin tedavi edilen implant sayısı, peri-implantitis cerrahisinin başarısını etkiliyor görünmektedir. Bu da eğitimin, işlem tutarlılığının ve bireyselleştirilmiş olgu planlamasının önemini gösterir.',
        X('Deneyim · ameliyat içi karar · olgu karmaşıklığı → eğitim, işlem tutarlılığı, bireysel planlama', 'key', cue=1),
        src='s. 10 · 3.8.2'),
    q('op-q1', 'H6.g', 'Operatörle ilişkili faktörler için hangisi makaleyle uyumludur?', [
        o('İşlemler standart olduğu için cerrahlar arasında başarı farkı görülmemiştir.', why='Standart işleme rağmen cerrahlar arasında anlamlı fark bulunmuştur.'),
        o('Daha az deneyim ve aynı seansta birden çok implant tedavisi daha kötü sonuçla ilişkilidir.', True),
        o('Öğrenme eğrisi yalnızca rekonstrüktif tedavide görülmüştür.', why='Öğrenme eğrisi rezektif tedavi çalışmasında bildirilmiştir.')],
      probe=True, expl='Deneyim, ameliyat içi karar verme ve olgu karmaşıklığı sonucu etkiliyor görünmektedir.', src='s. 9–10 · 3.8'),
])

# =====================================================================
# G3 — Lokal/hasta faktörleri ve takip (H4, H5)
# =====================================================================
section('siddet', 'Başlangıç hastalık şiddeti', ['H4.a'], [
    say('Başlangıçtaki kemik kaybının şiddeti güçlü bir prognostik faktördür. {1}Rekonstrüktif olmayan tedaviden 6 ay sonra, başlangıç kemik kaybı 2 ile 4 milimetre olan implantların yüzde 74\'ü sağlıklı bulunmuş; bu oran 5 ile 6 milimetre kayıpta yüzde 50\'ye inmiştir. 7 milimetre ve üzeri kayıpta ise 18 implantın 7\'si üçüncü aya kadar çıkarılmıştır. {2}Başka bir çalışmada 12. ayda başarı, kemik kaybı 1 ile 3 milimetre olan implantlarda yüzde 70, 7 ile 9 milimetre olanlarda yüzde 25\'tir. {3}Farklı yöntemleri birlikte analiz eden bir çalışmada yüzde 50\'den fazla kemik kaybı olan implantlarda başarısızlık odds\'u, yüzde 25\'ten az kayıp olanlara göre 23,6 kat yüksektir.',
        T('Başlangıç kemik kaybı'),
        TABLE(['Başlangıç kemik kaybı', 'Sonuç'], [
            ['2–4 mm', '6. ayda %74 sağlıklı'],
            ['5–6 mm', '6. ayda %50 sağlıklı'],
            ['≥7 mm', '18 implantın 7\'si 3. aya kadar çıkarıldı'],
            ['1–3 mm / 7–9 mm', '12. ayda başarı %70 / %25'],
            ['>%50 / <%25', 'Başarısızlık odds\'u 23,6 kat']], cue=1),
        src='s. 10–11 · 4.1'),
    say('Sondlama derinliği ve süpürasyon da belirleyicidir. {1}Çok merkezli bir randomize çalışmanın alt analizinde başlangıç sondlama derinliği, tedavi türünden bağımsız olarak sonucun en güçlü yordayıcısıdır. {2}Ameliyat öncesi süpürasyon, 6. ayda kalıcı süpürasyonla ve 7 yılda implant kaybıyla ilişkili bulunmuştur. Başlangıçtaki maksimum sondlama derinliğinde her 1 milimetrelik artış, 12 ayda cerrahi yeniden tedavi gereksinimini yüzde 30 artırmıştır. {3}Özetle, yaygın kemik kaybı, derin cepler ve süpürasyon cerrahi sonucun tutarlı olumsuz yordayıcılarıdır.',
        CLEAR, T('Cep derinliği ve süpürasyon'),
        B(['Başlangıç PD: tedavi türünden bağımsız en güçlü yordayıcı'], cue=1),
        P('Başlangıç Sup → kalıcı Sup (6 ay), implant kaybı (7 yıl)', cue=2),
        P('Maksimum PD\'de her +1 mm → yeniden tedavi gereksinimi %30 ↑ (12 ay)', cue=2),
        X('Yaygın kemik kaybı + derin cep + süpürasyon = tutarlı olumsuz yordayıcılar', 'key', cue=3),
        src='s. 11–12 · 4.1.3'),
    q('siddet-q1', 'H4.a', 'Makaleye göre hangi başlangıç bulguları cerrahi sonucun tutarlı olumsuz yordayıcılarıdır?', [
        o('Yaygın kemik kaybı, derin cepler ve süpürasyon', True),
        o('Keratinize mukozanın varlığı', why='Keratinize mukoza, özellikle rekonstrüktif tedavide sonucu olumlu etkiliyor görünmektedir.'),
        o('Hastanın cinsiyeti', why='Cinsiyetle ilgili bulgular tutarsızdır.')],
      probe=True, expl='Daha şiddetli başlangıç hastalığı, yani yaygın kemik kaybı, derin cepler ve süpürasyon, tutarlı olarak daha kötü sonuçla ilişkilidir.', src='s. 12 · 4.1; s. 17 · 6'),
    q('siddet-q2', 'H4.a', 'Bu iki implant için makaleyle en uyumlu prognoz değerlendirmesi hangisidir?', [
        o('X implantının prognozu daha iyidir; Y\'de yaygın kemik kaybı, derin cep ve süpürasyon olumsuz yordayıcılardır.', True),
        o('İkisinin prognozu aynıdır; sonucu yalnızca seçilen teknik belirler.', why='Başlangıç sondlama derinliği tedavi türünden bağımsız olarak en güçlü yordayıcı bulunmuştur.'),
        o('Y implantının prognozu daha iyidir; çünkü derin cepte daha çok greft yerleştirilir.', why='Derin cep ve yaygın kemik kaybı olumsuz yordayıcılardır.')],
      kind='application',
      scenario='Kurgusal iki implant: X implantında 3 mm kemik kaybı, en derin cep 6 mm, süpürasyon yok. Y implantında 8 mm kemik kaybı, en derin cep 10 mm, süpürasyon var.',
      expl='Kemik kaybının, cep derinliğinin ve süpürasyonun şiddeti cerrahi sonucun en tutarlı olumsuz yordayıcılarıdır.', src='s. 10–12 · 4.1'),
])

section('km', 'Keratinize mukoza', ['H4.b'], [
    say('Keratinize mukozanın genişliği 2 milimetrenin altında olan implant bölgeleri, daha yüksek peri-implantitis prevalansı, daha fazla plak birikimi, enflamasyon, çekilme ve kemik kaybıyla ilişkilidir. {1}Rekonstrüktif tedavide bir randomize çalışmada ameliyat öncesi keratinize mukoza genişliği hastalığın gerileme odds\'unu anlamlı olarak artırmıştır: Her ek milimetrede gerileme olasılığı yüzde 110 artmıştır. {2}Başka bir çalışmada 6. ayda 2 milimetre veya üzeri keratinize mukoza, 10 yıllık başarıyla doğrudan ilişkili bulunmuştur.',
        T('Keratinize mukoza'),
        X('KM < 2 mm: peri-implantitis prevalansı, plak, enflamasyon, çekilme, kemik kaybı ↑', 'note'),
        B(['RKÇ: başlangıç KM genişliği → gerileme odds\'u ↑ (her +1 mm: %110)', '6. ayda KM ≥2 mm → 10 yıllık başarı ile ilişkili'], title='Rekonstrüktif tedavi', cue=1),
        src='s. 11 · 4.2, 4.2.1'),
    say('Farklı yöntemleri birlikte analiz eden çalışmalarda sonuçlar daha az tutarlıdır. {1}Bir çalışmada tedaviden sonra keratinize mukozası yeterli ve yetersiz olan implantlar arasında fark bulunmamıştır. {2}Bir diğerinde ise yetersiz keratinize mukoza, rekonstrüktif tedavide başarısızlık riskini artırmış, rezektif tedavide artırmamıştır. {3}Bir bütün olarak ele alındığında veriler, keratinize mukozanın peri-implant sağlığa katkıda bulunduğunu ve özellikle rekonstrüktif önlemler içeren olgularda cerrahi sonucu olumlu etkilediğini düşündürmektedir.',
        CLEAR, T('Her yöntemde aynı mı?'),
        CMP([
            {'title': 'Rekonstrüktif', 'color': 'ok', 'items': ['KM <2 mm → başarısızlık riski ↑ (OR 13,9)']},
            {'title': 'Rezektif', 'items': ['Aynı çalışmada ilişki yok']}], cue=2),
        X('Sonuç: KM, özellikle rekonstrüktif tedavide sonucu olumlu etkiliyor **görünmektedir**.', 'key', cue=3),
        src='s. 11 · 4.2.2'),
    q('km-q1', 'H4.b', 'Keratinize mukozanın cerrahi sonuca etkisi en belirgin olarak hangi tedavi türünde bildirilmiştir?', [
        o('Rekonstrüktif tedavide', True),
        o('Yalnızca rezektif tedavide', why='Bir çalışmada yetersiz KM rezektif tedavide değil, rekonstrüktif tedavide başarısızlık riskini artırmıştır.'),
        o('Hiçbir tedavi türünde ilişki bulunmamıştır.', why='Rekonstrüktif tedavide KM ile daha iyi sonuç arasında ilişki bildirilmiştir.')],
      probe=True, expl='Veriler keratinize mukozanın özellikle rekonstrüktif önlemler içeren olgularda sonucu olumlu etkilediğini düşündürür.', src='s. 11 · 4.2; s. 17 · 6'),
])

section('konum', 'İmplant konumu', ['H4.c'], [
    say('İmplant konumunun etkisine ilişkin kanıtlar tutarsızdır. {1}Bir çalışmada posterior implantlarda başarısızlık riski anterior implantlara göre yüzde 78 daha düşük bulunmuştur. Başka bir çalışmada maksiller implantlar daha yüksek nüks riskiyle, bir diğerinde molar bölgedeki implantlar daha yüksek kayıp oranıyla ilişkilidir. {2}Buna karşılık rekonstrüktif bir randomize çalışmada maksiller konum başarıyla olumlu yönde ilişkili bulunmuştur. {3}Pek çok çalışma ise konumun hiçbir anlamlı etkisini saptamamıştır. Yazarlara göre konum yeterince incelenmemiştir; maksiller ya da anterior implantlarda bazı popülasyonlarda yeniden tedavi riskinin daha yüksek olabileceğine dair sınırlı kanıt vardır.',
        T('İmplant konumu'),
        CMP([
            {'title': 'Bir yönde', 'items': ['Posterior: başarısızlık riski %78 ↓ (anteriora göre)', 'Maksilla: nüks riski ↑', 'Molar bölge: kayıp ↑']},
            {'title': 'Ters yönde', 'color': 'accent', 'items': ['RKÇ (ozon ile): maksilla → başarıyla olumlu ilişkili']},
            {'title': 'İlişki yok', 'color': 'warn', 'items': ['Pek çok çalışma (çene, anterior–posterior)']}], cue=1),
        X('Konum yeterince incelenmemiş; sınırlı ve tutarsız kanıt.', 'key', cue=3),
        src='s. 11–12 · 4.3; s. 17 · 6'),
    q('konum-q1', 'H4.c', 'İmplant konumunun cerrahi sonuca etkisi için en doğru ifade hangisidir?', [
        o('Maksiller implantların her zaman daha kötü sonuç verdiği gösterilmiştir.', why='Bir randomize çalışma tersine maksiller konumu başarıyla ilişkili bulmuştur; pek çok çalışma ilişki saptamamıştır.', mis='Y1'),
        o('Kanıt sınırlı ve tutarsızdır; bazı popülasyonlarda maksiller ya da anterior implantlarda risk daha yüksek olabilir.', True),
        o('Konumun sonuçla ilişkili olmadığı kesin olarak gösterilmiştir.', why='Bazı çalışmalar ilişki bulmuştur; makale konuyu yeterince incelenmemiş sayar.')],
      probe=True, expl='Konumun etkisi yeterince incelenmemiştir ve bulgular tutarsızdır.', src='s. 12 · 4.3; s. 17 · 6'),
])

section('yuzey', 'İmplant yüzeyi', ['H4.d'], [
    say('İmplant yüzeyi özellikle rekonstrüktif olmayan tedavide sonucu etkiler. {1}3 yıllık bir çalışmada modifiye olmayan, yani düz işlenmiş yüzeyli implantlarda cep azalması daha fazla, 5 milimetreyi aşan kalan cep daha az görülmüştür. {2}5 yılda modifiye yüzeyli implantlarda nüks riski anlamlı olarak daha yüksektir. 7 yıllık bir analizde de modifiye yüzey implant kaybının anlamlı bir yordayıcısıdır. {3}Rekonstrüktif tedavide ise 7 yıllık bir çalışmada başarı, pürüzlü titanyum plazma spreyli yüzeylerde yüzde 14,3, orta pürüzlü kumlanmış ve asitlenmiş yüzeylerde yüzde 58,3\'tür.',
        T('İmplant yüzeyi'),
        TABLE(['Tedavi', 'Bulgu'], [
            ['Rekonstrüktif olmayan, 3 yıl', 'Düz yüzey: daha fazla PD azalması, daha az kalan PD >5 mm'],
            ['Rekonstrüktif olmayan, 5 yıl', 'Modifiye yüzey: nüks riski ↑ (OR 5,07)'],
            ['Rekonstrüktif olmayan, 7 yıl', 'Modifiye yüzey: implant kaybının yordayıcısı (HR 4,5)'],
            ['Rekonstrüktif, 7 yıl', 'Başarı: TPS %14,3 (2/14) · SLA %58,3 (7/12)']], cue=1),
        src='s. 12–13 · 4.4'),
    say('Yazarlar bunu nasıl açıklıyor? {1}Pürüzlü yüzeylerin cerrahi sırasında tam olarak dekontamine edilmesi zordur; ayrıca cerrahiden sonra bakterilerle yeniden kolonize olmaya daha yatkındır. Bu, zamanla nüks riskini artırabilir. Bu açıklama, çalışma yazarlarının bir yorumudur.',
        X('Olası açıklama (yazarların yorumu): pürüzlü yüzeyde tam dekontaminasyon zor + yeniden kolonizasyona yatkınlık', 'key', cue=1),
        src='s. 12 · 4.4.1', basis='source'),
    q('yuzey-q1', 'H4.d', 'Pürüzlü yüzeyli implantlarda cerrahi sonrası nüksün daha sık olmasının makalede önerilen açıklaması hangisidir?', [
        o('Pürüzlü yüzeyler daha kolay dekontamine edilir.', why='Tersine: tam dekontaminasyon pürüzlü yüzeyde zordur.'),
        o('Pürüzlü yüzeyde tam dekontaminasyon zordur; bu yüzey yeniden kolonizasyona da daha yatkındır.', True),
        o('Pürüzlü yüzeyler daha fazla keratinize mukoza oluşturur.', why='Makalede böyle bir ilişki yoktur.')],
      probe=True, expl='Yazarların yorumu: pürüzlü yüzeylerde tam dekontaminasyon güçtür ve bakteriyel yeniden kolonizasyona yatkınlık nüks riskini artırabilir.', src='s. 12 · 4.4.1; s. 17 · 6'),
])

section('postop', 'Cerrahi sonrası klinik göstergeler', ['H4.e'], [
    say('Cerrahiden sonraki klinik bulgular, uzun dönem stabiliteyi öngörmede kullanılabilir. {1}5 yıllık bir prospektif çalışmada 1. yılda 6 milimetre veya daha derin kalan cebi olan implantlarda nüks odds\'u anlamlı olarak yüksektir; nüks bu implantların yüzde 80\'inde, kalan cebi olmayanların ise yüzde 29\'unda görülmüştür. {2}Çevresel kalan cebi olan implantlarda hastalık ilerlemesi ilk 5 yılda yüzde 23\'ken 5. ile 10. yıllar arasında yüzde 53\'e çıkmıştır. {3}Başka bir analizde ek kemik kaybı olmama olasılığı, kanama yoksa yüzde 77, cep 5 milimetre veya altındaysa yüzde 83\'tür.',
        T('Ameliyat sonrası göstergeler'),
        TABLE(['Gösterge', 'Sonuç'], [
            ['1. yılda kalan PD ≥6 mm', 'Nüks: %80 / %29 (kalan cep yok) · OR 7,4'],
            ['Çevresel kalan PD', 'İlerleme: ilk 5 yıl %23 → 5–10. yıl %53'],
            ['BOP yok', 'Ek kemik kaybı olmaması: %77'],
            ['PD ≤5 mm', 'Ek kemik kaybı olmaması: %83']], cue=1),
        src='s. 12–13 · 4.5'),
    say('Özetle, kalan peri-implant cepleri, sondlamada kanamanın sürmesi ve cerrahi sonrası elverişsiz kemik seviyeleri, nüksü güçlü biçimde yordar. {1}Bu yüzden erken kontrol randevularında hastalığın tam olarak gerilemesini sağlamak önemlidir.',
        X('Kalan cep + süren BOP + elverişsiz kemik seviyesi → nüks', 'warn'),
        X('Erken kontrollerde tam gerilemeyi hedefle.', 'key', cue=1),
        src='s. 13 · 4.5'),
    q('postop-q1', 'H4.e', 'Cerrahi tedaviden 1 yıl sonra hangi bulgu, makaleye göre nüks riskinin daha yüksek olduğunu düşündürür?', [
        o('6 mm veya daha derin kalan cep', True),
        o('Sondlamada kanama olmaması', why='Kanama olmaması, ek kemik kaybı olmama olasılığıyla ilişkilidir (%77).'),
        o('5 mm veya daha az sondlama derinliği', why='PD ≤5 mm, ek kemik kaybı olmama olasılığıyla ilişkilidir (%83).')],
      probe=True, expl='Kalan derin cepler, süren kanama ve elverişsiz kemik seviyeleri nüksü güçlü biçimde yordar.', src='s. 12–13 · 4.5'),
])

section('protez', 'Protez tipi', ['H4.f'], [
    say('Protez tasarımı da peri-implant sağlığı ve cerrahi sonucu etkileyebilir. {1}Daha önceki çalışmalar, hareketli protezleri taşıyan implantlarda peri-implant hastalığı riskinin sabit restorasyon taşıyan implantlara göre daha yüksek olduğunu göstermiştir. {2}Cerrahi tedaviden sonra, bir çalışmada overdentür taşıyan implantlarda yeniden cerrahi tedavi gereksinimi, tek kuron taşıyanlara göre yaklaşık 3,6 kat yüksek bulunmuştur. Bir diğerinde sabit tam ark protezler tek değişkenli analizde daha yüksek nüksle ilişkilidir; ancak bu ilişki çok değişkenli modelde sürmemiştir.',
        T('Protez tipi'),
        B(['Overdentür ↔ tek kuron: yeniden cerrahi tedavi odds\'u 3,6 kat', 'Sabit tam ark: tek değişkenli analizde nüks ↑ (OR 9,45) · çok değişkenli modelde anlamlı değil'], title='Cerrahi sonrası', cue=2),
        X('Hareketli protez taşıyan implantlarda peri-implant hastalığı riski daha yüksek (önceki çalışmalar).', 'note', cue=1),
        src='s. 13 · 4.6'),
    say('Yazarlar bunu iki olası nedenle açıklar. {1}Hareketli ve tam ark restorasyonlarda etkili plak kontrolünü sağlamak ve sürdürmek daha zordur. {2}Ayrıca tam ark restorasyona yol açan dişsizlik çoğu zaman periodontitis öyküsünün sonucudur; periodontitis öyküsü de cerrahi sonrası nükse katkıda bulunabilir.',
        B(['Plak kontrolü güçlüğü', 'Arka planda periodontitis öyküsü'], title='Olası açıklamalar', cue=1),
        src='s. 13–14 · 4.6.1'),
    q('protez-q1', 'H4.f', 'Sabit tam ark protezlerle nüks arasındaki ilişki için hangisi doğrudur?', [
        o('Tek değişkenli analizde anlamlıdır, ancak çok değişkenli modelde sürmemiştir.', True),
        o('Tüm analizlerde güçlü ve bağımsız bir risk faktörüdür.', why='İlişki çok değişkenli modelde anlamlılığını kaybetmiştir.', mis='Y1'),
        o('Sabit tam ark protezler nüksü azaltır.', why='Tek değişkenli analizde nüks daha yüksektir.')],
      probe=True, targets=['Y1'], hints=['Tek değişkenli ve çok değişkenli analiz ne anlama gelir?'],
      expl='Tek değişkenli analizde görülen ilişki, diğer faktörler hesaba katılınca kaybolmuştur. Bu, ilişkinin başka faktörlerle karışmış olabileceğini düşündürür.', src='s. 13 · 4.6.1'),
])

section('makrofaj', 'Makrofaj polarizasyonu', ['H4.g'], [
    say('Lokal faktörlerin son başlığı, dokudaki bağışıklık cevabıdır. {1}Peri-implant hastalığında monositler doku ortamına göre iki ana fenotipe farklılaşır: Proenflamatuar M1 makrofajlar, interlökin 1 beta, interlökin 6, interlökin 12 ve tümör nekroz faktörü alfa gibi sitokinlerin başlıca kaynağıdır ve süren enflamasyona katkıda bulunur. {2}Antienflamatuar M2 makrofajlar ise arginaz 1, interlökin 4 ve interlökin 10 gibi medyatörlerle enflamasyonun gerilemesini ve doku onarımını destekler. {3}Peri-implantitis lezyonlarında belirgin bir M1 kayması görülür.',
        T('Makrofaj polarizasyonu'),
        CMP([
            {'title': 'M1 (proenflamatuar)', 'color': 'warn', 'items': ['IL-1β, IL-6, IL-12, TNF-α', 'Süren enflamasyon, doku yıkımı', 'Belirteç: CD80, iNOS']},
            {'title': 'M2 (antienflamatuar)', 'color': 'ok', 'items': ['ARG-1, IL-4, IL-10, IL-35, TGF-β1', 'Gerileme, onarım', 'Belirteç: CD206']}], cue=1),
        X('Peri-implantitis lezyonu: M1 yönünde kayma', 'key', cue=3),
        src='s. 13–14 · 4.7'),
    say('Şekil 6, bu analizlerin nasıl yapıldığını gösterir. {1}Solda tanı: sondlamada kanama, enflamasyonun bir bulgusudur. {2}Ortada cerrahi tedavi sırasında granülasyon dokusunun çıkarılması. {3}Sağda bu dokuda immünohistokimyasal boyama: CD80 ile M1, CD206 ile M2 makrofajlar belirlenir.',
        CLEAR, T('Analiz iş akışı'),
        IMG('sekil6'),
        HL(F6['tani'], 'Tanı: BOP', cue=1, id='a'),
        HL(F6['cerrahi'], 'Cerrahi + granülasyon dokusu', cue=2, id='b'),
        HL(F6['ihk'], 'CD80 (M1) · CD206 (M2)', cue=3, color='ok', id='c'),
        src='s. 14 · Şekil 6'),
    say('Bu bulgular klinik olarak ne anlama geliyor? {1}14 hastalık retrospektif bir çalışmada başlangıçtaki yüksek M1 ifadesi, 6. ayda daha fazla cep azalması ve daha fazla yumuşak doku çekilmesiyle ilişkili bulunmuştur. {2}Yazarların yayımlanmamış verilerinde tedaviye cevap vermeyen hastalarda iNOS daha yüksek kalmış, cevap verenlerde arginaz-1 artmıştır. {3}Bunlar yeni ortaya çıkan, küçük örneklemli ve kısmen yayımlanmamış verilerdir. Makale yalnızca bir ilişkiden söz eder ve bu cevabın düzenlenmesinin ileride bir tedavi hedefi olabileceğini belirtir.',
        CLEAR, T('Klinik bağlantı'),
        B(['14 hasta, retrospektif: yüksek başlangıç M1 → 6. ayda daha fazla PD azalması ve çekilme'], title='Bulgular', cue=1),
        P('Yayımlanmamış veri: cevap vermeyenlerde iNOS ↑, cevap verenlerde ARG-1 ↑', cue=2),
        X('Yeni ortaya çıkan kanıt: ilişki var, nedensellik ve tedavi kullanımı henüz yok. Modülasyon **ileride** hedef olabilir.', 'warn', cue=3),
        src='s. 14 · 4.7; s. 17 · 6'),
    q('makrofaj-q1', 'H4.g', 'Makrofaj polarizasyonu hakkında makalenin vardığı sonuç hangisidir?', [
        o('M1/M2 dengesinin cerrahi başarıyı belirlediği kanıtlanmıştır ve bugün tedavi hedefi olarak kullanılır.', why='Makale yalnızca yeni ortaya çıkan bir ilişkiden söz eder; modülasyon ileride bir hedef olabilir.', mis='Y8'),
        o('Yeni ortaya çıkan kanıtlar polarizasyon ile cerrahi sonuç arasında bir ilişkiye işaret eder; bu cevabın düzenlenmesi ileride bir tedavi hedefi olabilir.', True),
        o('Peri-implantitis lezyonlarında M2 makrofajlar baskındır.', why='Peri-implantitis lezyonlarında M1 yönünde belirgin bir kayma vardır.')],
      probe=True, targets=['Y8'],
      expl='Kanıt yeni ortaya çıkmaktadır ve kısmen yayımlanmamış verilere dayanır; örneklemler küçüktür. Makale bir ilişkiden ve gelecekteki olası bir hedeften söz eder.', src='s. 14 · 4.7; s. 17 · 6'),
])

section('hasta', 'Periodontitis öyküsü, sigara ve cinsiyet', ['H5.a'], [
    say('Periodontitis öyküsü, peri-implantitis gelişimi için iyi bilinen bir risk faktörüdür. {1}Ancak cerrahi tedavi sonucuna etkisi daha az kesindir. Bazı çalışmalar ilişki bulmamıştır; bu çalışmalardan birinde periodontitis öyküsü hastaların kendi beyanına dayanmaktadır. {2}3 yıllık bir randomize çalışmada periodontitis öyküsü başarı odds\'unu azaltmış, ama aynı hasta grubunun 7 yıllık izleminde bu ilişki doğrulanmamıştır. {3}Farklı yöntemleri birlikte analiz eden iki retrospektif çalışma ise daha güçlü olumsuz bir etki bildirmiştir; örneğin Derece C periodontitisli hastalarda nüks riski dört kat yüksektir. Yazarlara göre çalışma tasarımlarındaki heterojenlik, periodontitisin tutarsız tanımlanması ve farklı başarı ölçütleri bu değişkenliği büyük olasılıkla açıklar.',
        T('Hastaya bağlı faktörler'),
        CMP([
            {'title': 'İlişki yok', 'items': ['5 yıllık prospektif (rekonstrüktif olmayan)', 'İki RKÇ alt analizi (öykü hasta beyanı)', 'RKÇ, 7 yıl']},
            {'title': 'Olumsuz ilişki', 'color': 'warn', 'items': ['RKÇ, 3 yıl', 'Retrospektif: Derece C → nüks 4 kat', 'Retrospektif: başarısızlık OR 4,62']}], title='Periodontitis öyküsü', cue=1),
        X('Değişkenliğin olası nedeni: heterojen tasarım, tutarsız periodontitis tanımı, farklı başarı ölçütleri', 'key', cue=3),
        src='s. 14–15 · 5.1'),
    say('Sigara için de tablo benzerdir. {1}Sigaranın peri-implantitis riskiyle ilişkisi bir meta-analizde güçlü bulunmuştur, ama cerrahi sonuç üzerindeki etkisi çelişkilidir. Bazı çalışmalarda sigara ilerleme ve başarısızlık riskini artırmış, bazılarında 1 ile 5 yıllık izlemde fark bulunmamıştır. Bu nedenle kesin bir sonuca varılamaz. {2}Cinsiyetle ilgili bulgular da tutarsızdır: Bir randomize çalışmada kadın hastalarda gerileme olasılığı daha yüksek bulunmuş, iki retrospektif çalışma ise ters yönde sonuç bildirmiştir; bu ilişkiler çok değişkenli modelde sürmemiştir.',
        CLEAR, T('Sigara ve cinsiyet'),
        CMP([
            {'title': 'Sigara', 'items': ['Peri-implantitis riski ↑ (meta-analiz, RR ~2)', 'Cerrahi sonuç: çelişkili bulgular', 'Kesin sonuç yok']},
            {'title': 'Cinsiyet', 'items': ['RKÇ: kadınlarda gerileme ↑', 'İki retrospektif: ters yönde', 'Çok değişkenli modelde sürmedi']}], cue=1),
        X('Periodontitis öyküsü, sigara ve cinsiyet: bulgular kesin değildir.', 'key', cue=2),
        src='s. 15–16 · 5.2, 5.3; s. 17 · 6'),
    q('hasta-q1', 'H5.a', 'Periodontitis öyküsü, sigara ve cinsiyetin cerrahi tedavi sonucuna etkisi için makalenin vardığı sonuç hangisidir?', [
        o('Üçü de cerrahi sonucu tutarlı biçimde kötüleştirir.', why='Makaleye göre bu üç faktörle ilgili bulgular kesin değildir.', mis='Y7'),
        o('Bulgular kesin değildir; çalışmalar farklı yönlerde sonuçlar bildirmiştir.', True),
        o('Yalnız cinsiyetin etkisi kesin olarak gösterilmiştir.', why='Cinsiyetle ilgili bulgular da tutarsızdır.')],
      probe=True, targets=['Y7'],
      expl='Periodontitis öyküsü peri-implantitis gelişimi için iyi bilinen bir risk faktörüdür; ancak cerrahi sonuç üzerindeki etkisi, sigara ve cinsiyetin etkisi gibi, kesin değildir.', src='s. 14–17 · 5.1–5.3, 6'),
    q('hasta-q2', 'H5.a', 'Makaleyle en uyumlu bilgilendirme hangisidir?', [
        o('Sigara ve periodontitis öyküsü nedeniyle tedavinin başarısız olacağı kesindir.', why='Bu iki faktörün cerrahi sonuca etkisi tutarsızdır; kesinlik iddiası makaleyle uyuşmaz.', mis='Y7'),
        o('Bu faktörlerin cerrahi sonuca etkisi çalışmalarda tutarsızdır; buna karşılık ameliyat sonrası idameye uyum sonucu korumada kritik görünmektedir.', True),
        o('Bu faktörlerin peri-implant sağlıkla hiçbir ilgisi yoktur.', why='Periodontitis öyküsü peri-implantitis gelişimi için iyi bilinen bir risk faktörüdür.')],
      kind='application', targets=['Y7'],
      scenario='Kurgusal bir olgu: Günde 15 sigara içen ve periodontitis öyküsü olan bir hastaya cerrahi peri-implantitis tedavisi planlanıyor. Hasta "Bu koşullarda tedavi kesin başarısız olur mu?" diye soruyor.',
      expl='Periodontitis öyküsü ve sigaranın cerrahi sonuca etkisi tutarsızdır. Makale idameye uyumu sonucu korumada en kritik hasta faktörlerinden biri olarak öne çıkarır.', src='s. 14–17 · 5.1–5.4'),
])

section('idame', 'Destekleyici bakım ve uyum', ['H5.b'], [
    say('Uzun dönem başarının en kritik belirleyicilerinden biri, hastanın ameliyat sonrası destekleyici bakıma, yani idame tedavisine uyumudur. {1}5 yıllık bir çalışmada peri-implantitis insidansı idameye uyan hastalarda yüzde 18, uymayanlarda yüzde 44\'tür. {2}Rekonstrüktif olmayan cerrahiden sonra ortalama 6,5 yıllık izlemde tüm kontrol randevularına gelen hastalarda başarısızlık oranı anlamlı olarak daha düşüktür. Randevuların yarısından azına gelenlerin sonuçları, düzensiz gelenlerinkiyle benzerdir.',
        T('İdame ve hasta uyumu'),
        B(['5 yıl: peri-implantitis insidansı %18 (uyumlu) / %44 (uyumsuz)', '6,5 yıl: tüm randevulara gelen → başarısızlık ↓ (OR 0,15)'], title='Uyum', cue=1),
        src='s. 16–17 · 5.4'),
    say('Plak da belirleyicidir. {1}Ameliyat öncesi plak indeksindeki her bir birimlik artış, başarı olasılığını yüzde 87 azaltmıştır. {2}Ameliyattan 6 hafta sonra plak varlığı, 12. ayda 5 milimetreyi aşan kalan cepleri ve süren kanamayı yordamıştır. {3}3 yıllık bir randomize çalışmada tam uyumlu hastalarda, yani yılda iki kez destekleyici tedaviye gelenlerde, daha olumlu sonuç eğilimi görülmüştür: yüzde 32\'ye karşı yüzde 13. {4}Yazarlara göre bu veriler, cerrahi sonrası nüksü önlemede hem hastanın kendi uyguladığı hem de profesyonel biyofilm kontrolünün önemini gösterir.',
        CLEAR, T('Plak kontrolü'),
        B(['Başlangıç mPI: her +1 birim → başarı odds\'u %87 ↓ (OR 0,13)'], cue=1),
        P('6. haftada plak → 12. ayda kalan PD >5 mm ve süren BOP', cue=2),
        P('RKÇ, 3 yıl: tam uyum (yılda 2 kez) %32 · kısmi uyum %13', cue=3),
        X('Hastanın kendi uyguladığı + profesyonel biyofilm kontrolü = nüksü önlemenin temeli', 'key', cue=4),
        src='s. 16–17 · 5.4'),
    q('idame-q1', 'H5.b', 'Makaleye göre cerrahi sonrası sonucu korumada en kritik hasta faktörü hangisidir?', [
        o('Destekleyici idame tedavisine uyum', True),
        o('Hastanın cinsiyeti', why='Cinsiyetle ilgili bulgular tutarsızdır.'),
        o('Sigara içme durumu', why='Sigaranın cerrahi sonuca etkisi tutarsızdır.')],
      probe=True, expl='Güncel kanıtlar, cerrahiyle elde edilen sonucu korumada hastanın destekleyici bakıma uyumunun kritik rolünü vurgular.', src='s. 16–17 · 5.4, 6'),
    q('idame-q2', 'H5.b', 'Bu hasta için makaleyle en uyumlu yaklaşım hangisidir?', [
        o('Cerrahi başarılı olduğu için kontrol randevuları gerekli değildir.', why='Uyumsuz hastalarda peri-implantitis ve başarısızlık daha sık görülmüştür.'),
        o('Düzenli destekleyici tedaviye uyumun önemi ve plak kontrolü vurgulanmalıdır; uyumsuzluk nüks riskini artırır.', True),
        o('Plak birikimi sonucu etkilemez; yalnız cerrahi teknik önemlidir.', why='Ameliyat sonrası plak, kalan cep ve süren kanamayı yordamıştır.')],
      kind='application',
      scenario='Kurgusal bir olgu: Rekonstrüktif cerrahiden 6 hafta sonra hastanın implant çevresinde belirgin plak var. Hasta "Ameliyat başarılı geçti, artık kontrollere gelmem gerekmez herhalde" diyor.',
      expl='Erken dönemde plak varlığı ve kontrol randevularına uyumsuzluk, kalan cep, süren kanama ve nüksle ilişkilidir.', src='s. 16–17 · 5.4'),
])

section('sonuc', 'Toparlayalım', [], [
    say('Makalenin sonucu tek bir cümlede toplanabilir: {1}Cerrahi peri-implantitis tedavisinin sonucu, defekt morfolojisi, hastalık şiddeti, implant yüzey özellikleri, cerrahi deneyim ve hastanın destekleyici bakıma uyumunun karmaşık etkileşimiyle belirlenir. {2}Klinik olarak da dikkatli olgu seçimi, defekte özgü cerrahi planlama ve ameliyat sonrası sıkı idame, öngörülebilirliği ve uzun dönem stabiliteyi artırmak için gereklidir.',
        T('Sonuç'),
        FLOW(['Defekt morfolojisi', 'Hastalık şiddeti', 'İmplant yüzeyi', 'Cerrahi deneyim', 'İdameye uyum'], title='Sonucu belirleyen etkileşim', cue=1),
        B(['Dikkatli olgu seçimi', 'Defekte özgü cerrahi planlama', 'Ameliyat sonrası sıkı idame'], title='Klinik çıkarım', cue=2),
        src='s. 2 · Özet; s. 17 · 6'),
    say('Kesin sonuç çıkarılamayan konuları da unutmayalım: {1}flep tasarımı, iyileşme modu, membran, sistemik antibiyotik, biyolojik ajanlar, periodontitis öyküsü, sigara ve cinsiyet. Hastanın sistemik sağlık durumunun etkisi ise veri azlığı nedeniyle değerlendirilememiştir. {2}Şimdi hedefler tablosuna bakın. Kırmızı kalan alt hedeflerle ilgili bölümleri yeniden dinleyebilirsiniz.',
        X('Kesin sonuç yok: flep · iyileşme modu · membran · antibiyotik · biyolojikler · periodontitis öyküsü · sigara · cinsiyet. Sistemik sağlık değerlendirilemedi.', 'warn', cue=1),
        X('Hedefler tablosu: sağ üstteki hedef simgesi', 'note', cue=2),
        src='s. 1, 17–18 · Özet, 6'),
])

sessions = [
    {'id': 'G1', 'title': 'Makaleyi ve başarıyı birlikte okuma', 'minutes': 30, 'sections': ['giris', 'kanit', 'basari', 'sonuc-turu']},
    {'id': 'G2', 'title': 'Defekt ve cerrahi tercihlerin gerekçesi', 'minutes': 30, 'sections': ['flep', 'defekt', 'secim', 'greft', 'biyolojik', 'membran', 'iyilesme', 'antibiyotik', 'operator']},
    {'id': 'G3', 'title': 'Lokal/hasta faktörleri ve takip', 'minutes': 30, 'sections': ['siddet', 'km', 'konum', 'yuzey', 'postop', 'protez', 'makrofaj', 'hasta', 'idame', 'sonuc']},
]

# ---------- Hedefler: ALT_HEDEFLER.json\'dan aynen ----------
alt = json.load(open(ALT))
PARENTS = {
    'H1': 'Derlemenin tasarımı ve kanıt sınırı',
    'H2': 'Başarı ve sonuç ölçütleri',
    'H3': 'Defekt morfolojisi ve olgu seçimi',
    'H4': 'Lokal başlangıç faktörleri ve takip',
    'H5': 'Hasta faktörleri ve destekleyici bakım',
    'H6': 'Yardımcı uygulamalar ve cerrahi teknik',
}
goals = []
for pid, title in PARENTS.items():
    subs = []
    for sg in alt['subgoals']:
        if sg['parent'] != pid: continue
        pages = sg['pages']
        pr = f's. {pages[0]}' if len(pages) == 1 else f's. {pages[0]}–{pages[-1]}'
        subs.append({'id': sg['id'], 'text': sg['label'], 'sourceRef': f"{pr} · {sg['section']}"})
    goals.append({'id': pid, 'title': title, 'subgoals': subs})
assert sum(len(g['subgoals']) for g in goals) == 22

lesson = {
    'schemaVersion': 1,
    'id': 'peri-implantitis-cerrahi',
    'title': 'Peri-implantitiste cerrahi tedavinin etkinliğini etkileyen faktörler',
    'subtitle': 'Ramanauskaite ve ark., Periodontology 2000, 2026 · pilot ders',
    'language': 'tr-TR',
    'level': 'Uzmanlık / ileri lisans',
    'estimatedMinutes': 90,
    'authors': ['KlinikKoç örnek dersi'],
    'source': {
        'citation': 'Ramanauskaite A, Zhou W, Cafferata EA, Schwarz F. Factors influencing the effectiveness of surgical therapy of peri-implantitis. Periodontol 2000. 2026;00:1–21.',
        'doi': '10.1111/prd.70052',
        'license': 'CC BY 4.0 · Türkçe anlatım, sorular ve şekil kırpımları bu derse aittir; yazarların onayı anlamına gelmez.'
    },
    'audio': {'manifest': 'audio/manifest.json'},
    'assets': assets,
    'goals': goals,
    'misconceptions': misconceptions,
    'sessions': sessions,
    'sections': sections,
}
json.dump(lesson, open(OUT, 'w'), ensure_ascii=False, indent=2)
open(OUT, 'a').write('\n')
print('yazıldı', OUT, len(sections), 'bölüm')
