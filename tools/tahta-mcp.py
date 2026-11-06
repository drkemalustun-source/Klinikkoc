#!/usr/bin/env python3
"""Akıllı Tahta için MCP sunucusu: Claude masaüstü uygulaması tahtayı canlı yönetir.

API anahtarı gerekmez. Claude, sizin aboneliğinizle masaüstü uygulamasında çalışır;
bu dosya ona tahtayı yönetecek araçlar verir (tahtayı aç, ders oku, şekle bak,
tahtaya yaz ve anlat, soru sor, durdur). Komutlar bu bilgisayardaki
tools/sunucu.py'ye, oradan tarayıcıdaki canli.html sayfasına gider.

Kurulum (bir kez):
  python tools/tahta-mcp.py --kur
  Sonra Claude masaüstü uygulamasını tamamen kapatıp (sistem tepsisinden "Quit") yeniden açın.

Kaldırma:
  python tools/tahta-mcp.py --kaldir

Yalnızca Python'un kendi kitaplığı gerekir. Doğal ses için ayrıca Piper:
  python tools/ses-uret.py --kur   (zaten kuruluysa gerekmez)
"""
import base64
import glob
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(os.environ.get("AKILLI_TAHTA_PORT", "8800"))
ADRES = "http://127.0.0.1:%d" % PORT
SURUM = "0.4.0"
AD = "akilli-tahta"

TALIMAT = """Akıllı Tahta: bu bilgisayardaki tarayıcıda açık bir kara tahta. Bu araçlarla
tahtaya yazar, ders görsellerini gösterip işaretler ve Türkçe sesli anlatırsın (Pocket TTS Türkçe Kadın 3 sesi; hazır değilse Piper dfki).
Eğitmen (İnci ya da Mercan): Bir dersi öğretmeye başlamadan önce egitmen_hazirla aracını çağır. O araç
dersin eğitmenini, öğretim kurallarını, hedeflerini, öğretmen notlarını ve öğrencinin kaydını verir; bütün
oturum boyunca o kurallara uy. Öğrencinin ilerlemesini kayit_yaz ile işle, bitişte rapor_yaz ile rapor yaz.
Pilot ölçme testleri (ön/son/gecikmeli) yalnız olcme_testi ve olcme_kaydet araçlarıyla, öğretmenin onayladığı
sorularla yapılır; test sırasında ipucu ve açıklama verilmez.
Nasıl çalış:
- İlk iş tahtayi_ac. Ders konusu varsa dersler ve ders_oku ile içeriği oku; şekli işaretleyeceksen
  önce gorsel_bak ile görseli gör (işaret koordinatları görselin 0–1 arası oranlarıdır).
- tahta aracında anlatımı 2–6 adıma böl. Her adımda önce tahta komutları, sonra o adımın anlatımı.
  Anlatım konuşma dilinde, kısa cümlelerle, ders kitabı Türkçesiyle olsun; madde başına en çok ~10 sözcük.
- Tahtada tek görsel alan vardır (image, table, flow, compare, draw'dan biri); yanında title, bullets,
  term, text notları durabilir. Yeni konuya geçerken {"type":"clear"} ile başla.
- Ders görselleri dışında görsel kullanma; kendi çizimin için draw komutunu kullan.
- Bilgi dersin içeriğine dayansın; dersin dışına çıkarsan bunu açıkça söyle.
- Anlatım bitince sohbet penceresinde çok kısa özet ver; tahtada anlattığını sohbete tekrar yazma.
Sesli sohbet (dikte): Kullanıcı tahtadaki mikrofon tuşuna (ya da M tuşuna) basıp konuşabilir; söyledikleri
yazıya çevrilip sana gelir. Tuşa basmak anlatımı keser (söz alır).
- Ders ya da sohbet sırasında bir bölümü/cevabı bitirince dinle aracını çağır; gelen metne tahtada sesli
  cevap ver (gerekirse çizerek), sonra yeniden dinle. "sessiz" dönerse bir-iki kez daha dinle; uzun
  sessizlikte döngüyü bırak ve sohbete kısa bir not yaz.
- tahta, soru_sor ve tahta_durumu sonuçlarında 'kullanici_konustu' alanı varsa kullanıcı o sırada
  konuşmuştur; önce ona cevap ver.
- "dur", "bekle", "ara verelim" gibi isteklerde dinlemeyi de bırak.
Duraklat: Kullanıcı tahtadaki ⏸ tuşuyla (ya da P / Boşluk) anlatımı duraklatabilir. Bu iptal değildir.
- tahta, soru_sor ya da tahta_durumu 'duraklatildi' dönerse hata sayma, yeni komut gönderme, sohbete de
  yazma; aynı no ile tahta_durumu çağırarak beklemeyi sürdür. Devam edince anlatım kaldığı yerden sürer
  ve sonuç olağan biçimde 'bitti' gelir. Uzun süre duraklatılmış kalırsa beklemeyi bırakıp kısa bir not yaz."""

KOMUT_SEMASI = {
    "type": "object",
    "description": "Tahta komutu. Türe göre alanlar: "
                   "clear | title{text,subtitle} | bullets{title?,items[]} | point{text} | text{text,style?:note|key|warn} | "
                   "term{term,definition} | image{asset,caption?} | highlight{region[x,y,g,y] 0–1,label?,color?,shape?:rect|ellipse,id?} | "
                   "unhighlight{id?} | zoom{region} | unzoom | table{title?,headers[],rows[][],caption?} | "
                   "flow{title?,nodes[],direction?:row|column} | compare{title?,columns[{title,items[],color?}]} | "
                   "draw{title?,viewBox?='0 0 160 90',shapes[{kind:line|arrow|rect|ellipse|path|text, ...}]}. "
                   "ANATOMİK ŞABLON (diş/implant çizimi için serbest çizim yerine bunu kullan): "
                   "draw{title?,template:dis|implant,variant?,labels?[{part,text?,side?:sol|sag,color?}] ya da 'hepsi',"
                   "highlight?[part],probe?:true,shapes?[ek şekiller, aynı 160x90 tuvalde]}. Bukkal solda, ~3,4 birim = 1 mm. "
                   "dis variant: saglikli|gingivitis|periodontitis; parçalar: mine, dentin, pulpa, kok-kanali, apeks, mine-sement, "
                   "sement, pdl, kemik, kret, dis-eti, yapisik-dis-eti, mgj, mukoza, dis-eti-epiteli, cep, ba (birleşim epiteli), "
                   "bd (bağ dokusu ataşmanı), dis; gingivitis/periodontitis ek: iltihap, plak; periodontitis ek: tartar, "
                   "atasman-kaybi, kemik-kaybi. implant variant: saglikli|mukozitis|peri-implantitis; parçalar: kron, dayanak, "
                   "platform, implant, yiv, mukoza, cep, bariyer-epiteli, bd, kemik, osseo, kret, alveol-mukozasi; "
                   "mukozitis/peri-implantitis ek: iltihap, plak, kanama; peri-implantitis ek: krater, supurasyon, acik-yiv. "
                   "probe:true periodontal sondayı cebe yerleştirir (parça: sonda, derinliği mm yazar). "
                   "Adım adım kurmak için aynı template+variant ile labels listesini büyüterek yeniden gönder: çizim yerinde kalır, "
                   "yalnız yeni etiketler belirir. Etiket metnini yazmazsan doğru Türkçe terim kullanılır. "
                   "Renkler: chalk, accent, warn, ok. Metinde **kalın** ve _italik_ kullanılabilir.",
    "properties": {"type": {"type": "string", "enum": [
        "clear", "title", "bullets", "point", "text", "term", "image", "highlight", "unhighlight",
        "zoom", "unzoom", "table", "flow", "compare", "draw"]}},
    "required": ["type"],
    "additionalProperties": True,
}

