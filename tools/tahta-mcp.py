#!/usr/bin/env python3
"""KlinikKoç için MCP sunucusu: Claude masaüstü uygulaması tahtayı canlı yönetir.

API anahtarı gerekmez. Claude, sizin aboneliğinizle masaüstü uygulamasında çalışır;
bu dosya ona tahtayı yönetecek araçlar verir (tahtayı aç, ders oku, şekle bak,
tahtaya yaz ve anlat, soru sor, durdur). Komutlar bu bilgisayardaki
tools/sunucu.py'ye, oradan tarayıcıdaki canli.html sayfasına gider.

Kurulum (bir kez):
  python tools/tahta-mcp.py --kur
  Sonra Claude masaüstü uygulamasını tamamen kapatıp (sistem tepsisinden "Quit") yeniden açın.

Kaldırma:
  python tools/tahta-mcp.py --kaldir

Claude ayar dosyasını bulamazsa (Ayarlar › Geliştirici › "Yapılandırmayı düzenle" ile açılan dosya):
  python tools/tahta-mcp.py --kur --ayar "<dosyanın yolu>"

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
import threading
import time
import urllib.error
import urllib.request
import webbrowser

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, "tools"))
import bilgi_bankasi  # noqa: E402
import karne as karne_  # noqa: E402
import kayit_aktar  # noqa: E402
import kayit_deposu as kd  # noqa: E402
import veri_yeri  # noqa: E402


def _metin_oku(yol):
    """Dosyayı okuyup hemen kapatır (açık kalan dosya Windows'ta kilitlenmeye yol açar)."""
    with open(yol, encoding="utf-8") as f:
        return f.read()


def _json_oku(yol):
    with open(yol, encoding="utf-8") as f:
        return json.load(f)


def _ikili_oku(yol):
    with open(yol, "rb") as f:
        return f.read()
PORT = int(os.environ.get("KLINIK_KOC_PORT", "8810"))
ADRES = "http://127.0.0.1:%d" % PORT
SURUM = "0.4.0"
AD = "klinik-koc"

TALIMAT = """KlinikKoç: bu bilgisayardaki tarayıcıda açık bir kara tahta. Bu araçlarla
tahtaya yazar, ders görsellerini gösterip işaretler ve Türkçe sesli anlatırsın (Pocket TTS Türkçe Kadın 3 sesi; hazır değilse Piper dfki).
Öğrenci kimliği: egitmen_hazirla'yı öğrencinin adı ve kısa bir ayırt ediciyle (öğrenci numarasının son 3 hanesi
ya da takma ad; ayirt alanı) çağır. Araç 'ayirt_gerekli' ya da 'ayni_ad_var' dönerse verdiği talimata uy
("Bu adla kayıt var, sen misin?"). Dönen kimliği sonraki bütün araçlarda ogrenci alanına yaz. Öğretmen
deniyorsa ogrenci='deneme' ya da deneme=true ver; deneme kayıtları araştırmaya katılmaz. Kayıtlar yalnız bu
bilgisayarda durur; kendiliğinden hiçbir yere gönderilmez (öğrenci isterse kayit_disa_aktar).
Eğitmen (İnci ya da Mercan): Bir dersi öğretmeye başlamadan önce egitmen_hazirla aracını çağır. O araç
dersin eğitmenini, öğretim kurallarını, hedeflerini, öğretmen notlarını ve öğrencinin kaydını verir; bütün
oturum boyunca o kurallara uy. Öğrencinin ilerlemesini kayit_yaz ile işle, bitişte rapor_yaz ile rapor yaz.
Bilgi bankası: Cevabından emin değilsen ya da öğrenci ders dışı görünen bir şey sorarsa önce bilgi_ara ile
dersin kaynaklarında, anlatımında, öğretmen notlarında ve vakalarında ara; bulduğun parçanın kaynağını (sayfa) söyle.
bilgi_ara sonucundaki dayanak alanına uy: "yok" ise kaynakta olmadığını söyle, "zayif" ise yalnız parçanın
açıkça söylediğini aktar.
Vakalar: Dersin vaka kartları varsa (vakalar aracı) vaka_oku ile bir vakayı aç ve dönen vaka kurallarına uy.
Her cevaplanan soruyu ve vaka adımını kayit_yaz'ın cevaplar alanına işle (Bloom düzeyi ve rubrik puanıyla);
öğrenci "karnem" derse karne aracını çağır.
Sözlü sınav provası için sozlu_prova, bütün derslerden zayıf konu tekrarı için tekrar_listesi aracını kullan.
Karar ağacı: vaka ya da ayırıcı tanı anlatırken tahtada tree komutuyla ağacı adım adım kur.
Pilot ölçme testleri (ön/son/gecikmeli) yalnız olcme_testi ve olcme_kaydet araçlarıyla, öğretmenin onayladığı
sorularla yapılır; test sırasında ipucu ve açıklama verilmez.
Nasıl çalış:
- İlk iş tahtayi_ac. Ders konusu varsa dersler ve ders_oku ile içeriği oku; şekli işaretleyeceksen
  önce gorsel_bak ile görseli gör (işaret koordinatları görselin 0–1 arası oranlarıdır).
- tahta aracında anlatımı 2–6 adıma böl. Her adımda önce tahta komutları, sonra o adımın anlatımı.
  Anlatım konuşma dilinde, kısa cümlelerle, ders kitabı Türkçesiyle olsun; madde başına en çok ~10 sözcük.
- Tahtada tek görsel alan vardır (image, table, flow, compare, draw, tree'den biri); yanında title, bullets,
  term, text notları durabilir. Yeni konuya geçerken {"type":"clear"} ile başla.
- Ders görselleri dışında görsel kullanma; kendi çizimin için draw komutunu kullan.
Video: Dersin videoları (klasördeki dosyalar ve öğretmenin eklediği YouTube bağlantıları) videolar aracıyla
  listelenir; tahtada video komutuyla gösterilir. Klasördeki video internetsiz oynar, YouTube internet ister.
  Videoyu kısa tut (baslangic/bitis ile 1–3 dk); önce ne izleneceğini bir cümleyle söyle, video bitince anlat.
  Kullanıcı sohbete ya da tahtaya bir YouTube bağlantısı verirse onu da youtube alanıyla oynatabilirsin.
- Bilgi dersin içeriğine dayansın; dersin dışına çıkarsan bunu açıkça söyle.
- Anlatım bitince sohbet penceresinde çok kısa özet ver; tahtada anlattığını sohbete tekrar yazma.
Sesli sohbet (dikte): Kullanıcı tahtadaki mikrofon tuşuna (ya da M tuşuna) basıp konuşabilir; söyledikleri
yazıya çevrilip sana gelir. Tanıyıcı (Duyu-small, bu bilgisayarda; yoksa tarayıcınınki) alan terimlerini
bozabilir; metin terim sözlüğünden geçer. 'ham_metin' alanı tanıyıcının ilk çıktısıdır: düzeltme yanlış
görünüyorsa ya da cümle anlamsızsa öğrenciye ne demek istediğini kısaca sor.
- Söz kesme: Anlatım sürerken kullanıcı konuşursa tahta anlatımı kaldığı yerde duraklatır ve bekleyen tahta /
  tahta_durumu(no) çağrın beklemeden {"durum": "kullanici_konustu", "kullanici_konustu": "..."} döner.
  Önce ona cevap ver: tahtada sesli (tahta aracı; cevap araya girer, tahta sonra eski hâline döner) ya da
  sohbette. Sonra anlatima_devam ile anlatımı kaldığı yerden sürdür; konu değiştiyse anlatima_devam(birak=true).
- Soru kartı açıkken konuşursa kart kapanır; gerekirse soruyu yeniden sor.
- tahta ya da soru_sor 'gonderilmedi: true' ile dönerse kullanıcının cevaplanmamış sözü vardır; önce ona cevap ver.
- Ders ya da sohbet sırasında bir bölümü/cevabı bitirince dinle aracını çağır; gelen metne tahtada sesli
  cevap ver (gerekirse çizerek), sonra yeniden dinle. "sessiz" dönerse bir-iki kez daha dinle; uzun
  sessizlikte döngüyü bırak ve sohbete kısa bir not yaz.
- Bir oturumda cevabını bitirmeden önce son iş olarak dinle çağır; kullanıcı sesli sohbetteyse dinleme
  döngüsünü sürdür. Sen dinlemezken söylenenler bekler; tahta sayfası kullanıcıya sohbete "tahtaya bak"
  yazmasını söyler. Kullanıcı "tahtaya bak" yazarsa tahta_durumu'nu (no'suz) çağır: bekleyen sözü döndürür.
  Kullanıcı sohbete "Tahtadan sesli soru: ..." yapıştırırsa bu da tahtada söylenmiş bir sözdür.
- tahta, soru_sor ve tahta_durumu sonuçlarında 'kullanici_konustu' alanı varsa kullanıcı o sırada
  konuşmuştur; önce ona cevap ver.
- Claude Code'da kanal açıksa (tahta-mcp.py --kanal) sen dinlemezken söylenenler sohbete <channel
  source="klinik-koc"> iletisi olarak düşer; ona da tahtada cevap ver.
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
                   "flow{title?,nodes[],direction?:row|column} | compare{title?,columns[{title,items?[],asset?,caption?,color?}]} "
                   "(asset verilen sütunda o ders görseli gösterilir: iki fotoğrafı yan yana karşılaştırmak için) | "
                   "draw{title?,viewBox?='0 0 160 90',shapes[{kind:line|arrow|rect|ellipse|path|text, ...}]} | "
                   "tree{title?,nodes[{id,text,parent?,edge?,state?:ok|warn|accent|danger|dim}],path?[id],caption?} "
                   "(klinik karar ağacı: kök düğümün parent'ı yok; edge dala yazılan koşuldur, ör. 'ateş var'; path öğrencinin "
                   "seçtiği yolu vurgular. Aynı title ile düğüm ekleyerek yeniden gönderirsen ağaç adım adım büyür). "
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
                   "Renkler: chalk, accent, warn, ok. Metinde **kalın** ve _italik_ kullanılabilir. "
                   "VIDEO: video{video?:videolar aracındaki kimlik | youtube?:bağlantı ya da kimlik, baslangic?:sn, "
                   "bitis?:sn, oynat?=true, bekle?=true, sessiz?, caption?} görsel alanını kaplar; bekle=true iken o adımın "
                   "anlatımı video bitince başlar (videonun üstüne konuşma); kısa klip için baslangic/bitis ver. "
                   "video_kontrol{eylem:oynat|duraklat|git, saniye?} tahtadaki videoyu yönetir.",
    "properties": {"type": {"type": "string", "enum": [
        "clear", "title", "bullets", "point", "text", "term", "image", "highlight", "unhighlight",
        "zoom", "unzoom", "table", "flow", "compare", "draw", "tree", "video", "video_kontrol"]}},
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
            "ogrenci": {"type": "string", "description": "öğrencinin adı (ya da daha önce dönen kimliği). Kayıt yalnız "
                                                         "bu bilgisayarda tutulur."},
            "ayirt": {"type": "string", "description": "kısa ayırt edici: öğrenci numarasının son 3 hanesi ya da takma ad"},
            "ogrenci_kimligi": {"type": "string", "description": "'Bu adla kayıt var, sen misin?' sorusuna evet denince "
                                                                 "o kaydın kimliği"},
            "yeni_ogrenci": {"type": "boolean", "description": "aynı adlı kayıt öğrencinin değilse true: ayrı kayıt açılır"},
            "deneme": {"type": "boolean", "description": "öğretmen denemesi: kayıt 'deneme' olarak işaretlenir, "
                                                         "araştırma aktarımına katılmaz"},
            "egitmen": {"type": "string", "enum": ["inci", "mercan"],
                        "description": "yalnız ders izin veriyorsa başka eğitmen seçmek için"}},
            "required": ["ders"]},
    },
    {
        "name": "kayit_yaz",
        "description": "Öğrencinin ilerlemesini bu bilgisayardaki kayda işler. Her anlamlı adımdan sonra çağır. "
                       "hedefler: [{id, duzey (hatirla|anla|uygula|cozumle|degerlendir|olustur), yardim (yardimsiz|destekle), "
                       "iskele (S0 yardımsız | S1 genel yönlendirme | S2 odaklı ipucu | S3 kısmi çözüm ya da seçenek daraltma | "
                       "S4 cevabı gösterip açıklama; cevaba ulaşılan basamak, isteğe bağlı), "
                       "dogru, solo (yapi_oncesi|tek|cok|iliskisel|genisletilmis), durum (ele_alinmadi|destekle_yapti|"
                       "bagimsiz_yapti|tekrar_gerekli), tur (yanit|geri_cagirma|uygulama), kanit (tek cümle)}]. "
                       "yanilgilar: [{id, durum (acik|cozuldu), not}]. guven: [{hedef, soru, guven (tahmin|biraz|emin), dogru}]. "
                       "sorular: [{soru, kaynakta_yok}]. testler: [{tur (on|son|gecikmeli), dogru, toplam}]. "
                       "cevaplar: her cevaplanan soru ve vaka adımı için [{soru (kimlik ya da kısa metin), hedef, bloom, "
                       "tur (secmeli|acik|sozlu|vaka_karar|vaka_acik|vaka_veri), puan, en_yuksek (rubrik toplamı; seçmelide 1), "
                       "ilk_deneme (true/false), ipucu (kullanılan ipucu sayısı), vaka, dugum, tehlikeli (true/false), "
                       "karsilanan_olcutler [ölçüt metni, kısa], eksik_olcutler [ölçüt metni, kısa]}]. "
                       "mod: once_anlat|once_yanitla. mola: bekleyen nokta metni ya da null. oturum: {egitmen, ozet}. "
                       "Aralıklı tekrar tarihleri otomatik hesaplanır.",
        "inputSchema": {"type": "object", "properties": {
            "ogrenci": {"type": "string"}, "ders": {"type": "string"},
            "hedefler": {"type": "array", "items": {"type": "object"}},
            "yanilgilar": {"type": "array", "items": {"type": "object"}},
            "guven": {"type": "array", "items": {"type": "object"}},
            "sorular": {"type": "array", "items": {"type": "object"}},
            "testler": {"type": "array", "items": {"type": "object"}},
            "cevaplar": {"type": "array", "items": {"type": "object"}},
            "vaka_sonucu": {"type": "object", "description": "vaka bitince: {vaka, sonuc (iyi|kabul|kotu|yarim), dugum_sayisi, yeniden_anlatilan_bolumler[]}"},
            "mod": {"type": "string"}, "mola": {"type": ["string", "null"]},
            "oturum": {"type": "object"}},
            "required": ["ogrenci", "ders"]},
    },
    {
        "name": "bilgi_ara",
        "description": "Bu bilgisayardaki derslerin kaynak metinlerinde (ders notu/makale sayfaları), hazır anlatımlarında, "
                       "sorularında, öğretmen notlarında ve vaka kartlarında arar. Sözcük araması her zaman açıktır; "
                       "anlam araması kuruluysa anlamca yakın parçaları da bulur. Her sonuçta kaynak (sayfa) bilgisi vardır. "
                       "Sonuçta 'dayanak' (guclu | zayif | yok) kaynakta bu soruya gerçekten dayanak olup olmadığını söyler.",
        "inputSchema": {"type": "object", "properties": {
            "sorgu": {"type": "string", "description": "aranacak soru ya da anahtar sözcükler (Türkçe)"},
            "ders": {"type": "string", "description": "yalnız bu derste ara (isteğe bağlı)"},
            "tur": {"type": "string", "enum": ["kaynak", "anlatim", "ogretmen_notu", "vaka", "soru"],
                    "description": "yalnız bu türde ara (isteğe bağlı)"},
            "k": {"type": "integer", "description": "en çok kaç sonuç (varsayılan 6, en çok 15)"}},
            "required": ["sorgu"]},
    },
    {
        "name": "vakalar",
        "description": "Bir dersin vaka kartlarını listeler (başlık, hedefler, süre, onay durumu). Tanıyı ele vermez.",
        "inputSchema": {"type": "object", "properties": {"ders": {"type": "string"}}, "required": ["ders"]},
    },
    {
        "name": "vaka_oku",
        "description": "Bir vaka kartını eğitmen için açar: bütün bulgular, karar düğümleri, doğru cevaplar, rubrikler, "
                       "örnek cevaplar ve takılınca dönülecek ders bölümleri, ayrıca vakanın nasıl yürütüleceğine dair kurallar. "
                       "Cevapları öğrenciye önceden gösterme.",
        "inputSchema": {"type": "object", "properties": {
            "ders": {"type": "string"}, "vaka": {"type": "string", "description": "vaka kimliği (vakalar aracından)"}},
            "required": ["ders", "vaka"]},
    },
    {
        "name": "sozlu_prova",
        "description": "Sözlü sınav provası hazırlar: dersin ve vakalarının açık uçlu sorularını (rubrik ve örnek cevapla), "
                       "öğrencinin zayıf ve tekrar zamanı gelen hedeflerine göre sıralı verir; sınav hocası gibi yürütme "
                       "kurallarını da verir. Öğrenci 'sözlü provası', 'sınav provası' derse çağır.",
        "inputSchema": {"type": "object", "properties": {
            "ders": {"type": "string"}, "ogrenci": {"type": "string"},
            "soru_sayisi": {"type": "integer", "description": "1–12, varsayılan 5"}},
            "required": ["ders"]},
    },
    {
        "name": "tekrar_listesi",
        "description": "Öğrencinin bütün derslerinden tekrar zamanı gelen, başarısı düşük kalan hedefleri ve açık yanılgıları "
                       "tek listede, en gecikmiş olandan başlayarak verir; tekrar oturumunun kurallarını da verir. "
                       "Öğrenci 'tekrar yapalım', 'zayıf konularım' derse ya da oturumun başında ders seçilmemişse çağır.",
        "inputSchema": {"type": "object", "properties": {"ogrenci": {"type": "string"}}, "required": ["ogrenci"]},
    },
    {
        "name": "karne",
        "description": "Öğrencinin karnesini hesaplar: hedef başına başarı, Bloom düzeyine göre başarı, soru başına güçlük, "
                       "rubrik puanları, vaka sonuçları, tehlikeli seçimler ve tekrar zamanı gelen hedefler. "
                       "yaz=true ise karneyi öğrencinin bilgisayarına Markdown dosyası olarak da yazar. Karne not için değil, "
                       "öğrencinin kendini geliştirmesi içindir; hiçbir yere gönderilmez.",
        "inputSchema": {"type": "object", "properties": {
            "ogrenci": {"type": "string"}, "ders": {"type": "string"}, "yaz": {"type": "boolean"}},
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
                       "bilgisayarında, kalıcı kayıt klasöründe <kimlik>/raporlar/). Hedef tablosu, yanılgılar, güven ve sorular kayıttan "
                       "otomatik gelir; sen ogretmen_ozeti (6–8 cümle) ve isteğe bağlı guclukler, oneriler, geri_bildirim yaz.",
        "inputSchema": {"type": "object", "properties": {
            "ogrenci": {"type": "string"}, "ders": {"type": "string"},
            "ogretmen_ozeti": {"type": "string"}, "guclukler": {"type": "string"},
            "oneriler": {"type": "string"}, "geri_bildirim": {"type": "string"}},
            "required": ["ogrenci", "ders", "ogretmen_ozeti"]},
    },
    {
        "name": "kayit_disa_aktar",
        "description": "Öğrencinin bu bilgisayardaki bütün kaydını (dersler, raporlar, karneler) TEK dosyaya yazar "
                       "(varsayılan: masaüstü). Öğrenci başka bilgisayarda çalışmak ya da kaydını saklamak isterse çağır. "
                       "Hiçbir yere göndermez.",
        "inputSchema": {"type": "object", "properties": {
            "ogrenci": {"type": "string"}, "cikti": {"type": "string", "description": "dosya ya da klasör yolu (isteğe bağlı)"}},
            "required": ["ogrenci"]},
    },
    {
        "name": "kayit_ice_aktar",
        "description": "kayit_disa_aktar ile yazılmış kayıt dosyasını bu bilgisayara alır. Buradaki kayıt daha yeniyse "
                       "ona dokunmaz (uzerine=true ile yazar; eski sürüm yedekte kalır).",
        "inputSchema": {"type": "object", "properties": {
            "dosya": {"type": "string", "description": "kayıt dosyasının tam yolu"}, "uzerine": {"type": "boolean"}},
            "required": ["dosya"]},
    },
    {
        "name": "kayit_anonim_aktar",
        "description": "YALNIZ ÖĞRETMEN İÇİN, öğretmen açıkça isterse: seçilen öğrencilerin (ya da hepsinin) kayıtlarını "
                       "kimlik bilgisi olmadan (ad, kimlik, ayırt edici ve serbest metin yok; rastgele kod; tarihler gün "
                       "farkı) tek araştırma dosyasına yazar. Deneme kayıtları varsayılan olarak dışarıda kalır.",
        "inputSchema": {"type": "object", "properties": {
            "ogrenciler": {"type": "array", "items": {"type": "string"}, "description": "kimlikler; boşsa hepsi"},
            "dosyalar": {"type": "array", "items": {"type": "string"},
                         "description": "öğrencilerin dışa aktardığı kayıt dosyaları (içe almadan anonimleştirilir)"},
            "deneme_dahil": {"type": "boolean"}, "cikti": {"type": "string"},
            "ham_yanitlar": {"type": "boolean", "description": "true: ölçme testlerindeki kısa yazılı cevapların ham "
                             "metnini de ekle (puanlayıcı uyumu çalışması için). Serbest metindir; dosyayı paylaşmadan "
                             "önce öğretmen okumalı."}}},
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
                       "puan (0, 1, 2), öğrencinin cevabı kelimesi kelimesine ham_yanit ve kısa yanit_ozet verilir. "
                       "Her soruda guven: tahmin|biraz|emin.",
        "inputSchema": {"type": "object", "properties": {
            "ders": {"type": "string"}, "ogrenci": {"type": "string"},
            "tur": {"type": "string", "enum": ["on", "son", "gecikmeli"]},
            "yanitlar": {"type": "array", "items": {"type": "object", "properties": {
                "no": {"type": "string"}, "secim": {"type": "integer"}, "puan": {"type": "integer"},
                "yanit_ozet": {"type": "string"},
                "ham_yanit": {"type": "string", "description": "kısa yazılı soruda öğrencinin cevabı, kelimesi kelimesine, "
                              "düzeltmeden ve özetlemeden (sonradan insan puanlamasıyla karşılaştırmak için)"},
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
                       "'duraklatildi' döner: hata değil, tahta_durumu ile beklemeyi sürdür. Kullanıcı konuşursa "
                       "anlatım duraklar ve araç hemen 'kullanici_konustu' döner: cevap ver, sonra anlatima_devam.",
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
                       "ve sonucunu döndürür; kullanıcı konuşursa beklemeden 'kullanici_konustu' döner. "
                       "'duraklatildi': kullanıcı anlatımı duraklattı; aynı no ile beklemeyi sürdür. no verilmezse "
                       "kullanıcının bekleyen sözünü de 'kullanici_konustu' alanında verir (kullanıcı 'tahtaya bak' derse).",
        "inputSchema": {"type": "object", "properties": {"no": {"type": "integer"}}},
    },
    {
        "name": "dinle",
        "description": "Kullanıcının tahtadaki mikrofon tuşuyla söylediğini bekler ve yazı olarak döndürür "
                       "(en çok ~40 sn). Kimse konuşmazsa 'sessiz' döner; yeniden çağırabilirsin. Sesli sohbet "
                       "döngüsü: anlat → dinle → cevapla → dinle. Dikteyle gelen sözde 'metin' terim sözlüğüyle "
                       "düzeltilmiştir, 'ham_metin' tanıyıcının ilk çıktısı, 'motor' duyu|tarayici|yazi.",
        "inputSchema": {"type": "object", "properties": {
            "bekle": {"type": "integer", "description": "en çok kaç saniye beklensin (5–50, varsayılan 40)"}}},
    },
    {
        "name": "videolar",
        "description": "Dersin videolarını listeler: ders klasöründeki videolar/ dosyaları (internetsiz oynar) ve dersin "
                       "egitmen.json/ders.json'unda tanımlı YouTube bağlantıları. Tahtada göstermek için tahta aracında "
                       "{type:'video', video:'<kimlik>'} kullan.",
        "inputSchema": {"type": "object", "properties": {"ders": {"type": "string"}}, "required": ["ders"]},
    },
    {
        "name": "anlatima_devam",
        "description": "Kullanıcı söz alınca duraklayan anlatımı, cevabından sonra kaldığı cümleden sürdürür (tahta cevaptan "
                       "önceki hâline döner) ve anlatımın bitmesini tahta gibi bekler. birak=true: anlatımı sürdürmez, bırakır.",
        "inputSchema": {"type": "object", "properties": {
            "birak": {"type": "boolean", "description": "anlatımı sürdürme, bırak (konu değiştiyse)"}}},
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
        girisler = _json_oku(yol).get("lessons", [])
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
    return _json_oku(yol) if os.path.exists(yol) else None


def ders_json(ders):
    """ders.json'u döndürür. Yalnız egitmen.json olan (canlı) derste ondan özet bir ders kurar."""
    yol = ders_yolu(ders, "ders.json")
    if os.path.exists(yol):
        return _json_oku(yol)
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
        out = {"sayfa": n, "kaynak": kay.get("baslik"), "metin": _metin_oku(yol),
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
    veri = base64.b64encode(_ikili_oku(yol)).decode("ascii")
    return {"content": [{"type": "image", "data": veri, "mimeType": tur}, {"type": "text", "text": bilgi}]}


# ---------- Eğitmen, öğrenci kaydı, rapor ----------
EGITMENLER = {"inci": "İnci (lisans)", "mercan": "Mercan (uzmanlık)"}
BLOOM = ["hatirla", "anla", "uygula", "cozumle", "degerlendir", "olustur"]
BLOOM_AD = dict(zip(BLOOM, ["hatırla", "anla", "uygula", "çözümle", "değerlendir", "oluştur"]))
DURUM_AD = {"ele_alinmadi": "ele alınmadı", "destekle_yapti": "destekle yaptı", "bagimsiz_yapti": "bağımsız yaptı",
            "tekrar_gerekli": "tekrar gerekli", "devam_ediyor": "devam ediyor"}
TEKRAR_GUN = {1: 1, 2: 3, 3: 7, 4: 21}  # Leitner kutusu → sonraki geri çağırmaya kadar gün
# İpucu merdiveni: öğrencinin cevaba hangi basamakta ulaştığı. S0 yardımsız; S1 genel yönlendirme ("neye bakmalısın?");
# S2 odaklı ipucu; S3 kısmi çözüm ya da seçenek daraltma; S4 cevabı gösterip açıklama.
ISKELE = ("S0", "S1", "S2", "S3", "S4")


def yeni_kutu(kutu, dogru, yardimsiz, iskele=None):
    """Leitner kutusu. iskele verilmezse eski kural: yardımsız doğru bir üst kutu, gerisi 1. kutu.
    iskele verilirse: S0 doğru bir üst kutu; S1 doğru kutuyu korur (sıfırlamaz); S2–S4 ya da yanlış 1. kutu."""
    kutu = kutu or 0
    if not dogru:
        return 1
    if iskele in ISKELE:
        if iskele == "S0":
            return min(4, kutu + 1)
        if iskele == "S1":
            return max(1, kutu)
        return 1
    return min(4, kutu + 1) if yardimsiz else 1
KAYIT_KOK = veri_yeri.kayit_kok()          # kalıcı yer; KLINIK_KOC_KAYIT önce gelir
ESKI_KAYIT_KOK = os.path.join(KOK, "kayitlar")  # eski sürümlerin yeri: ilk açılışta bir kez kopyalanır
_DEPO = None


def depo():
    global _DEPO
    if _DEPO is None or _DEPO.kok != os.path.abspath(KAYIT_KOK):
        _DEPO = kd.Depo(KAYIT_KOK, None if veri_yeri.kayit_ortamdan_mi() else ESKI_KAYIT_KOK)
    return _DEPO


def bugun():
    return time.strftime("%Y-%m-%d")


def gun_ekle(tarih, gun):
    t = time.mktime(time.strptime(tarih, "%Y-%m-%d")) + gun * 86400 + 3600
    return time.strftime("%Y-%m-%d", time.localtime(t))


def ogrenci_kimligi(ogrenci):
    """Araçların ogrenci alanı (kimlik ya da ad) → kalıcı kimlik. Eski ada göre kayıtlar aynen bulunur."""
    return depo().coz(ogrenci)


def ogrenci_klasoru(ogrenci):
    return depo().klasor(ogrenci_kimligi(ogrenci))


def kayit_yolu(ogrenci, ders):
    ders_yolu(ders)  # kimlik denetimi
    return depo().kayit_yolu(ogrenci_kimligi(ogrenci), ders)


def kayit_yukle(ogrenci, ders):
    ders_yolu(ders)  # kimlik denetimi
    d = depo()
    kimlik = d.coz(ogrenci)
    k, uyarilar = d.yukle(kimlik, ders)
    if k is None:
        bilgi = d.defter()["ogrenciler"].get(kimlik) or {}
        k = {"ogrenci": bilgi.get("ad") or (ogrenci or "").strip(), "ders": ders, "olusturma": bugun(),
             "mod": "once_anlat", "hedefler": {}, "yanilgilar": {}, "guven": [], "sorular": [], "testler": [],
             "oturumlar": [], "mola": None, "cevaplar": [], "vakalar": []}
        if bilgi.get("ayirt"):
            k["tohum"] = kimlik  # ölçme testinde seçenek sırası bu kimliğe bağlı kalır
    k["ogrenci_kimligi"] = kimlik
    if d.deneme_mi(kimlik) or kd.deneme_adi_mi(k.get("ogrenci")):
        k["deneme"] = True
    k["_kimlik"] = kimlik
    if uyarilar:
        k["_uyarilar"] = uyarilar
    return k


def kayit_kaydet(k):
    kimlik = k.get("_kimlik") or k.get("ogrenci_kimligi") or depo().coz(k["ogrenci"])
    return depo().yaz(kimlik, k["ders"], k)


def kayit_temiz(k):
    return {a: v for a, v in k.items() if not a.startswith("_")}


def uyari_ekle(out, k):
    if k.get("_uyarilar"):
        out.setdefault("uyarilar", [])
        out["uyarilar"] = k["_uyarilar"] + out["uyarilar"]
    return out


def tohum(k):
    return k.get("tohum") or (k.get("ogrenci") or "")


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


OGRENCI_TALIMAT = ("Sonraki bütün araçlarda (kayit_yaz, kayit_oku, karne, rapor_yaz, olcme_..., tekrar_listesi, "
                   "sozlu_prova) ogrenci alanına bu kimliği yaz: %s")


def ogrenci_sec(a):
    """egitmen_hazirla için öğrenciyi bulur ya da açar. (kimlik, None) ya da (None, sorulacak durum)."""
    d = depo()
    d.hazirla()
    ad = (a.get("ogrenci") or "").strip()
    ayirt = (a.get("ayirt") or "").strip()
    deneme = bool(a.get("deneme")) or kd.deneme_adi_mi(ad)
    defter = d.defter()["ogrenciler"]
    kim = (a.get("ogrenci_kimligi") or "").strip()
    if not kim and ad in defter and defter[ad].get("ayirt"):
        kim = ad  # ogrenci alanına zaten kimlik yazılmış
    if kim:
        if not d.var_mi(kim):
            raise kd.KayitHatasi("Bu kimlikle kayıt yok: %s" % kim)
        if not (defter.get(kim) or {}).get("ayirt") or deneme:
            d.eskiyi_bagla(kim, ayirt or None, deneme)
        return kim, None
    if not ad:
        return None, {"durum": "ad_gerekli",
                      "talimat": "Öğrenciye bir kez adını ve kısa bir ayırt ediciyi (öğrenci numarasının son 3 hanesi "
                                 "ya da kendi seçtiği bir takma ad) sor; sonra egitmen_hazirla'yı ogrenci ve ayirt ile "
                                 "yeniden çağır. Öğretmen deniyorsa ogrenci='deneme' ya da deneme=true ver."}
    if deneme:
        return d.kimlik_olustur(ad, ayirt or "ogretmen", deneme=True), None
    adaylar = d.adaylar(ad)
    if ayirt:
        for x in adaylar:
            if x.get("ayirt") and kd.kisalt(x["ayirt"]) == kd.kisalt(ayirt):
                return x["kimlik"], None
        if not adaylar or a.get("yeni_ogrenci"):
            return d.kimlik_olustur(ad, ayirt), None
    elif not adaylar:
        return None, {"durum": "ayirt_gerekli",
                      "talimat": "Bu adla kayıt yok; ilk giriş. Öğrenciye kısa bir ayırt edici sor: öğrenci numarasının "
                                 "son 3 hanesi ya da kendi seçeceği bir takma ad (aynı adlı başka öğrenciyle karışmasın "
                                 "diye). Sonra egitmen_hazirla'yı ogrenci ve ayirt ile yeniden çağır."}
    return None, {"durum": "ayni_ad_var", "soru": "Bu adla kayıt var, sen misin?",
                  "kayitlar": [{"kimlik": x["kimlik"], "dersler": x["dersler"], "son_calisma": x["son_calisma"],
                                "eski_kayit": x["eski"]} for x in adaylar],
                  "talimat": "Öğrenciye 'Bu adla kayıt var, sen misin?' diye sor (kaydın derslerini ve son çalışma "
                             "tarihini söyleyebilirsin). Evet derse egitmen_hazirla'yı ogrenci_kimligi=<kimlik> ile "
                             "çağır (eski kayıtsa ayirt'ı da ver, kayıt ona bağlanır). Hayır derse ayirt ve "
                             "yeni_ogrenci=true ile çağır; yeni ve ayrı bir kayıt açılır."}


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
    kurallar = _metin_oku(os.path.join(KOK, "egitmenler", "ortak.md")) + "\n\n" + \
        _metin_oku(os.path.join(KOK, "egitmenler", secilen + ".md"))
    out = {"egitmen": EGITMENLER[secilen], "izinli_egitmenler": [EGITMENLER.get(x, x) for x in izinli],
           "kurallar": kurallar,
           "ders": {"kimlik": ders, "baslik": eg.get("baslik") or d.get("title"), "duzey": eg.get("duzey"),
                    "kaynak": eg.get("kaynak") or d.get("source"), "hedefler": eg.get("hedefler"),
                    "ogretmen_notlari": eg.get("ogretmenNotlari"), "bilinen_yanilgilar": eg.get("yanilgilar"),
                    "oturumlar": eg.get("oturumlar"), "arac_seti": eg.get("aracSeti"), "olcme": olcme_ozeti(eg),
                    "gorseller": {k: v.get("aciklama") for k, v in (eg.get("gorseller") or {}).items()}
                    or {k: v.get("caption") for k, v in (d.get("assets") or {}).items()},
                    "hazir_anlatim_bolumleri": [s["id"] for s in d.get("sections", [])],
                    "vakalar": [os.path.splitext(os.path.basename(y))[0]
                                for y in sorted(glob.glob(ders_yolu(ders, "vakalar", "*.json")))]},
           "bloom_sirasi": BLOOM}
    if not_:
        out["not"] = not_
    kimlik, soru = ogrenci_sec(a)
    if kimlik:
        k = kayit_yukle(kimlik, ders)
        out["ogrenci"] = {"ad": k["ogrenci"], "kimlik": kimlik, "kayit": kayit_ozeti(k, eg),
                          "ilk_oturum": not k.get("oturumlar"), "olcme_sirasi": olcme_sirasi(k, eg),
                          "kayit_klasoru": depo().klasor(kimlik), "not": OGRENCI_TALIMAT % kimlik}
        if k.get("deneme"):
            out["ogrenci"]["deneme"] = True
            out["ogrenci"]["deneme_notu"] = ("Öğretmen deneme kaydı: karnede ve araştırma dışa aktarımında ayrı "
                                             "işaretlenir, anonim aktarıma katılmaz.")
        uyari_ekle(out["ogrenci"], k)
    else:
        out["ogrenci"] = soru
    if depo().tasima_raporu and not getattr(depo(), "_tasima_soylendi", False):
        r = depo().tasima_raporu
        depo()._tasima_soylendi = True
        out["kayit_tasima"] = {"not": "Eski kayıtlar kalıcı kayıt klasörüne kopyalandı; eski dosyalar silinmedi.",
                               "kaynak": r["kaynak"], "yeni_yer": depo().kok, "kopyalanan": r["kopyalanan"]}
    return metin(out)


def ar_kayit_oku(a):
    k = kayit_yukle(a.get("ogrenci"), a.get("ders"))
    eg = egitmen_json(a.get("ders"))
    out = kayit_ozeti(k, eg)
    out["ogrenci_kimligi"] = k["_kimlik"]
    if k.get("deneme"):
        out["deneme"] = True
    if a.get("ayrinti"):
        out["kayit"] = kayit_temiz(k)
    return metin(uyari_ekle(out, k))


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
        iskele = g.get("iskele")
        if iskele is not None and iskele not in ISKELE:
            uyarilar.append("Geçersiz iskele basamağı: %s (S0–S4 olmalı)" % iskele)
            iskele = None
        if iskele and not g.get("yardim"):
            g["yardim"] = "yardimsiz" if iskele == "S0" else "destekle"
        elif iskele and (iskele == "S0") != (g.get("yardim") == "yardimsiz"):
            uyarilar.append("%s: yardim (%s) ile iskele (%s) uyuşmuyor; iskele esas alındı" % (hid, g.get("yardim"), iskele))
            g["yardim"] = "yardimsiz" if iskele == "S0" else "destekle"
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
            # Aralıklı tekrar: yardımsız başarı bir üst kutu; yalnız genel yönlendirmeyle (S1) başarı kutuyu korur;
            # başarısızlık ya da daha fazla yardım 1. kutu.
            v["kutu"] = yeni_kutu(v.get("kutu", 0), g.get("dogru", True), yardimsiz, iskele)
            v["sonraki_tekrar"] = gun_ekle(b, TEKRAR_GUN[v["kutu"]])
        v["son"] = b
        if g.get("kanit"):
            v["kanitlar"] = (v.get("kanitlar") or [])[-9:] + [
                {"tarih": b, "tur": g.get("tur", "yanit"), "duzey": duzey, "yardim": g.get("yardim"),
                 **({"iskele": iskele} if iskele else {}), "solo": g.get("solo"), "dogru": g.get("dogru"), "ozet": g["kanit"]}]
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
    for c in a.get("cevaplar") or []:
        c = dict(c, tarih=b, saat=time.strftime("%H:%M"))
        if c.get("bloom") and c["bloom"] not in BLOOM:
            uyarilar.append("Geçersiz Bloom düzeyi: %s" % c["bloom"])
            c.pop("bloom")
        try:
            c["puan"] = float(c.get("puan", 1 if c.get("dogru") else 0))
            c["en_yuksek"] = float(c.get("en_yuksek") or 1)
        except (TypeError, ValueError):
            uyarilar.append("Cevap puanı sayı olmalı: %s" % c.get("soru"))
            continue
        k.setdefault("cevaplar", []).append(c)
    if a.get("vaka_sonucu"):
        k.setdefault("vakalar", []).append(dict(a["vaka_sonucu"], tarih=b))
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
    out = {"durum": "kaydedildi", "dosya": yol, "ozet": kayit_ozeti(k, eg)}
    if uyarilar:
        out["uyarilar"] = uyarilar
    return metin(uyari_ekle(out, k))


def ar_rapor_yaz(a):
    ders = a.get("ders")
    k = kayit_yukle(a.get("ogrenci"), ders)
    eg = egitmen_json(ders) or {}
    hed = {x["id"]: x for x in eg.get("hedefler", [])}
    y = ["# Çalışma raporu — %s" % (eg.get("baslik") or ders), "",
         "Öğrenci: %s · Tarih: %s · Eğitmen: %s · Oturum sayısı: %d" % (
             k["ogrenci"], bugun(), EGITMENLER.get(eg.get("egitmen"), "-"), len(k.get("oturumlar", []))),
         "", "Bu rapor not için değildir. Öğrencinin bilgisayarında üretildi; otomatik gönderilmedi.", ""]
    if k.get("deneme"):
        y += ["> **DENEME KAYDI:** öğretmen denemesidir; araştırma verisine katılmaz.", ""]
    y += [
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
    if k.get("cevaplar"):
        kr = karne_.hesapla(k, karne_.ders_hedefleri(ders_yolu(ders)), bugun())
        y += ["", "## Bloom düzeyine göre başarı", "", "| Düzey | Cevap | Başarı |", "| --- | --- | --- |"]
        y += ["| %s | %d | %s |" % (karne_.BLOOM_AD[b["duzey"]], b["cevap"], karne_.yuzde(b["oran"])) for b in kr["bloom"]]
        if kr["tehlikeli_secimler"]:
            y += ["", "Vakalarda hastaya zarar verebilecek seçim sayısı: %d" % len(kr["tehlikeli_secimler"])]
    for baslik, alan in (("Öğrenme güçlükleri", "guclukler"), ("Eğitmen için iyileştirme önerileri", "oneriler"),
                         ("Öğrencinin geri bildirimi", "geri_bildirim")):
        if a.get(alan):
            y += ["", "## " + baslik, "", a[alan].strip()]
    y += ["", "---", "Eğitmenin kendi değerlendirmesi bağımsız bir ölçüm değildir. Kalıcılık ancak sonraki oturumlardaki "
          "yardımsız geri çağırmayla gösterilir."]
    yol = depo().metin_yaz(k["_kimlik"], "raporlar", "%s_%s.md" % (ders, time.strftime("%Y-%m-%d_%H%M")),
                           "\n".join(y) + "\n")
    return metin(uyari_ekle({"durum": "yazıldı", "dosya": yol,
                             "not": "Öğrenciye dosyanın yerini söyle; isterse öğretmenine kendisi gönderir."}, k))


# ---------- Bilgi bankası ----------
_MODEL = None


def anlam_modeli():
    global _MODEL
    if _MODEL is None:
        try:
            _MODEL = bilgi_bankasi.AnlamModeli()
        except Exception as e:  # model bozuksa sözcük aramasıyla sürdür
            _MODEL = type("Yok", (), {"hazir": False, "neden": str(e)})()
    return _MODEL


def ar_bilgi_ara(a):
    sorgu = (a.get("sorgu") or "").strip()
    if not sorgu:
        raise ValueError("sorgu gerekli")
    if a.get("ders"):
        ders_yolu(a["ders"])
    model = anlam_modeli()
    # Değişen dersler her aramadan önce yeniden dizinlenir (değişmeyenler saniyenin altında atlanır).
    bilgi_bankasi.dizinle(model=model, sessiz=True)
    k = max(1, min(int(a.get("k") or 6), 15))
    sonuclar, oz = bilgi_bankasi.ara_ve_dayanak(sorgu, a.get("ders"), a.get("tur"), k, model=model)
    out = {"sorgu": sorgu, "anlam_aramasi": "açık" if model.hazir else "kapalı (yalnız sözcük araması)",
           "dayanak": oz["dayanak"]}
    if DAYANAK_TALIMAT.get(oz["dayanak"]):
        out["talimat"] = DAYANAK_TALIMAT[oz["dayanak"]]
    out["dayanak_olcumu"] = {x: oz[x] for x in ("en_iyi_benzerlik", "en_iyi_kapsam", "sozcuk_eslesen_sayi")}
    out["sonuclar"] = sonuclar
    if not sonuclar:
        out["not"] = "Sonuç yok. Başka sözcüklerle ya da daha kısa bir sorguyla dene; yine yoksa 'kaynaklarda bulamadım' de."
    return metin(out)


DAYANAK_TALIMAT = {
    "yok": "Kaynakta bu soruya dayanak bulunamadı. Ders dışı bilgi verme; ortak kurallar §1'i uygula "
           "(\"Bu sorunun cevabı ders kaynağında yer almıyor.\"). Sorgu çok kısa ya da farklı sözcüklerle yazıldıysa "
           "bir kez başka sözcüklerle yeniden arayabilirsin.",
    "zayif": "Dayanak zayıf. Yalnız parçanın açıkça söylediğini aktar; kalanını 'kaynakta yok' diye ayır.",
}


# ---------- Vakalar ----------
VAKA_TALIMAT = """Vakayı şöyle yürüt (vaka bir sınav değil, klinik akıl yürütme alıştırmasıdır):
- Önce hastayı tanıt: yaş aralığı, şikâyet (hastanın sözleriyle), öykü ve 'acilis: baslangic' bulguları. Başlığı,
  tanıyı ve doğru seçenekleri söyleme. Vaka kurgusalsa bir kez "kurgusal vaka" de; öğretmen onayı yoksa "taslak".
- Düğümleri baslangic'tan başlayarak sırayla aç. Her düğümde önce 'anlat', sonra 'soru'.
- veri düğümü: Öğrenci hangi muayeneyi isterse yalnız o bulguyu ver. gerekli_bulgular'ın hepsi istenmeden geçme;
  eksik kalan için önce ipucu ver. İstenmeyen bulguyu kendiliğinden söyleme.
- karar düğümü: Seçenekleri soru_sor ile tahtada göster, 'dogru' alanını VERME (geri bildirimi sen vereceksin).
  Seçimden sonra o seçeneğin geribildirim'ini söyle. sonuc dogru ise (gerekce_iste false değilse) "Neden?" diye
  gerekçesini iste. yanlis ise sıradaki ipucunu ver ve aynı düğümde yeniden sor. tehlikeli ise nedenini sakin ve
  açık söyle; hastaya ne olacağını anlat. kabul ise neden en iyi seçenek olmadığını söyle ve sonraki'ye geç.
- acik düğümü: Öğrencinin cevabını rubrik ölçütlerine göre sessizce puanla. Sonra hangi ölçütleri karşıladığını
  (adıyla) ve eksik kalanları söyle, ardından ornek_cevap'ı "Öğretmenin örnek cevabı" diye göster (tahtada text).
  Zorunlu ölçüt eksikse bir kez daha denemesini iste.
- Takılma: Aynı düğümde iki denemede ilerleyemezse ya da "bilmiyorum" derse vakayı beklet: "Bunu birlikte
  hatırlayalım" de, takilirsa.bolum'u ders_oku ile oku ve o bölümü 2–4 adımda tahtada kısaca yeniden anlat
  (takilirsa.not'a odaklan). Sonra aynı düğüme dön ve soruyu küçültüp yeniden sor.
- Her cevaptan sonra kayit_yaz ile cevaplar listesine işle: soru (düğüm başlığı), vaka, dugum, hedef, bloom, tur
  (vaka_karar|vaka_acik|vaka_veri), puan, en_yuksek (karar: 1, acik: rubrik toplamı, veri: gerekli bulgu sayısı),
  ilk_deneme, ipucu, tehlikeli, karsilanan_olcutler, eksik_olcutler.
- son düğümünde 'anlat'ı söyle, kapanis.ozet ve ogrenme_noktalari ile toparla, kayit_yaz'a vaka_sonucu yaz
  (yeniden_anlatilan_bolumler dahil).
- Kapanışta bir "Ya şöyle olsaydı?" sorusu sor: vakanın tek bir bulgusunu değiştir (ör. "ateş de olsaydı",
  "lezyon dişetiyle sınırlı kalsaydı") ve tanının ya da tedavinin nasıl değişeceğini sor. Değiştirdiğin bulgu, ders
  kaynağında ya da vaka kartında tabloları birbirinden ayıran bir bulgu olarak geçmeli; kaynakta olmayan senaryo
  kurma. Bir soru yeter; cevabı kayit_yaz içinde uygulama türüyle işle.
- Sonra karnesini görmek isteyip istemediğini sor.
- Görseli göstermeden önce gorsel_bak ile bak; gorsel_aciklama'nın ötesinde yorum yapma."""


def vaka_yolu(ders, vaka):
    if not vaka or any(c in vaka for c in "/\\.") or vaka.startswith("_"):
        raise ValueError("Geçersiz vaka kimliği")
    return ders_yolu(ders, "vakalar", vaka + ".json")


def ar_vakalar(a):
    ders = a.get("ders")
    out = []
    for yol in sorted(glob.glob(ders_yolu(ders, "vakalar", "*.json"))):
        try:
            v = _json_oku(yol)
        except ValueError:
            out.append({"vaka": os.path.basename(yol), "hata": "okunamadı"})
            continue
        out.append({"vaka": v.get("id"), "baslik": v.get("baslik"), "duzey": v.get("duzey"), "sure_dk": v.get("sure_dk"),
                    "hedefler": v.get("hedefler"), "kurgusal": v.get("kurgusal"),
                    "ogretmen_onayi": bool((v.get("ogretmen_onayi") or {}).get("onaylandi"))})
    return metin({"ders": ders, "vakalar": out} if out else {"ders": ders, "vakalar": [], "not": "Bu derste vaka kartı yok."})


def ar_vaka_oku(a):
    import vaka_denetle
    yol = vaka_yolu(a.get("ders"), a.get("vaka"))
    if not os.path.exists(yol):
        raise ValueError("Vaka yok. vakalar aracıyla listeye bak.")
    hatalar, uyarilar, v = vaka_denetle.denetle(yol)
    if hatalar:
        return metin({"durum": "kullanılamaz", "hatalar": hatalar,
                      "not": "Bu vaka kartında hata var; öğrenciye açma. Öğretmen tools/vaka_denetle.py ile düzeltmeli."}, hata=True)
    return metin({"talimat": VAKA_TALIMAT, "vaka": v, "uyarilar": uyarilar or None})


def ar_karne(a):
    ders = a.get("ders")
    k = kayit_yukle(a.get("ogrenci"), ders)
    hedefler = karne_.ders_hedefleri(ders_yolu(ders))
    sonuc = karne_.hesapla(k, hedefler, bugun())
    out = {"karne": sonuc}
    if a.get("yaz"):
        d = egitmen_json(ders) or {}
        baslik = d.get("baslik") or ders_json(ders).get("title")
        out["dosya"] = depo().metin_yaz(k["_kimlik"], "karneler", "%s_%s.md" % (ders, time.strftime("%Y-%m-%d_%H%M")),
                                        karne_.markdown(sonuc, baslik, bugun()))
    out["not"] = ("Öğrenciye karnenin özetini 3–5 cümleyle, cesaretlendirici ve somut söyle: en güçlü hedef, "
                  "geliştirilecek hedef ve bir sonraki adım. Puanı not gibi sunma. İstersen tahtada table ile göster.")
    return metin(uyari_ekle(out, k))


# ---------- Sözlü sınav provası ----------
SOZLU_TALIMAT = """Bu bir sözlü sınav provası. Sen sınav hocasısın; sakin, saygılı ve kısa konuş. Not vermezsin.
- Başta söyle: kaç soru soracağını, her soruda önce sesli düşünmesinin serbest olduğunu, sonunda ayrıntılı
  geri bildirim vereceğini. Sınav sırasında ders anlatma, ipucu verme, cevabı onaylama ya da düzeltme.
- Soruyu tahtaya yaz (tahta: title + text) ve sesli sor; cevabı dinle aracıyla al. Sessiz kalırsa bir kez
  "Acele etme, aklına gelenden başla." de; ikinci sessizlikte bir sonraki soruya geç ve bunu not al.
- Cevap kısa kalırsa gerçek sınavdaki gibi en çok bir izleme sorusu sor ("Neden?", "Ayırıcı tanıda ne düşünürsün?",
  "Bu hastada bunu hangi bulguya dayanarak söylüyorsun?"). İzleme sorusu yeni bilgi vermemeli.
- Her cevabı sessizce rubrikle puanla (rubrik yoksa hedefin Bloom düzeyine göre 0–2). Hazır soru azsa hedefler
  listesinden, hedefin Bloom düzeyinde yeni soru kur; bilgisini ders_oku ya da bilgi_ara ile dersten al ve
  bu soruların senin kurduğun soru olduğunu kayda geçir (soru metninin başına "[eğitmen]" yaz).
- Bütün sorular bitince sınav tarzı geri bildirim ver, her soru için üç kısa satır: ne iyiydi, neyi eksik bıraktı
  (rubrik ölçütüyle), sınavda nasıl daha iyi söylenirdi (yapı: tanım → bulgu → karar → gerekçe; terimi doğru kullan).
  Sonra genel izlenim: akıl yürütmenin düzeni, terim kullanımı, kendinden eminlik. En önemli tek öneriyi söyle.
- Her cevabı kayit_yaz'ın cevaplar alanına tur "sozlu" ile işle (soru, hedef, bloom, puan, en_yuksek,
  karsilanan_olcutler, eksik_olcutler, ilk_deneme: true). Hedef düzeyini (gozlemler) yalnız yardımsız ve
  yeterli cevaplarda yükselt. Bitince öğrenci isterse karne aracını çağır."""


def ar_sozlu_prova(a):
    ders = a.get("ders")
    n = max(1, min(int(a.get("soru_sayisi") or 5), 12))
    d = ders_json(ders)
    eg = egitmen_json(ders) or {}
    hedefler = karne_.ders_hedefleri(ders_yolu(ders))
    oncelik = []
    if a.get("ogrenci"):
        k = kayit_yukle(a.get("ogrenci"), ders)
        kr = karne_.hesapla(k, hedefler, bugun())
        oncelik = list(dict.fromkeys(kr["gelistirilecek"] + kr["tekrar_zamani_gelen"] + kr["yoklanmayan"]))
    maddeler = []
    for sec in d.get("sections", []):
        for st in sec.get("steps", []):
            q = st.get("question") or {}
            if q.get("type") == "open":
                maddeler.append({"kaynak": "ders", "bolum": sec.get("id"), "soru": q.get("prompt"), "hedef": q.get("goal"),
                                 "bloom": q.get("bloom"), "rubrik": q.get("rubric"), "ornek_cevap": q.get("modelAnswer")})
    for yol in sorted(glob.glob(ders_yolu(ders, "vakalar", "*.json"))):
        try:
            v = _json_oku(yol)
        except ValueError:
            continue
        for nd in v.get("dugumler", []):
            if nd.get("tur") == "acik":
                maddeler.append({"kaynak": "vaka", "vaka": v.get("id"), "vaka_ozeti": (v.get("basvuru") or {}).get("sikayet"),
                                 "soru": nd.get("soru"), "hedef": nd.get("hedef"), "bloom": nd.get("bloom"),
                                 "rubrik": nd.get("rubrik"), "ornek_cevap": nd.get("ornek_cevap")})
    sira = {h: i for i, h in enumerate(oncelik)}
    maddeler.sort(key=lambda m: (sira.get(m.get("hedef"), len(sira)),
                                 -BLOOM.index(m["bloom"]) if m.get("bloom") in BLOOM else 0))
    secilen = maddeler[:n]
    return metin({"talimat": SOZLU_TALIMAT, "ders": ders, "soru_sayisi": n, "hazir_sorular": secilen,
                  "eksik_soru": max(0, n - len(secilen)),
                  "oncelikli_hedefler": oncelik[:8],
                  "hedefler": [{"id": h["id"], "baslik": h.get("baslik"), "bloom": h.get("bloom")} for h in hedefler],
                  "ogretmen_notlari": eg.get("ogretmenNotlari")})


# ---------- Dersler arası tekrar ----------
TEKRAR_TALIMAT = """Bu bir tekrar oturumu: öğrencinin bütün derslerinden, zamanı gelen ve zayıf kalan hedefler.
- Listenin başından başla; bir oturumda en çok 5 hedef (~10–15 dk). Hangi derslerden geleceğini kısaca söyle.
- Her hedefte önce anlatma, önce sor (geri çağırma): hedefin Bloom düzeyinde tek bir soru ya da kısa bir vaka
  sahnesi. Cevaptan sonra kısa düzelt; gerekiyorsa ders_oku ile o bölümden 2–3 cümlelik yeniden anlatım yap.
- Açık yanılgısı olan hedefte, o yanılgıyı yoklayan bir soru sor; doğru cevaplarsa yanılgıyı kapat.
- Her cevabı o dersin kaydına kayit_yaz ile işle (ders alanı o dersin kimliği). Böylece sonraki tekrar zamanı güncellenir.
- Bitince hangi hedeflerin bir sonraki tekrara kaldığını söyle."""


def gun_farki(once, sonra):
    return int((time.mktime(time.strptime(sonra, "%Y-%m-%d")) - time.mktime(time.strptime(once, "%Y-%m-%d")) + 3600) // 86400)


def ar_tekrar_listesi(a):
    klasor = ogrenci_klasoru(a.get("ogrenci"))
    b = bugun()
    liste = []
    for yol in sorted(glob.glob(os.path.join(klasor, "*.json"))):
        ders = os.path.splitext(os.path.basename(yol))[0]
        if not os.path.isdir(os.path.join(KOK, "lessons", ders)):
            continue
        try:
            k, _ = kd.guvenli_oku(yol)
            if not k:
                continue
            kr = karne_.hesapla(k, karne_.ders_hedefleri(ders_yolu(ders)), b)
        except (ValueError, KeyError, OSError):
            continue
        hb = {h["id"]: h for h in kr["hedefler"]}
        for hid in dict.fromkeys(kr["tekrar_zamani_gelen"] + kr["gelistirilecek"]):
            h = hb.get(hid, {})
            st = h.get("sonraki_tekrar")
            neden = [x for x, v in (("tekrar zamanı geldi", hid in kr["tekrar_zamani_gelen"]),
                                    ("başarı düşük", hid in kr["gelistirilecek"])) if v]
            liste.append({"ders": ders, "hedef": hid, "baslik": h.get("baslik"), "bloom": h.get("hedef_bloom"),
                          "neden": " · ".join(neden), "basari": h.get("oran"),
                          "gecikme_gun": gun_farki(st, b) if st and st <= b else 0})
        for y, v in (k.get("yanilgilar") or {}).items():
            if v.get("durum") == "acik":
                liste.append({"ders": ders, "yanilgi": y, "neden": "açık yanılgı", "basari": None, "gecikme_gun": 0})
    liste.sort(key=lambda x: (-x["gecikme_gun"], x["basari"] if x["basari"] is not None else 1))
    if not liste:
        return metin({"ogrenci": a.get("ogrenci"), "liste": [], "not": "Bugün tekrar zamanı gelen ya da zayıf kalan hedef yok."})
    return metin({"talimat": TEKRAR_TALIMAT, "ogrenci": a.get("ogrenci"), "liste": liste[:20], "toplam": len(liste)})


# ---------- Ölçme (pilot) ----------
TEST_AD = {"on": "Ön test", "son": "Son test", "gecikmeli": "Gecikmeli test"}

OLCME_TALIMAT = """Bu bir ölçme testi, ders değil. Eğitmen kurallarını test bitene kadar askıya al:
- İpucu, açıklama, doğru/yanlış bilgisi verme; öğrencinin cevabını yorumlama. "Bilmiyorum" geçerli bir cevaptır.
- Önce öğrenciye kısaca söyle: soru sayısı, yaklaşık 15 dakika, not için değil, sonuçlar ve doğru cevaplar sonda.
- Soruları sırayla, tek tek sor. Çoktan seçmeli soruda soru_sor'u 'dogru' ve 'aciklama' OLMADAN, verilen secenekler
  sırasıyla ve etiket ile çağır (ör. "Ön test · 3/12"). Dönen 'secim' değerini not al.
- Kısa yazılı soruda soruyu tahtaya yaz (tahta: title + text) ve öğrencinin cevabını sohbetten ya da dinle ile al.
  Puanı 'olcut'e göre sessizce ver (0, 1, 2); öğrenciye söyleme. olcme_kaydet'te öğrencinin cevabını kelimesi
  kelimesine ham_yanit olarak ver (düzeltme, özetleme yok; konuştuysa dinle'nin ham_metin'i).
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


def olcme_grubu(k, o):
    """Çapraz form tasarımında öğrencinin grubu: 1 → plan olduğu gibi (ör. A→B→A), 2 → formlar yer değiştirir
    (B→A→B). Grup bir kez belirlenir ve kayda yazılır. Öğrenci numarasının son hanesi varsa tek/çift (sınıfta
    yaklaşık yarı yarıya ve öğretmen tarafından denetlenebilir), yoksa kimlikten türetilen sabit bir sayı."""
    if not (o.get("plan") or {}).get("capraz") or len(o.get("formlar") or {}) != 2:
        return None
    if k.get("olcme_grubu") in (1, 2):
        return k["olcme_grubu"]
    bilgi = depo().defter()["ogrenciler"].get(k.get("_kimlik") or k.get("ogrenci_kimligi")) or {}
    ayirt = "".join(c for c in str(bilgi.get("ayirt") or "") if c.isdigit())
    if ayirt:
        g = 1 if int(ayirt[-1]) % 2 == 0 else 2
    else:
        g = 1 + int(hashlib.sha256(tohum(k).strip().lower().encode("utf-8")).hexdigest()[:8], 16) % 2
    k["olcme_grubu"] = g
    return g


def test_formu(a, k=None):
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
    if k is not None and olcme_grubu(k, o) == 2:
        a_, b_ = sorted(o["formlar"])
        form = b_ if form == a_ else a_
    return eg, o, form, ogr


def ar_olcme_testi(a):
    test_formu(a)  # önce girdileri denetle
    tur, ders = a["tur"], a["ders"]
    k = kayit_yukle(a["ogrenci"].strip(), ders)
    yeni_grup = "olcme_grubu" not in k
    eg, o, form, ogr = test_formu(a, k)
    if yeni_grup and k.get("olcme_grubu"):
        kayit_kaydet(k)
    ogr = tohum(k)
    uyari = list(k.get("_uyarilar") or [])
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
    test_formu(a)
    tur, ders = a["tur"], a["ders"]
    k = kayit_yukle(a["ogrenci"].strip(), ders)
    eg, o, form, ogr = test_formu(a, k)
    ogr = tohum(k)
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
            # Ham cevap: Claude'un puanını sonradan körlemeli insan puanıyla karşılaştırabilmek için (araştırma).
            if (y.get("ham_yanit") or "").strip():
                r["ham_yanit"] = y["ham_yanit"].strip()
            else:
                uyarilar.append("%s: ham_yanit eksik; öğrencinin cevabını kelimesi kelimesine ver" % s["no"])
            tam = r["puan"] == 2
            if r["puan"] == 0 and s.get("yanilgi") and y.get("yanilgi_secildi"):
                yanilgilar.append(s["yanilgi"])
        if y.get("guven") == "emin" and not tam:
            r["emin_ama_yanlis"] = True
            emin_yanlis += 1
        puan += r["puan"]
        ayrinti.append(r)
    eksik = [n for n in sorular if n not in {r["no"] for r in ayrinti}]
    kayit = {"tur": tur, "form": form, "grup": k.get("olcme_grubu"), "tarih": bugun(), "saat": time.strftime("%H:%M"), "puan": puan,
             "toplam": toplam, "emin_ama_yanlis": emin_yanlis, "secilen_yanilgilar": sorted(set(yanilgilar)),
             "yarim_kaldi": bool(a.get("yarim_kaldi") or eksik), "yanitlar": ayrinti}
    if eksik:
        kayit["cevapsiz"] = eksik
    k.setdefault("testler", []).append(kayit)
    yol = kayit_kaydet(k)
    out = {"durum": "kaydedildi", "dosya": yol, "test": TEST_AD[tur], "puan": puan,
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
    return metin(uyari_ekle(out, k))


# ---------- Kayıtları aktarma (yalnız bu bilgisayarda; hiçbir yere gönderilmez) ----------
def ar_kayit_disa_aktar(a):
    r = kayit_aktar.disa_aktar(depo(), a.get("ogrenci"), a.get("cikti") or None)
    r["not"] = ("Öğrenciye dosyanın yerini söyle. Bu dosyayı başka bilgisayara (USB bellek, e-posta) kendisi taşır; "
                "orada kayit_ice_aktar ile ya da tools/kayit_aktar.py ice ile içe alır. Dosyada adı vardır; "
                "yalnız güvendiği yere koysun.")
    return metin(r)


def ar_kayit_ice_aktar(a):
    yol = os.path.abspath(os.path.expanduser((a.get("dosya") or "").strip().strip('"')))
    if not os.path.isfile(yol):
        raise ValueError("Dosya bulunamadı: %s" % yol)
    r = kayit_aktar.ice_aktar(depo(), yol, bool(a.get("uzerine")))
    r["not"] = "Sonraki araçlarda ogrenci alanına bu kimliği yaz: %s" % r["kimlik"]
    return metin(r)


def ar_kayit_anonim_aktar(a):
    r = kayit_aktar.anonim(depo(), a.get("ogrenciler") or None, a.get("dosyalar") or None,
                           bool(a.get("deneme_dahil")), a.get("cikti") or veri_yeri.masaustu(),
                           ham_yanitlar=bool(a.get("ham_yanitlar")))
    return metin({"dosya": r["dosya"], "ogrenci_sayisi": r["ogrenci_sayisi"],
                  "haric_tutulan_deneme": r["haric_tutulan_deneme"],
                  "not": ("Dosyada ad, kimlik ve ayırt edici yoktur; kodlar rastgeledir. Ölçme testlerinin kısa yazılı "
                          "cevapları ham metin olarak VAR: paylaşmadan önce içinde ad ya da kimlik geçmediğini kontrol et.")
                  if a.get("ham_yanitlar") else
                  "Dosyada ad, kimlik, ayırt edici ve serbest metin yoktur; kodlar rastgeledir."})


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
    return metin({"durum": "hazır", "tahta": d.get("sayfa"), "ses": d.get("ses"), "dikte": dikte_durumu(d),
                  "not": "Tahta açık. Kullanıcı ilk açılışta sayfada 'başlat' düğmesine bir kez dokunmalı; "
                         "dokunmadıysa ses çalmaz ama yazılar görünür."})


def dikte_durumu(d):
    """Mikrofonun hangi tanıyıcıyla çalıştığı ve Duyu'nun kurulum durumu."""
    out = {}
    sayfa = d.get("sayfa") if isinstance(d.get("sayfa"), dict) else {}
    if sayfa.get("dikte"):
        out["motor"] = sayfa["dikte"]
    try:
        r = urllib.request.Request(ADRES + "/api/duyu/durum")
        with urllib.request.urlopen(r, timeout=10) as y:
            du = json.loads(y.read().decode("utf-8"))
    except Exception:
        du = None
    if du is None:
        out["duyu"] = "bilinmiyor (sunucu eski sürüm olabilir)"
    elif not du.get("kurulu"):
        out["duyu"] = "kurulu değil"
        out["not"] = ("Mikrofon tarayıcının tanıyıcısıyla çalışıyor; alan terimlerini bozabilir. Daha doğru tanıma için "
                      "kullanıcıya bir kez şu komutu çalıştırmasını önerebilirsin: " + du.get("komut", ""))
    else:
        out["duyu"] = "hazır" if du.get("hazir") else ("kurulu" if du.get("model_indirildi")
                                                       else "kurulu, model ilk kullanımda indirilecek")
    out["terim_duzeltme"] = ("Dikteyle gelen sözlerde 'metin' terim sözlüğüyle düzeltilmiştir; 'ham_metin' tanıyıcının "
                             "ilk çıktısıdır. İkisi farklıysa ve anlam belirsizse öğrenciye kısaca sor.")
    return out


def ar_tahta(a):
    adimlar = a.get("adimlar") or []
    if not isinstance(adimlar, list) or not adimlar:
        raise ValueError("adimlar boş")
    videolari_coz(adimlar, a.get("ders"))
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
    try:
        return metin(istek("durum?al=1", zaman=5))
    except Exception:
        return metin({"durum": "sunucu kapalı", "not": "tahtayi_ac ile aç."})


VIDEO_UZANTI = (".mp4", ".m4v", ".webm", ".ogv", ".mov")


def ders_videolari(ders):
    """Kimlik → {src | youtube, baslik, ...}. Klasördeki dosyalar (lessons/<ders>/videolar/) ve tanımlı bağlantılar.
    İsteğe bağlı lessons/<ders>/videolar/videolar.json: {"dosya.mp4": {"baslik", "aciklama", "credit"}}."""
    out = {}
    klasor = ders_yolu(ders, "videolar")
    bilgi = {}
    yol = os.path.join(klasor, "videolar.json")
    if os.path.exists(yol):
        try:
            with open(yol, encoding="utf-8") as f:
                bilgi = json.load(f) or {}
        except ValueError:
            bilgi = {}
    if os.path.isdir(klasor):
        for ad in sorted(os.listdir(klasor)):
            if not ad.lower().endswith(VIDEO_UZANTI):
                continue
            kimlik = os.path.splitext(ad)[0]
            b = bilgi.get(ad) or bilgi.get(kimlik) or {}
            out[kimlik] = dict(b, dosya=ad, src="/lessons/%s/videolar/%s" % (ders, urllib.request.quote(ad)),
                               boyut_mb=round(os.path.getsize(os.path.join(klasor, ad)) / 1e6, 1), internet=False)
    tanimli = dict((ders_json_ham(ders) or {}).get("videos") or {})
    tanimli.update((egitmen_json(ders) or {}).get("videolar") or {})
    for kimlik, v in tanimli.items():
        v = dict(v)
        if v.get("src") and not v["src"].startswith(("/", "http")):
            v["src"] = "/lessons/%s/%s" % (ders, v["src"])
        v["internet"] = bool(v.get("youtube") or str(v.get("src", "")).startswith("http"))
        out[kimlik] = v
    return out


def ders_json_ham(ders):
    yol = ders_yolu(ders, "ders.json")
    if not os.path.exists(yol):
        return None
    with open(yol, encoding="utf-8") as f:
        return json.load(f)


def ar_videolar(a):
    v = ders_videolari(a.get("ders"))
    if not v:
        return metin({"ders": a.get("ders"), "videolar": {},
                      "not": "Bu dersin videosu yok. Öğretmen videoları lessons/%s/videolar/ klasörüne koyabilir; "
                             "kullanıcı bir YouTube bağlantısı verirse {type:'video', youtube:'<bağlantı>'} ile oynatılır." % a.get("ders")})
    return metin({"ders": a.get("ders"), "videolar": v})


def videolari_coz(adimlar, ders):
    """tahta aracındaki video komutlarında 'video' kimliğini dosya yoluna ya da YouTube bağlantısına çevirir."""
    liste = None
    for adim in adimlar:
        for c in (adim or {}).get("komutlar") or []:
            if not isinstance(c, dict) or c.get("type") != "video" or c.get("src") or c.get("youtube"):
                continue
            if not c.get("video"):
                raise ValueError("video komutunda video, youtube ya da src gerekli")
            if not ders:
                raise ValueError("Ders videosu için tahta aracına ders alanını da ver")
            if liste is None:
                liste = ders_videolari(ders)
            v = liste.get(c["video"])
            if not v:
                raise ValueError("Video yok: %s. Bu dersin videoları: %s" % (c["video"], ", ".join(liste) or "yok"))
            for k in ("src", "youtube", "baslangic", "bitis"):
                if v.get(k) is not None and c.get(k) is None:
                    c[k] = v[k]
            if not c.get("caption") and (v.get("baslik") or v.get("caption")):
                c["caption"] = v.get("baslik") or v.get("caption")
            if v.get("credit"):
                c["credit"] = v["credit"]
            c.pop("video", None)


def ar_anlatima_devam(a):
    birak = a.get("birak") is True
    r = gonder({"tur": "devam", "birak": birak}, bekle=True)
    no = r.get("anlatim_no")
    if birak or r.get("durum") not in ("devam_ediyor", "zaten_suruyor") or not no:
        return metin(r)
    # Anlatım sürüyor: bitişini tahta aracındaki gibi bekle (kullanıcı yine konuşursa hemen döner).
    try:
        s = istek("sonuc?no=%d&bekle=40" % int(no), zaman=70)
    except urllib.error.URLError:
        return metin(r)
    s["devam"] = r.get("durum")
    return metin(s)


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
               "tahta_durumu": ar_tahta_durumu, "dinle": ar_dinle, "durdur": ar_durdur,
               "anlatima_devam": ar_anlatima_devam, "videolar": ar_videolar,
               "bilgi_ara": ar_bilgi_ara, "vakalar": ar_vakalar, "vaka_oku": ar_vaka_oku, "karne": ar_karne,
               "sozlu_prova": ar_sozlu_prova, "tekrar_listesi": ar_tekrar_listesi,
               "kayit_disa_aktar": ar_kayit_disa_aktar, "kayit_ice_aktar": ar_kayit_ice_aktar,
               "kayit_anonim_aktar": ar_kayit_anonim_aktar}


def metin(veri, hata=False):
    t = veri if isinstance(veri, str) else json.dumps(veri, ensure_ascii=False, indent=1)
    out = {"content": [{"type": "text", "text": t}]}
    if hata:
        out["isError"] = True
    return out


# ---------- MCP (JSON-RPC, satır satır stdin/stdout) ----------
YAZ_KILIT = threading.Lock()  # kanal iş parçacığı ile ana döngü aynı anda yazmasın


def yaz(mesaj):
    with YAZ_KILIT:
        sys.stdout.buffer.write(json.dumps(mesaj, ensure_ascii=False).encode("utf-8") + b"\n")
        sys.stdout.buffer.flush()


# ---------- Claude Code kanalı (isteğe bağlı: --kanal) ----------
# Claude Code'un "channels" özelliği (araştırma önizlemesi) bir MCP sunucusunun oturuma kendiliğinden ileti
# göndermesine izin verir: notifications/claude/channel. Claude masaüstü sohbeti bunu desteklemez; bu yüzden
# yalnız --kanal ile açılır (yoksa söz, iletilmediği hâlde sunucudan alınıp kaybolurdu).
# Claude Code'u şöyle başlatın:  claude --dangerously-load-development-channels server:klinik-koc
KANAL = "--kanal" in sys.argv or os.environ.get("KLINIK_KOC_KANAL") == "1"
_kanal_basladi = False


def kanal_dongusu():
    while True:
        try:
            r = istek("kanal?bekle=25", zaman=45)
        except Exception:
            time.sleep(3)  # sunucu kapalı: tahtayi_ac açınca bağlanılır
            continue
        if r.get("durum") == "konustu" and r.get("metin"):
            sayfa = r.get("sayfa") or {}
            meta = {"kaynak": "tahta_mikrofonu"}
            if sayfa.get("ders"):
                meta["ders"] = str(sayfa["ders"])
            yaz({"jsonrpc": "2.0", "method": "notifications/claude/channel",
                 "params": {"content": r["metin"], "meta": meta}})


def kanali_baslat():
    global _kanal_basladi
    if KANAL and not _kanal_basladi:
        _kanal_basladi = True
        threading.Thread(target=kanal_dongusu, daemon=True).start()


def isle(m):
    yontem, no, p = m.get("method"), m.get("id"), m.get("params") or {}
    if no is None:
        if yontem == "notifications/initialized":
            kanali_baslat()
        return None  # bildirim: yanıt verilmez
    if yontem == "initialize":
        yetenek = {"tools": {}}
        if KANAL:
            yetenek["experimental"] = {"claude/channel": {}}
        return {"protocolVersion": p.get("protocolVersion") or "2025-06-18",
                "capabilities": yetenek,
                "serverInfo": {"name": AD, "title": "KlinikKoç", "version": SURUM},
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
# Claude masaüstü uygulamasının MCP ayarı (claude_desktop_config.json) kuruluma göre farklı yerdedir:
#  - Windows, Microsoft Store (MSIX) kurulumu, yeni sürümler: %LOCALAPPDATA%\Claude-Data\claude_<paket>\
#    (uygulama veriyi buraya taşır, eski paket klasörüne ".user-data-left.*" işareti bırakır)
#  - Windows, MSIX eski sürümler: %LOCALAPPDATA%\Packages\Claude_<paket>\LocalCache\Roaming\Claude\
#  - Windows, .exe kurulumu: %APPDATA%\Claude\
#  - macOS: ~/Library/Application Support/Claude/   - Linux: ~/.config/Claude/
# Kesin yol, uygulamada Ayarlar › Geliştirici › "Yapılandırmayı düzenle" düğmesinin açtığı dosyadır;
# bulunamazsa kullanıcı onu --ayar "<yol>" ile verebilir.
AYAR_ADI = "claude_desktop_config.json"


def _paket_kimligi(klasor_adi):
    """'Claude_pzs8sxrjxfjjc' / 'claude_pzs8sxrjxfjjc' → 'pzs8sxrjxfjjc'."""
    return klasor_adi.split("_", 1)[1].lower() if "_" in klasor_adi else ""


def ayar_adaylari(isletim=None, ortam=None):
    """Olası ayar dosyalarını [(yol, tur, aciklama)] olarak döndürür.

    tur: "asil"  → Claude'un okuduğu dosya (kur buraya yazar)
         "eski"  → eskiden kullanılan, artık okunmayan dosya (yalnız bilgi için listelenir)
    Klasörü olmayan adaylar listelenmez. Hiç aday yoksa boş liste döner.
    """
    isletim = isletim or ("nt" if os.name == "nt" else sys.platform)
    ortam = os.environ if ortam is None else ortam
    sonuc = []
    if isletim == "nt":
        appdata = ortam.get("APPDATA", "")
        yerel = ortam.get("LOCALAPPDATA", "")
        tasinan = set()
        if yerel:
            for d in sorted(glob.glob(os.path.join(yerel, "Claude-Data", "claude_*"))):
                if os.path.isdir(d):
                    tasinan.add(_paket_kimligi(os.path.basename(d)))
                    sonuc.append((os.path.join(d, AYAR_ADI), "asil", "Microsoft Store kurulumu (yeni yer)"))
        msix_var = False
        if yerel:
            for paket in sorted(glob.glob(os.path.join(yerel, "Packages", "Claude_*"))):
                d = os.path.join(paket, "LocalCache", "Roaming", "Claude")
                if not os.path.isdir(d):
                    continue
                msix_var = True
                ayrildi = glob.glob(os.path.join(d, ".user-data-left*"))
                if ayrildi or _paket_kimligi(os.path.basename(paket)) in tasinan:
                    sonuc.append((os.path.join(d, AYAR_ADI), "eski", "Microsoft Store paket klasörü (veri taşınmış)"))
                else:
                    sonuc.append((os.path.join(d, AYAR_ADI), "asil", "Microsoft Store paket klasörü"))
        if appdata and os.path.isdir(os.path.join(appdata, "Claude")):
            if msix_var or tasinan:
                # Store kurulumunda uygulama %APPDATA%\Claude'u okumaz.
                sonuc.append((os.path.join(appdata, "Claude", AYAR_ADI), "eski", "%APPDATA%\\Claude (Store kurulumu bunu okumaz)"))
            else:
                sonuc.append((os.path.join(appdata, "Claude", AYAR_ADI), "asil", "Claude .exe kurulumu"))
    else:
        if isletim == "darwin":
            d = os.path.expanduser("~/Library/Application Support/Claude")
        else:
            d = os.path.join(ortam.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "Claude")
        if os.path.isdir(d):
            sonuc.append((os.path.join(d, AYAR_ADI), "asil", "Claude masaüstü"))
    return sonuc


def ayar_dosyalari():
    """Claude'un okuduğu ayar dosyaları (kur bunlara yazar)."""
    return [y for y, tur, _ in ayar_adaylari() if tur == "asil"]


YOL_GOSTER = ("Claude'un ayar dosyası bulunamadı.\n"
              "Claude masaüstü uygulamasını açın → Ayarlar → Geliştirici → \"Yapılandırmayı düzenle\".\n"
              "Açılan dosyanın yolunu kopyalayıp şunu çalıştırın:\n"
              "  python tools/tahta-mcp.py --kur --ayar \"<dosyanın yolu>\"")


def _ayar_yolu_arg():
    if "--ayar" in sys.argv:
        i = sys.argv.index("--ayar")
        if i + 1 >= len(sys.argv):
            sys.exit("--ayar'dan sonra dosya yolunu yazın.")
        yol = os.path.abspath(os.path.expanduser(sys.argv[i + 1].strip('"')))
        if os.path.isdir(yol):
            yol = os.path.join(yol, AYAR_ADI)
        return yol
    return None


def sunucu_girdisi():
    return {"command": sys.executable, "args": [os.path.abspath(__file__)],
            "env": {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}}


def ayara_yaz(yol, kaldir=False):
    """Yalnız mcpServers[AD]'yi değiştirir; dosyadaki öteki alanlar (preferences vb.) olduğu gibi kalır."""
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    ayar = {}
    if os.path.exists(yol) and os.path.getsize(yol) > 0:
        try:
            with open(yol, encoding="utf-8-sig") as f:
                ayar = json.load(f) or {}
        except Exception:
            sys.exit("Ayar dosyası okunamadı (bozuk JSON?): %s\nDosyayı düzeltip yeniden deneyin." % yol)
        shutil.copy2(yol, yol + ".yedek")
    sunucular = ayar.setdefault("mcpServers", {})
    if kaldir:
        sunucular.pop(AD, None)
    else:
        sunucular[AD] = sunucu_girdisi()
    gecici = yol + ".yaziliyor"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(ayar, f, ensure_ascii=False, indent=2)
    os.replace(gecici, yol)


def kur(kaldir=False):
    elle = _ayar_yolu_arg()
    hedefler = [elle] if elle else ayar_dosyalari()
    if not hedefler:
        print(YOL_GOSTER)
        sys.exit(1)
    for yol in hedefler:
        ayara_yaz(yol, kaldir)
        print(("Kaldırıldı: " if kaldir else "Eklendi (Claude'un okuduğu dosya): ") + yol)
    if not elle:
        for yol, tur, aciklama in ayar_adaylari():
            if tur == "eski":
                print("Atlandı (eski yer, Claude artık okumuyor): %s" % yol)
    if not kaldir:
        print("\nŞimdi Claude masaüstü uygulamasını TAMAMEN kapatın: saatin yanındaki ^ → Claude simgesi →")
        print("sağ tık → Çık (Mac'te Cmd+Q). Sonra yeniden açın.")
        print("Denetim: Claude'da Ayarlar › Geliştirici ekranında '%s' \"Çalışıyor\" görünmeli." % AD)
        print("Görünmüyorsa: aynı ekranda \"Yapılandırmayı düzenle\"ye basın, açılan dosyanın yolunu")
        print("  python tools/tahta-mcp.py --kur --ayar \"<yol>\"  ile verin.")
        print("Sonra Claude'a şunu yazın:  Tahtayı aç ve bana Şekil 2'yi anlat.")
        kayit_yeri_hazirla()


def ayar_raporu():
    """--dene için: bulunan her ayar dosyasında bu sunucu var mı? Sorun varsa uyarı satırları döndürür."""
    satirlar, uyarilar = [], []
    adaylar = ayar_adaylari()
    if not adaylar:
        uyarilar.append(YOL_GOSTER)
    for yol, tur, aciklama in adaylar:
        durum = "dosya yok"
        if os.path.exists(yol):
            try:
                with open(yol, encoding="utf-8-sig") as f:
                    g = ((json.load(f) or {}).get("mcpServers") or {}).get(AD)
                if g:
                    hedef = (g.get("args") or [""])[0]
                    durum = AD + " var" + ("" if os.path.exists(hedef) else " AMA dosyası yok: " + hedef)
                    if tur == "asil" and not os.path.exists(hedef):
                        uyarilar.append("%s girdisi var olmayan bir dosyayı gösteriyor: %s\nKUR'u bu klasörden yeniden çalıştırın." % (AD, hedef))
                else:
                    durum = AD + " YOK"
            except Exception as e:
                durum = "okunamadı (%s)" % e
        satirlar.append("  [%s] %s\n        %s — %s" % ("asıl" if tur == "asil" else "eski", aciklama, yol, durum))
        if tur == "asil" and AD + " var" not in durum:
            uyarilar.append("Claude'un okuduğu dosyada %s yok: %s\nKUR'u yeniden çalıştırın." % (AD, yol))
    return satirlar, uyarilar


def kayit_yeri_hazirla():
    d = depo()
    d.hazirla()
    print("\nÖğrenci kayıtları bu klasörde durur (güncellemede silinmez):\n  " + d.kok)
    if d.tasima_raporu:
        print("Eski kayıtlar buraya kopyalandı (%d dosya); eski dosyalar silinmedi: %s" % (
            d.tasima_raporu["kopyalanan"], d.tasima_raporu["kaynak"]))


def kendini_dene():
    """Kurulumdan sonra hızlı denetim: araç listesi ve ders dosyaları okunuyor mu?"""
    print("Python:", sys.executable)
    print("Klasör:", KOK)
    print("Dersler:", ", ".join(g["id"] for g in katalog()) or "yok")
    print("Araçlar:", ", ".join(a["name"] for a in ARACLAR))
    print("Kayıt klasörü:", KAYIT_KOK)
    d = sunucu_acik()
    print("Yerel sunucu:", "açık, tahta " + ("bağlı" if d and d.get("bagli") else "bağlı değil") if d else "kapalı (Claude açacak)")
    satirlar, uyarilar = ayar_raporu()
    print("Claude ayar dosyaları:")
    for x in satirlar:
        print(x)
    for u in uyarilar:
        print("UYARI: " + u)
    if not uyarilar:
        print("Tamam: Claude'un okuduğu ayar dosyasında %s var." % AD)


if __name__ == "__main__":
    if "--kur" in sys.argv:
        kur()
    elif "--kaldir" in sys.argv:
        kur(kaldir=True)
    elif "--kayit-yeri" in sys.argv:
        kayit_yeri_hazirla()
    elif "--dene" in sys.argv:
        kendini_dene()
    else:
        calis()