ARACLAR = [
    {
        "name": "egitmen_hazirla",
        "description": "Bir dersi öğretmeden önce ilk çağrılacak araç. Dersin eğitmenini (İnci: lisans, Mercan: uzmanlık), "
                       "öğretim kurallarını, hedefleri ve Bloom hedef düzeylerini, öğretmen notlarını, bilinen yanılgıları "
                       "ve ogrenci verilirse öğrencinin kaydını (tekrar zamanı gelen hedefler, mola noktası) döndürür. "
                       "Dönen kurallara bütün oturum boyunca uy.",
        "inputSchema": {"type": "object", "properties": {
            "ders": {"type": "string"},
            "ogrenci": {"type": "string", "description": "öğrencinin adı (kayıt yalnız bu bilgisayarda tutulur)"},
            "egitmen": {"type": "string", "enum": ["inci", "mercan"],
                        "description": "yalnız ders izin veriyorsa başka eğitmen seçmek için"}},
            "required": ["ders"]},
    },
    {
        "name": "kayit_yaz",
        "description": "Öğrencinin ilerlemesini bu bilgisayardaki kayda işler. Her anlamlı adımdan sonra çağır. "
                       "hedefler: [{id, duzey (hatirla|anla|uygula|cozumle|degerlendir|olustur), yardim (yardimsiz|destekle), "
                       "dogru, solo (yapi_oncesi|tek|cok|iliskisel|genisletilmis), durum (ele_alinmadi|destekle_yapti|"
                       "bagimsiz_yapti|tekrar_gerekli), tur (yanit|geri_cagirma|uygulama), kanit (tek cümle)}]. "
                       "yanilgilar: [{id, durum (acik|cozuldu), not}]. guven: [{hedef, soru, guven (tahmin|biraz|emin), dogru}]. "
                       "sorular: [{soru, kaynakta_yok}]. testler: [{tur (on|son|gecikmeli), dogru, toplam}]. "
                       "mod: once_anlat|once_yanitla. mola: bekleyen nokta metni ya da null. oturum: {egitmen, ozet}. "
                       "Aralıklı tekrar tarihleri otomatik hesaplanır.",
        "inputSchema": {"type": "object", "properties": {
            "ogrenci": {"type": "string"}, "ders": {"type": "string"},
            "hedefler": {"type": "array", "items": {"type": "object"}},
            "yanilgilar": {"type": "array", "items": {"type": "object"}},
            "guven": {"type": "array", "items": {"type": "object"}},
            "sorular": {"type": "array", "items": {"type": "object"}},
            "testler": {"type": "array", "items": {"type": "object"}},
            "mod": {"type": "string"}, "mola": {"type": ["string", "null"]},
            "oturum": {"type": "object"}},
            "required": ["ogrenci", "ders"]},
    },
    {
        "name": "kayit_oku",
        "description": "Öğrencinin bu dersteki kaydının özetini verir (hedef düzeyleri, açık yanılgılar, tekrar zamanı "
                       "gelenler, mola noktası). ayrinti=true ile bütün kayıt.",
        "inputSchema": {"type": "object", "properties": {
            "ogrenci": {"type": "string"}, "ders": {"type": "string"}, "ayrinti": {"type": "boolean"}},
            "required": ["ogrenci", "ders"]},
    },
    {
        "name": "rapor_yaz",
        "description": "Oturum sonunda ya da 'rapor oluştur' denince öğretmen için Markdown rapor yazar (öğrencinin "
                       "bilgisayarında, kayitlar/<ad>/raporlar/). Hedef tablosu, yanılgılar, güven ve sorular kayıttan "
                       "otomatik gelir; sen ogretmen_ozeti (6–8 cümle) ve isteğe bağlı guclukler, oneriler, geri_bildirim yaz.",
        "inputSchema": {"type": "object", "properties": {
            "ogrenci": {"type": "string"}, "ders": {"type": "string"},
            "ogretmen_ozeti": {"type": "string"}, "guclukler": {"type": "string"},
            "oneriler": {"type": "string"}, "geri_bildirim": {"type": "string"}},
            "required": ["ogrenci", "ders", "ogretmen_ozeti"]},
    },
    {
        "name": "olcme_testi",
        "description": "Pilot ölçme testini başlatır: öğretmenin onayladığı soruları (ön test, son test ya da gecikmeli "
                       "test) seçenek sırası bu öğrenci için karıştırılmış olarak verir ve testin nasıl uygulanacağını "
                       "söyler. Yalnız öğrenci kabul ederse ya da isterse çağır. Test bitince olcme_kaydet ile kaydet.",
        "inputSchema": {"type": "object", "properties": {
            "ders": {"type": "string"}, "ogrenci": {"type": "string"},
            "tur": {"type": "string", "enum": ["on", "son", "gecikmeli"]}},
            "required": ["ders", "ogrenci", "tur"]},
    },
    {
        "name": "olcme_kaydet",
        "description": "Biten ölçme testinin yanıtlarını kaydeder ve puanlar. Çoktan seçmelilerde tahtanın döndürdüğü "
                       "secim (0'dan başlayan sıra) verilir, puanı araç hesaplar. Kısa yazılı sorularda ölçüte göre "
                       "puan (0, 1, 2) ve yanit_ozet verilir. Her soruda guven: tahmin|biraz|emin.",
        "inputSchema": {"type": "object", "properties": {
            "ders": {"type": "string"}, "ogrenci": {"type": "string"},
            "tur": {"type": "string", "enum": ["on", "son", "gecikmeli"]},
            "yanitlar": {"type": "array", "items": {"type": "object", "properties": {
                "no": {"type": "string"}, "secim": {"type": "integer"}, "puan": {"type": "integer"},
                "yanit_ozet": {"type": "string"},
                "yanilgi_secildi": {"type": "boolean", "description": "kısa yanıtta ölçütteki yanılgı dile getirildiyse true"},
                "guven": {"type": "string", "enum": ["tahmin", "biraz", "emin"]}},
                "required": ["no"]}},
            "yarim_kaldi": {"type": "boolean", "description": "öğrenci testi bitirmeden bıraktıysa true"}},
            "required": ["ders", "ogrenci", "tur", "yanitlar"]},
    },
    {
        "name": "tahtayi_ac",
        "description": "Tahtayı hazırlar: yerel sunucu kapalıysa açar, canlı tahta sayfası açık değilse "
                       "tarayıcıda açar ve bağlanmasını bekler. Derse başlamadan önce bir kez çağır.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "dersler",
        "description": "Bilgisayardaki dersleri, bölümlerini ve görsellerini listeler.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ders_oku",
        "description": "Bir dersin içeriğini okur. bolum verilmezse ders planı (hedefler, bölümler, görseller); "
                       "bolum verilirse o bölümün anlatım metni, tahta komutları ve soruları; sayfa verilirse "
                       "kaynağın (ders notu ya da makale) o sayfasının metni.",
        "inputSchema": {"type": "object", "properties": {
            "ders": {"type": "string", "description": "ders kimliği, ör. peri-implantitis-cerrahi"},
            "bolum": {"type": "string", "description": "bölüm kimliği (isteğe bağlı)"},
            "sayfa": {"type": "integer", "description": "kaynağın bu sayfasının metnini ve o sayfaya ait öğretmen notlarını oku"}},
            "required": ["ders"]},
    },
    {
        "name": "gorsel_bak",
        "description": "Bir ders görselini sana gösterir; işaretleme ve yakınlaştırma bölgelerini seçmek için kullan.",
        "inputSchema": {"type": "object", "properties": {
            "ders": {"type": "string"}, "gorsel": {"type": "string", "description": "görsel kimliği, ör. sekil2"}},
            "required": ["ders", "gorsel"]},
    },
    {
        "name": "tahta",
        "description": "Tahtaya yazar ve sesli anlatır. adimlar sırayla uygulanır: her adımda önce komutlar "
                       "tahtaya çizilir, sonra anlat metni okunur. Anlatım ~40 sn'den uzun sürerse araç "
                       "'sürüyor' döner; bitişini tahta_durumu ile bekleyebilirsin. Kullanıcı tahtada duraklattıysa "
                       "'duraklatildi' döner: hata değil, tahta_durumu ile beklemeyi sürdür.",
        "inputSchema": {"type": "object", "properties": {
            "ders": {"type": "string", "description": "image komutu kullanılacaksa görsellerin alınacağı ders"},
            "adimlar": {"type": "array", "minItems": 1, "maxItems": 12, "items": {
                "type": "object", "properties": {
                    "komutlar": {"type": "array", "items": KOMUT_SEMASI},
                    "anlat": {"type": "string", "description": "bu adımda sesli okunacak metin"}}}},
            "bekle": {"type": "boolean", "description": "anlatımın bitmesini bekle (varsayılan: evet)"}},
            "required": ["adimlar"]},
    },
    {
        "name": "soru_sor",
        "description": "Tahtada çoktan seçmeli bir soru kartı açar ve dokunulan cevabı döndürür (en çok ~40 sn bekler; "
                       "cevap gelmezse tahta_durumu ile beklemeyi sürdür). dogru verilirse kart doğru/yanlışı ve "
                       "aciklama'yı gösterir. Sorular not için değil, öğrenmek içindir.",
        "inputSchema": {"type": "object", "properties": {
            "soru": {"type": "string"},
            "secenekler": {"type": "array", "minItems": 2, "maxItems": 6, "items": {"type": "string"}},
            "dogru": {"type": "integer", "description": "doğru seçeneğin sırası, 0'dan başlar (isteğe bağlı)"},
            "aciklama": {"type": "string", "description": "cevaptan sonra kartta görünecek kısa açıklama"},
            "anlat": {"type": "string", "description": "soruyu sesli okumak için metin (isteğe bağlı)"},
            "etiket": {"type": "string", "description": "kartın üstündeki küçük etiket, ör. 'Ön test · 3/12'"}},
            "required": ["soru", "secenekler"]},
    },
    {
        "name": "tahta_durumu",
        "description": "Tahtanın durumunu verir. no verilirse o komutun (anlatım ya da soru) bitmesini en çok ~40 sn bekler "
                       "ve sonucunu döndürür. 'duraklatildi': kullanıcı anlatımı duraklattı; aynı no ile beklemeyi sürdür.",
        "inputSchema": {"type": "object", "properties": {"no": {"type": "integer"}}},
    },
    {
        "name": "dinle",
        "description": "Kullanıcının tahtadaki mikrofon tuşuyla söylediğini bekler ve yazı olarak döndürür "
                       "(en çok ~40 sn). Kimse konuşmazsa 'sessiz' döner; yeniden çağırabilirsin. Sesli sohbet "
                       "döngüsü: anlat → dinle → cevapla → dinle.",
        "inputSchema": {"type": "object", "properties": {
            "bekle": {"type": "integer", "description": "en çok kaç saniye beklensin (5–50, varsayılan 40)"}}},
    },
    {
        "name": "durdur",
        "description": "Anlatımı hemen keser ve sıradaki komutları iptal eder.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# ---------- Yerel sunucuyla konuşma ----------
def istek(yol, govde=None, zaman=60):
    veri = None if govde is None else json.dumps(govde, ensure_ascii=False).encode("utf-8")
    r = urllib.request.Request(ADRES + "/api/canli/" + yol, data=veri,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=zaman) as y:
        return json.loads(y.read().decode("utf-8"))


def sunucu_acik():
    try:
        return istek("durum", zaman=3)
    except Exception:
        return None


def sunucuyu_baslat():
    betik = os.path.join(KOK, "tools", "sunucu.py")
    arg = [sys.executable, betik, "--acma", "--port", str(PORT)]
    if os.name == "nt":
        # Ayrı bir konsol penceresinde açılır; kapatmak için o pencereyi kapatmak yeter.
        subprocess.Popen(arg, cwd=KOK, creationflags=subprocess.CREATE_NEW_CONSOLE,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(arg, cwd=KOK, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)


def gonder(komut, bekle=True):
    try:
        return istek("gonder", {"komut": komut, "bekle": 40 if bekle else 0.5}, zaman=70)
    except urllib.error.URLError:
        return {"durum": "bağlı değil", "hata": "Yerel tahta sunucusu kapalı. Önce tahtayi_ac aracını çağır."}


# ---------- Ders dosyaları ----------
def katalog():
    yol = os.path.join(KOK, "lessons", "katalog.json")
    girisler = []
    if os.path.exists(yol):
        girisler = json.load(open(yol, encoding="utf-8")).get("lessons", [])
    bilinen = {g["id"] for g in girisler}
    for d in sorted(glob.glob(os.path.join(KOK, "lessons", "*", "ders.json")) +
                    glob.glob(os.path.join(KOK, "lessons", "*", "egitmen.json"))):
        i = os.path.basename(os.path.dirname(d))
        if i not in bilinen:
            bilinen.add(i)
            girisler.append({"id": i, "path": "lessons/%s/" % i})
    return girisler


def ders_yolu(ders, *parca):
    if not ders or any(c in ders for c in "/\\.") or ders.startswith("_"):
        raise ValueError("Geçersiz ders kimliği")
    return os.path.join(KOK, "lessons", ders, *parca)


def egitmen_json(ders):
    yol = ders_yolu(ders, "egitmen.json")
    return json.load(open(yol, encoding="utf-8")) if os.path.exists(yol) else None


def ders_json(ders):
    """ders.json'u döndürür. Yalnız egitmen.json olan (canlı) derste ondan özet bir ders kurar."""
    yol = ders_yolu(ders, "ders.json")
    if os.path.exists(yol):
        return json.load(open(yol, encoding="utf-8"))
    eg = egitmen_json(ders)
    if not eg:
        raise ValueError("Ders bulunamadı: %s. dersler aracıyla listeye bak." % ders)
    assets = {k: {"src": g["src"], "caption": "%s. %s" % (g.get("baslik", k), g.get("aciklama", "")),
                  "alt": g.get("aciklama")} for k, g in (eg.get("gorseller") or {}).items()}
    kay = eg.get("kaynak") or {}
    if kay.get("sayfaGorseli"):
        for i in range(1, int(kay.get("sayfaSayisi") or 0) + 1):
            nn = "%02d" % i
            assets["sayfa-" + nn] = {"src": kay["sayfaGorseli"].replace("{nn}", nn), "caption": "Kaynak, sayfa %d" % i}
    return {"id": ders, "title": eg.get("baslik"), "level": eg.get("duzey"), "source": kay,
            "goals": eg.get("hedefler"), "sections": [], "assets": assets, "_canli": True}


def ar_dersler(_):
    out = []
    for g in katalog():
        try:
            d = ders_json(g["id"])
        except Exception:
            continue
        eg = egitmen_json(g["id"]) or {}
        out.append({
            "ders": g["id"], "baslik": d.get("title"), "duzey": d.get("level"),
            "egitmen": eg.get("egitmen"), "yalniz_canli": bool(d.get("_canli")),
            "bolumler": [{"bolum": s["id"], "baslik": s.get("title")} for s in d.get("sections", [])],
            "gorseller": {k: v.get("caption") or v.get("alt") for k, v in (d.get("assets") or {}).items()
                          if not k.startswith("sayfa-")},
        })
    return metin(out)


def ar_ders_oku(a):
    ders = a.get("ders")
    d = ders_json(ders)
    if a.get("sayfa"):
        eg = egitmen_json(ders) or {}
        kay = eg.get("kaynak") or {}
        try:
            n = int(a["sayfa"])
        except (TypeError, ValueError):
            raise ValueError("sayfa bir sayı olmalı")
        sablon = kay.get("sayfaMetni") or "kaynak/sayfa-{nn}.txt"
        yol = ders_yolu(ders, *sablon.replace("{nn}", "%02d" % n).split("/"))
        if not os.path.exists(yol):
            return metin({"sayfa": n, "durum": "okunamadı", "not": "Bu sayfanın metni pakette yok. "
                          "'Notta yok' deme; 'bu sayfayı okuyamadım' de."})
        out = {"sayfa": n, "kaynak": kay.get("baslik"), "metin": open(yol, encoding="utf-8").read(),
               "okuma_notu": kay.get("okumaNotu")}
        if kay.get("sayfaGorseli"):
            out["sayfa_gorseli"] = "sayfa-%02d (gorsel_bak ile bakabilirsin)" % n
        notlar = [x for x in eg.get("ogretmenNotlari", []) if n in (x.get("sayfalar") or [])]
        if notlar:
            out["ogretmen_notlari"] = notlar
        return metin(out)
    bolum = a.get("bolum")
    if not bolum:
        return metin({
            "ders": d.get("id"), "baslik": d.get("title"), "duzey": d.get("level"), "kaynak": d.get("source"),
            "hedefler": d.get("goals"),
            "bolumler": [{"bolum": s["id"], "baslik": s.get("title"), "hedefler": s.get("goals"),
                          "adim": len(s.get("steps", []))} for s in d.get("sections", [])],
            "gorseller": {k: {"aciklama": v.get("alt"), "altyazi": v.get("caption")}
                          for k, v in (d.get("assets") or {}).items() if not k.startswith("sayfa-")},
            "not": "Kaynağın bir sayfasını okumak için ders_oku'yu sayfa ile çağır." if egitmen_json(ders) else None,
        })
    s = next((x for x in d.get("sections", []) if x["id"] == bolum), None)
    if not s:
        raise ValueError("Bölüm yok: %s" % bolum)
    adimlar = []
    for st in s.get("steps", []):
        x = {"adim": st["id"]}
        if st.get("say"):
            x["anlatim"] = st["say"]
        if st.get("board"):
            x["tahta"] = st["board"]
        if st.get("question"):
            q = st["question"]
            x["soru"] = {k: q.get(k) for k in ("type", "prompt", "options", "answer", "explanation", "goal") if q.get(k) is not None}
        if st.get("sourceRef"):
            x["kaynak"] = st["sourceRef"]
        adimlar.append(x)
    return metin({"bolum": s["id"], "baslik": s.get("title"), "hedefler": s.get("goals"), "adimlar": adimlar})


def ar_gorsel_bak(a):
    d = ders_json(a.get("ders"))
    g = (d.get("assets") or {}).get(a.get("gorsel"))
    if not g:
        raise ValueError("Görsel yok. Bu dersin görselleri: " + ", ".join(
            k for k in (d.get("assets") or {}) if not k.startswith("sayfa-")) + " (ve sayfa-01, sayfa-02 ... varsa)")
    yol = os.path.normpath(os.path.join(KOK, "lessons", a["ders"], g["src"]))
    uz = os.path.splitext(yol)[1].lower()
    tur = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
           ".gif": "image/gif"}.get(uz)
    alt = g.get("alt") or ""
    bilgi = "%s\n%s\nİşaretlerken bölge [sol, üst, genişlik, yükseklik] görselin 0–1 arası oranlarıdır." % (
        g.get("caption") or "", "" if alt and alt in (g.get("caption") or "") else alt)
    eg = egitmen_json(a["ders"]) or {}
    eg_g = (eg.get("gorseller") or {}).get(a.get("gorsel")) or {}
    for k in ("ogretmenNotu", "kaynakNotu"):
        if eg_g.get(k):
            bilgi += "\n%s: %s" % ("Öğretmen notu" if k == "ogretmenNotu" else "Kaynak notu", eg_g[k])
    if not tur:
        return {"content": [{"type": "text", "text": bilgi + "\n(Bu görsel türü gösterilemiyor: %s)" % uz}]}
    veri = base64.b64encode(open(yol, "rb").read()).decode("ascii")
    return {"content": [{"type": "image", "data": veri, "mimeType": tur}, {"type": "text", "text": bilgi}]}


# ---------- Eğitmen, öğrenci kaydı, rapor ----------
EGITMENLER = {"inci": "İnci (lisans)", "mercan": "Mercan (uzmanlık)"}
BLOOM = ["hatirla", "anla", "uygula", "cozumle", "degerlendir", "olustur"]
BLOOM_AD = dict(zip(BLOOM, ["hatırla", "anla", "uygula", "çözümle", "değerlendir", "oluştur"]))
DURUM_AD = {"ele_alinmadi": "ele alınmadı", "destekle_yapti": "destekle yaptı", "bagimsiz_yapti": "bağımsız yaptı",
            "tekrar_gerekli": "tekrar gerekli", "devam_ediyor": "devam ediyor"}
TEKRAR_GUN = {1: 1, 2: 3, 3: 7, 4: 21}  # Leitner kutusu → sonraki geri çağırmaya kadar gün
KAYIT_KOK = os.environ.get("AKILLI_TAHTA_KAYIT") or os.path.join(KOK, "kayitlar")


def bugun():
    return time.strftime("%Y-%m-%d")


def gun_ekle(tarih, gun):
    t = time.mktime(time.strptime(tarih, "%Y-%m-%d")) + gun * 86400 + 3600
    return time.strftime("%Y-%m-%d", time.localtime(t))


def ogrenci_klasoru(ad):
    ad = (ad or "").strip()
    if not ad:
        raise ValueError("ogrenci (öğrencinin adı) gerekli")
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ ", "cgiosuCGIOSU-")
    kisa = "".join(c for c in ad.translate(tr).lower() if c.isalnum() or c == "-")[:60] or "ogrenci"
    return os.path.join(KAYIT_KOK, kisa)


def kayit_yolu(ogrenci, ders):
    ders_yolu(ders)  # kimlik denetimi
    return os.path.join(ogrenci_klasoru(ogrenci), ders + ".json")


def kayit_yukle(ogrenci, ders):
    yol = kayit_yolu(ogrenci, ders)
    if os.path.exists(yol):
        return json.load(open(yol, encoding="utf-8"))
    return {"ogrenci": ogrenci.strip(), "ders": ders, "olusturma": bugun(), "mod": "once_anlat",
            "hedefler": {}, "yanilgilar": {}, "guven": [], "sorular": [], "testler": [], "oturumlar": [], "mola": None}


def kayit_kaydet(k):
    yol = kayit_yolu(k["ogrenci"], k["ders"])
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    gecici = yol + ".tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(k, f, ensure_ascii=False, indent=1)
    os.replace(gecici, yol)
    return yol


def tekrar_zamani_gelenler(k):
    b = bugun()
    return sorted([h for h, v in k["hedefler"].items()
                   if v.get("sonraki_tekrar") and v["sonraki_tekrar"] <= b],
                  key=lambda h: k["hedefler"][h]["sonraki_tekrar"])


def kayit_ozeti(k, eg):
    hedefler = {x["id"]: x for x in (eg or {}).get("hedefler", [])}
    ozet = {}
    for hid, h in hedefler.items():
        v = k["hedefler"].get(hid, {})
        ozet[hid] = {"baslik": h.get("baslik"), "hedef_duzey": h.get("bloom"),
                     "ulasilan_yardimsiz": v.get("yardimsiz_duzey"), "ulasilan_destekle": v.get("destekle_duzey"),
                     "durum": v.get("durum", "ele_alinmadi"), "sonraki_tekrar": v.get("sonraki_tekrar")}
    return {"hedefler": ozet,
            "acik_yanilgilar": [y for y, v in k["yanilgilar"].items() if v.get("durum") == "acik"],
            "tekrar_zamani_gelen": tekrar_zamani_gelenler(k),
            "mola": k.get("mola"), "mod": k.get("mod"),
            "oturum_sayisi": len(k.get("oturumlar", [])),
            "testler": [{"tur": t.get("tur"), "tarih": t.get("tarih"), "puan": t.get("puan"), "toplam": t.get("toplam"),
                         "secilen_yanilgilar": t.get("secilen_yanilgilar")} for t in k.get("testler", [])]}


def ar_egitmen_hazirla(a):
    ders = a.get("ders")
    eg = egitmen_json(ders)
    d = ders_json(ders)
    if not eg:
        eg = {"egitmen": "inci", "izinliEgitmenler": ["inci", "mercan"], "hedefler": [
            {"id": s["id"], "baslik": s.get("text")} for g in d.get("goals", []) for s in g.get("subgoals", [])]}
    secilen = (a.get("egitmen") or eg.get("egitmen") or "inci").lower()
    izinli = eg.get("izinliEgitmenler") or [eg.get("egitmen")]
    not_ = None
    if secilen not in izinli:
        not_ = "%s bu ders için açık değil; dersin eğitmeni %s kullanılıyor." % (secilen, eg.get("egitmen"))
        secilen = eg.get("egitmen")
    if secilen not in EGITMENLER:
        raise ValueError("Bilinmeyen eğitmen: %s" % secilen)
    kurallar = open(os.path.join(KOK, "egitmenler", "ortak.md"), encoding="utf-8").read() + "\n\n" + \
        open(os.path.join(KOK, "egitmenler", secilen + ".md"), encoding="utf-8").read()
    out = {"egitmen": EGITMENLER[secilen], "izinli_egitmenler": [EGITMENLER.get(x, x) for x in izinli],
           "kurallar": kurallar,
           "ders": {"kimlik": ders, "baslik": eg.get("baslik") or d.get("title"), "duzey": eg.get("duzey"),
                    "kaynak": eg.get("kaynak") or d.get("source"), "hedefler": eg.get("hedefler"),
                    "ogretmen_notlari": eg.get("ogretmenNotlari"), "bilinen_yanilgilar": eg.get("yanilgilar"),
                    "oturumlar": eg.get("oturumlar"), "arac_seti": eg.get("aracSeti"), "olcme": olcme_ozeti(eg),
                    "gorseller": {k: v.get("aciklama") for k, v in (eg.get("gorseller") or {}).items()}
                    or {k: v.get("caption") for k, v in (d.get("assets") or {}).items()},
                    "hazir_anlatim_bolumleri": [s["id"] for s in d.get("sections", [])]},
           "bloom_sirasi": BLOOM}
    if not_:
        out["not"] = not_
    if a.get("ogrenci"):
        k = kayit_yukle(a["ogrenci"], ders)
        out["ogrenci"] = {"ad": k["ogrenci"], "kayit": kayit_ozeti(k, eg),
                          "ilk_oturum": not k.get("oturumlar"), "olcme_sirasi": olcme_sirasi(k, eg)}
    else:
        out["ogrenci"] = "Adı bilinmiyor: öğrenciye bir kez adını sor, sonra egitmen_hazirla'yı ogrenci ile yeniden çağır."
    return metin(out)


def ar_kayit_oku(a):
    k = kayit_yukle(a.get("ogrenci"), a.get("ders"))
    eg = egitmen_json(a.get("ders"))
    out = kayit_ozeti(k, eg)
    if a.get("ayrinti"):
        out["kayit"] = k
    return metin(out)


def ar_kayit_yaz(a):
    k = kayit_yukle(a.get("ogrenci"), a.get("ders"))
    eg = egitmen_json(a.get("ders")) or {}
    gecerli = {x["id"] for x in eg.get("hedefler", [])}
    uyarilar = []
    b = bugun()
    for g in a.get("hedefler") or []:
        hid = g.get("id")
        if gecerli and hid not in gecerli:
            uyarilar.append("Bilinmeyen hedef: %s" % hid)
            continue
        v = k["hedefler"].setdefault(hid, {"kutu": 0, "kanitlar": []})
        duzey = g.get("duzey")
        if duzey and duzey not in BLOOM:
            uyarilar.append("Geçersiz Bloom düzeyi: %s" % duzey)
            duzey = None
        yardimsiz = g.get("yardim") == "yardimsiz"
        if duzey:
            alan = "yardimsiz_duzey" if yardimsiz else "destekle_duzey"
            if BLOOM.index(duzey) >= BLOOM.index(v.get(alan) or "hatirla") or not v.get(alan):
                v[alan] = duzey
        if g.get("durum"):
            v["durum"] = g["durum"]
        elif duzey:
            hedef = next((x.get("bloom") for x in eg.get("hedefler", []) if x["id"] == hid), None)
            if yardimsiz and g.get("dogru", True) and hedef in BLOOM and BLOOM.index(duzey) >= BLOOM.index(hedef):
                v["durum"] = "bagimsiz_yapti"
            elif v.get("durum") != "bagimsiz_yapti":
                v["durum"] = "destekle_yapti" if not yardimsiz else "devam_ediyor"
        if duzey or g.get("tur") == "geri_cagirma":
            # Aralıklı tekrar: yardımsız başarı bir üst kutu, başarısızlık ya da yardım 1. kutu.
            v["kutu"] = min(4, v.get("kutu", 0) + 1) if (yardimsiz and g.get("dogru", True)) else 1
            v["sonraki_tekrar"] = gun_ekle(b, TEKRAR_GUN[v["kutu"]])
        v["son"] = b
        if g.get("kanit"):
            v["kanitlar"] = (v.get("kanitlar") or [])[-9:] + [
                {"tarih": b, "tur": g.get("tur", "yanit"), "duzey": duzey, "yardim": g.get("yardim"),
                 "solo": g.get("solo"), "dogru": g.get("dogru"), "ozet": g["kanit"]}]
    for y in a.get("yanilgilar") or []:
        v = k["yanilgilar"].setdefault(y.get("id"), {"durum": "acik", "ilk": b})
        v["durum"] = y.get("durum", v["durum"])
        if y.get("not"):
            v["not"] = y["not"]
        v["son"] = b
    for g in a.get("guven") or []:
        k["guven"].append(dict(g, tarih=b))
    for s in a.get("sorular") or []:
        k["sorular"].append(dict(s, tarih=b))
    for t in a.get("testler") or []:
        k["testler"].append(dict(t, tarih=b))
    if a.get("mod") in ("once_anlat", "once_yanitla"):
        k["mod"] = a["mod"]
    if "mola" in a:
        k["mola"] = a.get("mola")
    if a.get("oturum"):
        o = dict(a["oturum"], tarih=b)
        if k["oturumlar"] and k["oturumlar"][-1].get("tarih") == b and not a["oturum"].get("yeni"):
            k["oturumlar"][-1].update(o)
        else:
            k["oturumlar"].append(o)
    yol = kayit_kaydet(k)
    out = {"durum": "kaydedildi", "dosya": os.path.relpath(yol, KOK), "ozet": kayit_ozeti(k, eg)}
    if uyarilar:
        out["uyarilar"] = uyarilar
    return metin(out)


def ar_rapor_yaz(a):
    ders = a.get("ders")
    k = kayit_yukle(a.get("ogrenci"), ders)
    eg = egitmen_json(ders) or {}
    hed = {x["id"]: x for x in eg.get("hedefler", [])}
    y = ["# Çalışma raporu — %s" % (eg.get("baslik") or ders), "",
         "Öğrenci: %s · Tarih: %s · Eğitmen: %s · Oturum sayısı: %d" % (
             k["ogrenci"], bugun(), EGITMENLER.get(eg.get("egitmen"), "-"), len(k.get("oturumlar", []))),
         "", "Bu rapor not için değildir. Öğrencinin bilgisayarında üretildi; otomatik gönderilmedi.", "",
         "## Öğretmen özeti", "", (a.get("ogretmen_ozeti") or "(özet yazılmadı)").strip(), ""]
    y += ["## Hedefler", "", "| Hedef | Hedef düzey | Yardımsız ulaşılan | Destekle ulaşılan | Durum | Sonraki tekrar |",
          "| --- | --- | --- | --- | --- | --- |"]
    for hid, h in hed.items():
        v = k["hedefler"].get(hid, {})
        y.append("| %s %s | %s | %s | %s | %s | %s |" % (hid, h.get("baslik", ""), BLOOM_AD.get(h.get("bloom"), "-"),
                 BLOOM_AD.get(v.get("yardimsiz_duzey"), "-"), BLOOM_AD.get(v.get("destekle_duzey"), "-"),
                 DURUM_AD.get(v.get("durum", "ele_alinmadi"), v.get("durum")), v.get("sonraki_tekrar") or "-"))
    yan = {x["id"]: x for x in eg.get("yanilgilar", [])}
    if k["yanilgilar"]:
        y += ["", "## Yanılgılar", ""]
        for yid, v in k["yanilgilar"].items():
            y.append("- **%s** (%s): %s%s" % (yid, v.get("durum"), yan.get(yid, {}).get("metin", ""),
                                              (" — " + v["not"]) if v.get("not") else ""))
    yanlis_emin = [g for g in k.get("guven", []) if g.get("guven") == "emin" and g.get("dogru") is False]
    if k.get("guven"):
        y += ["", "## Güven ve doğruluk (olgu soruları)", "",
              "Toplam %d olgu sorusu; emin ama yanlış: %d." % (len(k["guven"]), len(yanlis_emin))]
        for g in yanlis_emin:
            y.append("- %s: %s" % (g.get("hedef", ""), g.get("soru", "")))
    if k.get("sorular"):
        y += ["", "## Öğrencinin soruları (notta olmayanlar ve ilginç olanlar)", ""]
        for s in k["sorular"]:
            y.append("- %s%s" % (s.get("soru", ""), " — kaynakta yok" if s.get("kaynakta_yok") else ""))
    if k.get("testler"):
        y += ["", "## Ölçme testleri (pilot)", "",
              "| Tarih | Test | Form | Puan | Emin ama yanlış | Seçilen yanılgılar |", "| --- | --- | --- | --- | --- | --- |"]
        for t in k["testler"]:
            y.append("| %s | %s%s | %s | %s / %s | %s | %s |" % (
                t.get("tarih"), TEST_AD.get(t.get("tur"), t.get("tur")), " (yarım)" if t.get("yarim_kaldi") else "",
                t.get("form", "-"), t.get("puan", t.get("dogru")), t.get("toplam"),
                t.get("emin_ama_yanlis", "-"), ", ".join(t.get("secilen_yanilgilar") or []) or "-"))
    for baslik, alan in (("Öğrenme güçlükleri", "guclukler"), ("Eğitmen için iyileştirme önerileri", "oneriler"),
                         ("Öğrencinin geri bildirimi", "geri_bildirim")):
        if a.get(alan):
            y += ["", "## " + baslik, "", a[alan].strip()]
    y += ["", "---", "Eğitmenin kendi değerlendirmesi bağımsız bir ölçüm değildir. Kalıcılık ancak sonraki oturumlardaki "
          "yardımsız geri çağırmayla gösterilir."]
    klasor = os.path.join(ogrenci_klasoru(k["ogrenci"]), "raporlar")
    os.makedirs(klasor, exist_ok=True)
    yol = os.path.join(klasor, "%s_%s.md" % (ders, time.strftime("%Y-%m-%d_%H%M")))
    open(yol, "w", encoding="utf-8").write("\n".join(y) + "\n")
    return metin({"durum": "yazıldı", "dosya": os.path.relpath(yol, KOK),
                  "not": "Öğrenciye dosyanın yerini söyle; isterse öğretmenine kendisi gönderir."})


# ---------- Ölçme (pilot) ----------
TEST_AD = {"on": "Ön test", "son": "Son test", "gecikmeli": "Gecikmeli test"}

OLCME_TALIMAT = """Bu bir ölçme testi, ders değil. Eğitmen kurallarını test bitene kadar askıya al:
- İpucu, açıklama, doğru/yanlış bilgisi verme; öğrencinin cevabını yorumlama. "Bilmiyorum" geçerli bir cevaptır.
- Önce öğrenciye kısaca söyle: soru sayısı, yaklaşık 15 dakika, not için değil, sonuçlar ve doğru cevaplar sonda.
- Soruları sırayla, tek tek sor. Çoktan seçmeli soruda soru_sor'u 'dogru' ve 'aciklama' OLMADAN, verilen secenekler
  sırasıyla ve etiket ile çağır (ör. "Ön test · 3/12"). Dönen 'secim' değerini not al.
- Kısa yazılı soruda soruyu tahtaya yaz (tahta: title + text) ve öğrencinin cevabını sohbetten ya da dinle ile al.
  Puanı 'olcut'e göre sessizce ver (0, 1, 2); öğrenciye söyleme.
- Her sorudan sonra güveni sor: soru_sor ile secenekler ["Tahmin", "Biraz", "Emin"], etiket "Ne kadar eminsin?".
- Bütün sorular bitince olcme_kaydet'i çağır. Sonra puanı ve her yanlış sorunun doğru cevabını kısa, sakin bir dille
  göster; 'emin ama yanlış' olanları özellikle düzelt. Öğrenci testi yarıda bırakırsa yarim_kaldi=true ile kaydet.
- Test sonucu kayit_yaz'daki hedef düzeylerini değiştirmez; ölçme ile öğretim ayrı tutulur."""


def olcme(eg):
    o = (eg or {}).get("olcme") or {}
    return o if o.get("durum") == "onaylandi" and o.get("formlar") else None


def olcme_ozeti(eg):
    o = olcme(eg)
    if not o:
        return {"durum": ((eg or {}).get("olcme") or {}).get("durum", "yok"),
                "not": "Onaylı ölçme sorusu yok; test yapma."}
    return {"durum": "onaylandi", "plan": o.get("plan"), "puanlama": o.get("puanlama"),
            "soru_sayisi": {f: len(v) for f, v in o["formlar"].items()},
            "not": "Soruları burada görmüyorsun; testi olcme_testi aracıyla başlat."}


def olcme_sirasi(k, eg):
    o = olcme(eg)
    if not o:
        return None
    yapilan = {t.get("tur"): t for t in k.get("testler", []) if not t.get("yarim_kaldi")}
    if "on" not in yapilan:
        if k.get("oturumlar"):
            return {"oneri": None, "not": "Ön test yapılmadan derse başlanmış; ön test artık önerilmez."}
        return {"oneri": "on", "not": "İlk oturum: derse başlamadan önce isteğe bağlı ön testi öner (yaklaşık 15 dk). "
                                       "Öğrenci istemezse doğrudan derse geç."}
    if "son" not in yapilan:
        return {"oneri": None, "not": "Son test, öğrenci bütün hedefleri çalışıp dersi bitirdiğinde ya da kendisi "
                                       "isterse önerilir (olcme_testi tur=son)."}
    if "gecikmeli" not in yapilan:
        gun = int((o.get("plan") or {}).get("gecikmeli_en_erken_gun", 21))
        hazir = gun_ekle(yapilan["son"].get("tarih", bugun()), gun)
        if bugun() >= hazir:
            return {"oneri": "gecikmeli", "not": "Gecikmeli test zamanı geldi; oturumun başında, tekrar sorularından "
                                                  "ÖNCE öner."}
        return {"oneri": None, "not": "Gecikmeli test %s tarihinden itibaren yapılabilir." % hazir}
    return {"oneri": None, "not": "Üç test de tamamlandı."}


def karisik_sira(ogrenci, ders, tur, no, n):
    tohum = hashlib.sha256(("%s|%s|%s|%s" % (ogrenci.strip().lower(), ders, tur, no)).encode("utf-8")).hexdigest()
    sira = list(range(n))
    random.Random(int(tohum[:16], 16)).shuffle(sira)
    return sira


def test_formu(a):
    ders, ogr, tur = a.get("ders"), (a.get("ogrenci") or "").strip(), a.get("tur")
    if not ogr:
        raise ValueError("ogrenci gerekli")
    if tur not in TEST_AD:
        raise ValueError("tur: on, son ya da gecikmeli olmalı")
    eg = egitmen_json(ders)
    o = olcme(eg)
    if not o:
        raise ValueError("Bu derste öğretmenin onayladığı ölçme sorusu yok; test yapılamaz.")
    form = (o.get("plan") or {}).get(tur)
    if form not in o["formlar"]:
        raise ValueError("Bu test türü için form tanımlı değil: %s" % tur)
    return eg, o, form, ogr


def ar_olcme_testi(a):
    eg, o, form, ogr = test_formu(a)
    tur, ders = a["tur"], a["ders"]
    k = kayit_yukle(ogr, ders)
    uyari = []
    if any(t.get("tur") == tur and not t.get("yarim_kaldi") for t in k.get("testler", [])):
        uyari.append("Bu öğrenci %s testini daha önce tamamladı; tekrarı araştırmada ayrı sayılır." % TEST_AD[tur].lower())
    sira_onerisi = olcme_sirasi(k, eg) or {}
    if sira_onerisi.get("oneri") not in (None, tur):
        uyari.append("Sıradaki önerilen test: %s." % TEST_AD.get(sira_onerisi["oneri"]))
    sorular = []
    for i, s in enumerate(o["formlar"][form], 1):
        x = {"sira": "%d/%d" % (i, len(o["formlar"][form])), "no": s["no"], "hedef": s.get("hedef"),
             "tur": s["tur"], "soru": s["soru"]}
        if s["tur"] == "secmeli":
            sira = karisik_sira(ogr, ders, tur, s["no"], len(s["secenekler"]))
            x["secenekler"] = [s["secenekler"][j] for j in sira]
        else:
            x["olcut"] = s.get("olcut")
        sorular.append(x)
    out = {"test": TEST_AD[a["tur"]], "form": form, "soru_sayisi": len(sorular), "puanlama": o.get("puanlama"),
           "talimat": OLCME_TALIMAT, "sorular": sorular}
    if uyari:
        out["uyarilar"] = uyari
    return metin(out)


def ar_olcme_kaydet(a):
    eg, o, form, ogr = test_formu(a)
    tur, ders = a["tur"], a["ders"]
    sorular = {s["no"]: s for s in o["formlar"][form]}
    toplam = sum(1 if s["tur"] == "secmeli" else 2 for s in sorular.values())
    ayrinti, uyarilar, yanilgilar = [], [], []
    puan = emin_yanlis = 0
    for y in a.get("yanitlar") or []:
        s = sorular.get(y.get("no"))
        if not s:
            uyarilar.append("Bilinmeyen soru: %s" % y.get("no"))
            continue
        r = {"no": s["no"], "hedef": s.get("hedef"), "guven": y.get("guven")}
        if s["tur"] == "secmeli":
            sec = y.get("secim")
            if not isinstance(sec, int) or not 0 <= sec < len(s["secenekler"]):
                r.update(puan=0, cevap=None)
            else:
                asil = karisik_sira(ogr, ders, tur, s["no"], len(s["secenekler"]))[sec]
                r.update(puan=1 if asil == s["dogru"] else 0, cevap=s["secenekler"][asil])
                yid = (s.get("yanilgi_secenekleri") or {}).get(str(asil))
                if yid:
                    r["yanilgi"] = yid
                    yanilgilar.append(yid)
            r["dogru_cevap"] = s["secenekler"][s["dogru"]]
            tam = r["puan"] == 1
        else:
            p = y.get("puan")
            r.update(puan=p if p in (0, 1, 2) else 0, cevap=y.get("yanit_ozet"))
            tam = r["puan"] == 2
            if r["puan"] == 0 and s.get("yanilgi") and y.get("yanilgi_secildi"):
                yanilgilar.append(s["yanilgi"])
        if y.get("guven") == "emin" and not tam:
            r["emin_ama_yanlis"] = True
            emin_yanlis += 1
        puan += r["puan"]
        ayrinti.append(r)
    eksik = [n for n in sorular if n not in {r["no"] for r in ayrinti}]
    k = kayit_yukle(ogr, ders)
    kayit = {"tur": tur, "form": form, "tarih": bugun(), "saat": time.strftime("%H:%M"), "puan": puan,
             "toplam": toplam, "emin_ama_yanlis": emin_yanlis, "secilen_yanilgilar": sorted(set(yanilgilar)),
             "yarim_kaldi": bool(a.get("yarim_kaldi") or eksik), "yanitlar": ayrinti}
    if eksik:
        kayit["cevapsiz"] = eksik
    k.setdefault("testler", []).append(kayit)
    yol = kayit_kaydet(k)
    out = {"durum": "kaydedildi", "dosya": os.path.relpath(yol, KOK), "test": TEST_AD[tur], "puan": puan,
           "toplam": toplam, "emin_ama_yanlis": emin_yanlis, "secilen_yanilgilar": kayit["secilen_yanilgilar"],
           "yanlislar": [{"no": r["no"], "cevap": r.get("cevap"), "dogru_cevap": r.get("dogru_cevap"),
                          "olcut": sorular[r["no"]].get("olcut"), "emin_ama_yanlis": r.get("emin_ama_yanlis", False)}
                         for r in ayrinti if r["puan"] < (1 if sorular[r["no"]]["tur"] == "secmeli" else 2)],
           "not": "Şimdi öğrenciye puanı ve yanlışların doğru cevabını kısa ve sakin göster; emin ama yanlış olanları "
                  "özellikle düzelt. Sonra derse ya da molaya geç."}
    if eksik:
        out["cevapsiz"] = eksik
    if uyarilar:
        out["uyarilar"] = uyarilar
    return metin(out)


# ---------- Tahta ----------
def ar_tahtayi_ac(_):
    d = sunucu_acik()
    if not d:
        sunucuyu_baslat()
        for _ in range(30):
            time.sleep(0.5)
            d = sunucu_acik()
            if d:
                break
        if not d:
            return metin({"durum": "hata", "hata": "Yerel sunucu açılamadı. Bilgisayarda şunu çalıştırın: "
                                                    "python tools/sunucu.py --sayfa canli.html"}, hata=True)
    if not d.get("bagli"):
        webbrowser.open("http://localhost:%d/canli.html" % PORT)
        for _ in range(40):
            time.sleep(0.5)
            d = sunucu_acik() or {}
            if d.get("bagli"):
                break
    if not d.get("bagli"):
        return metin({"durum": "bekleniyor", "not": "Tarayıcıda canli.html açılıyor; birkaç saniye sonra tekrar dene."})
    return metin({"durum": "hazır", "tahta": d.get("sayfa"), "ses": d.get("ses"),
                  "not": "Tahta açık. Kullanıcı ilk açılışta sayfada 'başlat' düğmesine bir kez dokunmalı; "
                         "dokunmadıysa ses çalmaz ama yazılar görünür."})


def ar_tahta(a):
    adimlar = a.get("adimlar") or []
    if not isinstance(adimlar, list) or not adimlar:
        raise ValueError("adimlar boş")
    komut = {"tur": "adimlar", "adimlar": adimlar}
    if a.get("ders"):
        komut["ders"] = a["ders"]
    return metin(gonder(komut, a.get("bekle", True) is not False))


def ar_soru_sor(a):
    komut = {"tur": "soru", "soru": a.get("soru"), "secenekler": a.get("secenekler")}
    for k in ("dogru", "aciklama", "anlat", "etiket"):
        if a.get(k) is not None:
            komut[k] = a[k]
    return metin(gonder(komut))


def ar_tahta_durumu(a):
    if a.get("no"):
        try:
            return metin(istek("sonuc?no=%d&bekle=40" % int(a["no"]), zaman=70))
        except urllib.error.URLError:
            return metin({"durum": "bağlı değil"})
    return metin(sunucu_acik() or {"durum": "sunucu kapalı", "not": "tahtayi_ac ile aç."})


def ar_dinle(a):
    try:
        sure = max(5, min(int(a.get("bekle") or 40), 50))
    except (TypeError, ValueError):
        sure = 40
    try:
        return metin(istek("dinle?bekle=%d" % sure, zaman=sure + 20))
    except urllib.error.URLError:
        return metin({"durum": "bağlı değil", "hata": "Yerel tahta sunucusu kapalı. Önce tahtayi_ac aracını çağır."})


def ar_durdur(_):
    return metin(gonder({"tur": "dur"}, bekle=True))


ISLEYICILER = {"egitmen_hazirla": ar_egitmen_hazirla, "kayit_oku": ar_kayit_oku, "kayit_yaz": ar_kayit_yaz,
               "rapor_yaz": ar_rapor_yaz, "olcme_testi": ar_olcme_testi, "olcme_kaydet": ar_olcme_kaydet,
               "tahtayi_ac": ar_tahtayi_ac, "dersler": ar_dersler, "ders_oku": ar_ders_oku,
               "gorsel_bak": ar_gorsel_bak, "tahta": ar_tahta, "soru_sor": ar_soru_sor,
               "tahta_durumu": ar_tahta_durumu, "dinle": ar_dinle, "durdur": ar_durdur}


def metin(veri, hata=False):
    t = veri if isinstance(veri, str) else json.dumps(veri, ensure_ascii=False, indent=1)
    out = {"content": [{"type": "text", "text": t}]}
    if hata:
        out["isError"] = True
    return out


# ---------- MCP (JSON-RPC, satır satır stdin/stdout) ----------
def yaz(mesaj):
    sys.stdout.buffer.write(json.dumps(mesaj, ensure_ascii=False).encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()


def isle(m):
    yontem, no, p = m.get("method"), m.get("id"), m.get("params") or {}
    if no is None:
        return None  # bildirim: yanıt verilmez
    if yontem == "initialize":
        return {"protocolVersion": p.get("protocolVersion") or "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": AD, "title": "Akıllı Tahta", "version": SURUM},
                "instructions": TALIMAT}
    if yontem == "ping":
        return {}
    if yontem == "tools/list":
        return {"tools": ARACLAR}
    if yontem == "tools/call":
        f = ISLEYICILER.get(p.get("name"))
        if not f:
            raise LookupError("Bilinmeyen araç: %s" % p.get("name"))
        try:
            return f(p.get("arguments") or {})
        except Exception as e:
            return metin("Hata: %s" % e, hata=True)
    if yontem in ("resources/list", "prompts/list"):
        return {yontem.split("/")[0]: []}
    raise NotImplementedError(yontem)


def calis():
    while True:
        satir = sys.stdin.buffer.readline()
        if not satir:
            break
        satir = satir.strip()
        if not satir:
            continue
        try:
            m = json.loads(satir.decode("utf-8"))
        except Exception:
            yaz({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Geçersiz JSON"}})
            continue
        try:
            sonuc = isle(m)
            if m.get("id") is not None:
                yaz({"jsonrpc": "2.0", "id": m["id"], "result": sonuc})
        except NotImplementedError as e:
            yaz({"jsonrpc": "2.0", "id": m.get("id"), "error": {"code": -32601, "message": "Yöntem yok: %s" % e}})
        except Exception as e:
            yaz({"jsonrpc": "2.0", "id": m.get("id"), "error": {"code": -32603, "message": str(e)}})


# ---------- Claude masaüstü ayarı ----------
def ayar_dosyalari():
    yollar = []
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", "")
        yerel = os.environ.get("LOCALAPPDATA", "")
        # Microsoft Store / MSIX kurulumu ayarı paket klasöründe tutar.
        for p in glob.glob(os.path.join(yerel, "Packages", "Claude_*", "LocalCache", "Roaming", "Claude")):
            yollar.append(p)
        yollar.append(os.path.join(appdata, "Claude"))
    elif sys.platform == "darwin":
        yollar.append(os.path.expanduser("~/Library/Application Support/Claude"))
    else:
        yollar.append(os.path.expanduser("~/.config/Claude"))
    var = [p for p in yollar if os.path.isdir(p)]
    return [os.path.join(p, "claude_desktop_config.json") for p in (var or yollar[-1:])]


def kur(kaldir=False):
    for yol in ayar_dosyalari():
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        ayar = {}
        if os.path.exists(yol):
            try:
                ayar = json.load(open(yol, encoding="utf-8")) or {}
            except Exception:
                sys.exit("Ayar dosyası okunamadı (bozuk JSON?): %s\nDosyayı düzeltip yeniden deneyin." % yol)
            shutil.copy2(yol, yol + ".yedek")
        sunucular = ayar.setdefault("mcpServers", {})
        if kaldir:
            sunucular.pop(AD, None)
        else:
            sunucular[AD] = {"command": sys.executable, "args": [os.path.abspath(__file__)],
                             "env": {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}}
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(ayar, f, ensure_ascii=False, indent=2)
        print(("Kaldırıldı: " if kaldir else "Eklendi: ") + yol)
    if not kaldir:
        print("\nŞimdi Claude masaüstü uygulamasını TAMAMEN kapatın (saat yanındaki simgeye sağ tık → Quit/Çık)")
        print("ve yeniden açın. Sohbet kutusunun altındaki araçlar menüsünde 'akilli-tahta' görünmelidir.")
        print("Sonra Claude'a şunu yazın:  Tahtayı aç ve bana Şekil 2'yi anlat.")


def kendini_dene():
    """Kurulumdan sonra hızlı denetim: araç listesi ve ders dosyaları okunuyor mu?"""
    print("Python:", sys.executable)
    print("Klasör:", KOK)
    print("Dersler:", ", ".join(g["id"] for g in katalog()) or "yok")
    print("Araçlar:", ", ".join(a["name"] for a in ARACLAR))
    d = sunucu_acik()
    print("Yerel sunucu:", "açık, tahta " + ("bağlı" if d and d.get("bagli") else "bağlı değil") if d else "kapalı (Claude açacak)")


if __name__ == "__main__":
    if "--kur" in sys.argv:
        kur()
    elif "--kaldir" in sys.argv:
        kur(kaldir=True)
    elif "--dene" in sys.argv:
        kendini_dene()
    else:
        calis()
