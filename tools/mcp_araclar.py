"""KlinikKoç tahta aracının (tools/tahta-mcp.py) Claude'a gösterdiği metinler: genel talimat ve araç tanımları.

Yalnız veri; mantık tools/tahta-mcp.py'dedir. Bir aracın adını ya da alanlarını değiştirirseniz tahta-mcp.py'deki
işleyicisini (ISLEYICILER) de güncelleyin. Öğretmen araçları öğrenci profilinde gizlenir (tahta-mcp.py: OGRETMEN_ARACLARI).
"""

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
  bekle(no) çağrın beklemeden {"durum": "kullanici_konustu", "kullanici_konustu": "..."} döner.
  Önce ona cevap ver: tahtada sesli (tahta aracı; cevap araya girer, tahta sonra eski hâline döner) ya da
  sohbette. Sonra anlatima_devam ile anlatımı kaldığı yerden sürdür; konu değiştiyse anlatima_devam(birak=true).
- Soru kartı açıkken konuşursa kart kapanır; gerekirse soruyu yeniden sor.
- tahta ya da soru_sor 'gonderilmedi: true' ile dönerse kullanıcının cevaplanmamış sözü vardır; önce ona cevap ver.
- Bekleme tek araçtır: bekle. Bir bölümü/cevabı bitirince bekle'yi (no'suz) çağır; gelen söze tahtada sesli
  cevap ver (gerekirse çizerek), sonra yeniden bekle. tahta ya da soru_sor 'sürüyor' dönerse bekle(no) çağır;
  sohbete "anlatım sürüyor" gibi bir şey yazma. bekle "sessiz" dönerse 'devam' alanına bak: devam=true ise
  hemen yeniden bekle; devam=false gelince döngüyü bırak ve sonuçtaki 'not'taki gibi sohbete tek cümle yaz.
- Bir oturumda cevabını bitirmeden önce son iş olarak bekle çağır. Sen beklemezken söylenenler kaybolmaz:
  otomatik uyandırma açıksa söz bu sohbete "Tahtadan sesli soru: ..." diye kendiliğinden düşer; kapalıysa
  tahta öğrenciye sohbete "tahtaya bak" yazmasını söyler. "Tahtadan sesli soru: ..." iletisi tahtada söylenmiş
  bir sözdür: cevabını tahtada sesli ver (tahta aracı), sohbete uzun yazma, sonra bekle. Kullanıcı "tahtaya bak"
  yazarsa tahta_durumu'nu (no'suz) çağır: bekleyen sözü döndürür.
- tahta, soru_sor ve tahta_durumu sonuçlarında 'kullanici_konustu' alanı varsa kullanıcı o sırada
  konuşmuştur; önce ona cevap ver.
- Claude Code'da kanal açıksa (tahta-mcp.py --kanal) sen dinlemezken söylenenler sohbete <channel
  source="klinik-koc"> iletisi olarak düşer; ona da tahtada cevap ver.
- Öğrenci "dur", "bekle", "ara verelim" derse beklemeyi de bırak.
- Ders sırasında dersin kendisinde bir sorun görürsen (yanlış ya da çelişkili bilgi, kaynakta olmayan ama çok
  sorulan konu, belirsiz cevap anahtarı, anlaşılmayan adım, araç hatası, dikte hatası) degerlendirme_notu ile hemen
  not al; öğrenciye söylemen gerekmez. ders_bitir ders sonu değerlendirme formunu açar; formda bu notlar görünür.
Duraklat: Kullanıcı tahtadaki ⏸ tuşuyla (ya da P / Boşluk) anlatımı duraklatabilir. Bu iptal değildir.
- tahta, soru_sor ya da tahta_durumu 'duraklatildi' dönerse hata sayma, yeni komut gönderme, sohbete de
  yazma; aynı no ile bekle(no) çağırarak beklemeyi sürdür. Devam edince anlatım kaldığı yerden sürer
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
                   "yalnız yeni etiketler belirir. CANLANDIRMA: aynı template'i başka variant ve gecis:<sn> (0,5–10, ör. 3) ile "
                   "gönderirsen çizim o saniyede eski durumdan yenisine akarak geçer (dişeti şişer, cep derinleşir, kemik geriler; "
                   "probe:true ise sonda cep tabanını izler). Her durumu ayrı adımda o adımın cümlesiyle gönder; adım hem cümle hem "
                   "geçiş bitince ilerler, Duraklat ikisini de durdurur. Ör. saglikli → gingivitis (gecis 3) → periodontitis (gecis 4); "
                   "implant: saglikli → mukozitis → peri-implantitis. Etiket metnini yazmazsan doğru Türkçe terim kullanılır. "
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
                       "mod: once_anlat|once_yanitla. mola: bekleyen nokta metni ya da null. oturum: {egitmen, ozet, sure_dk "
                       "(oturumun yaklaşık süresi, dakika)}. "
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
        "name": "makaleler",
        "description": "Bir dersin makale listesini ve her makalenin durumunu gösterir: hazir (indirildi, aramada), eksik "
                       "(bulunamadı; öğrenci yayıncı sayfasından indirip eklemeli), hata, denenmedi. Ders paketinde makalelerin "
                       "kendisi yoktur; makale_bul onları bu bilgisayara indirir. ac true ise makaleler sayfası tarayıcıda "
                       "açılır (öğrenci orada eksik PDF'leri sürükleyip bırakabilir). Dersi anlatmaya başlamadan önce bak: "
                       "eksik makale varsa öğrenciye söyle; o makaleye dayanan soruda 'bu makaleyi okuyamadım' de.",
        "inputSchema": {"type": "object", "properties": {
            "ders": {"type": "string", "description": "verilmezse makale listesi olan dersler listelenir"},
            "ac": {"type": "boolean", "description": "makaleler sayfasını tarayıcıda aç"}}},
    },
    {
        "name": "ders_paketi_ekle",
        "description": "Öğretmenin verdiği ders paketini (.zip) bu bilgisayara kurar ve makalelerini arka planda aramaya "
                       "başlar. Program derssiz gelir; öğrenci 'ders listesi boş', 'ders yok' derse ya da bir zip'ten söz "
                       "ederse bunu kullan. zip verilmezse ders paketleri sayfasını açar (öğrenci zip'i oraya sürükler). "
                       "Ders zaten kuruluysa öğrenciye güncellemek isteyip istemediğini sor; isterse uzerine: true.",
        "inputSchema": {"type": "object", "properties": {
            "zip": {"type": "string", "description": "paketin bu bilgisayardaki yolu, ör. İndirilenler'deki dosya"},
            "uzerine": {"type": "boolean", "description": "ders kuruluysa yenisiyle değiştir (kayıtlar korunur)"}}},
    },
    {
        "name": "makale_bul",
        "description": "Dersin makalelerini arka planda bulup indirir: önce bilgisayardaki makale klasörü, sonra açık erişimli "
                       "sürüm, sonra yayıncı (bilgisayar üniversite ağındaysa abonelikli dergiler de iner). İnenler metne "
                       "çevrilip aramaya eklenir. Birkaç dakika sürebilir; ilerlemeyi makaleler aracıyla izle.",
        "inputSchema": {"type": "object", "properties": {"ders": {"type": "string"}}, "required": ["ders"]},
    },
    {
        "name": "makale_ekle",
        "description": "Öğrencinin bu bilgisayardaki bir PDF'ini derse ekler. kaynak verilirse o makalenin yerine geçer; "
                       "verilmezse PDF'teki DOI'den listedeki makale bulunur, bulunamazsa 'öğrencinin eklediği' ayrı kaynak olur. "
                       "Makale hiçbir derse bağlı değilse (ya da hiç ders yoksa) ders='kendi-makalelerim' kullan: öğrencinin "
                       "kişisel kitaplığıdır; sonra egitmen_hazirla(ders='kendi-makalelerim') ile o makalelerle çalışılır.",
        "inputSchema": {"type": "object", "properties": {
            "ders": {"type": "string", "description": "ders kimliği ya da 'kendi-makalelerim'"},
            "dosya": {"type": "string", "description": "PDF'in bu bilgisayardaki tam yolu"},
            "kaynak": {"type": "string", "description": "makaleler listesindeki id (isteğe bağlı)"}},
            "required": ["ders", "dosya"]},
    },
    {
        "name": "sihirbaz_oku",
        "description": "Öğretmen için: ders hazırlama sihirbazındaki bir ders taslağını okur (ders kartı, makale künyeleri ve "
                       "özetleri, ders notunun bölümleri, öğretmenin soruları ve dikkat edilecekler, onaylı hedefler) ve "
                       "nasıl öneri yazılacağını söyler. ders verilmezse taslaklar listelenir. Öğretmen 'X dersi için "
                       "öneri hazırla' derse önce bunu, sonra sihirbaz_oner'i çağır.",
        "inputSchema": {"type": "object", "properties": {"ders": {"type": "string"}}},
    },
    {
        "name": "sihirbaz_oner",
        "description": "Öğretmen için: ders taslağına öneri yazar (hedefler + Bloom düzeyi, terimler, soru taslakları, "
                       "yanılgılar). Öneriler öğretmen sihirbaz sayfasında kabul etmeden derse girmez. Biçim için "
                       "sihirbaz_oku'nun talimatına uy. Yalnız gönderdiğin türler değişir.",
        "inputSchema": {"type": "object", "properties": {
            "ders": {"type": "string"},
            "hedefler": {"type": "array", "items": {"type": "object"}},
            "terimler": {"type": "array", "items": {"type": "string"}},
            "sorular": {"type": "array", "items": {"type": "object"}},
            "yanilgilar": {"type": "array", "items": {"type": "object"}},
            "ac": {"type": "boolean", "description": "sihirbaz sayfasını tarayıcıda aç"}},
            "required": ["ders"]},
    },
    {
        "name": "ders_bitir",
        "description": "Öğrenci dersi bitirince (bütün hedefler ele alındı ya da öğrenci 'bitirdim' dedi) çağır. Tamamlama "
                       "raporunu öğrencinin bilgisayarına yazar (hedefler, zorlandığı konular, vakalar, çalışma süresi, "
                       "notu), zorlandığı sorulardan en çok 10 tekrar kartı çıkarır ve kaydı 'tamamlandı' diye işaretler. "
                       "Ders yerinde kalır; arşivlenmez. Önce öğrenciye derse dair bir notu olup olmadığını sor.",
        "inputSchema": {"type": "object", "properties": {
            "ogrenci": {"type": "string"}, "ders": {"type": "string"},
            "ogrenci_notu": {"type": "string", "description": "öğrencinin kendi notu (isteğe bağlı, kelimesi kelimesine)"},
            "claude_tespitleri": {"type": "array", "description": "değerlendirme formuna senin tespitlerin (henüz "
                                  "degerlendirme_notu ile yazmadıkların): [{tur, ayrinti, yer}]",
                                  "items": {"type": "object"}},
            "form": {"type": "boolean", "description": "değerlendirme formunu tarayıcıda aç (varsayılan true)"}},
            "required": ["ogrenci", "ders"]},
    },
    {
        "name": "makale_sayfasi_bak",
        "description": "Öğretmen için: derse makaleden şekil eklerken makalenin bir sayfasını görüntü olarak gösterir "
                       "(makalenin PDF'i bu bilgisayarda hazır olmalı). bolge verilirse yalnız o kısım. Şeklin yerini "
                       "bulup makale_sekli_ekle'ye bolge vermek için kullan. bolge = [sol, üst, sağ, alt], sayfanın "
                       "0–1 arası oranları (sol-üst köşe 0,0).",
        "inputSchema": {"type": "object", "properties": {
            "ders": {"type": "string"}, "kaynak": {"type": "string", "description": "kaynaklar.json'daki makale kimliği"},
            "sayfa": {"type": "integer"}, "bolge": {"type": "array", "items": {"type": "number"}}},
            "required": ["ders", "kaynak", "sayfa"]},
    },
    {
        "name": "makale_sekli_ekle",
        "description": "Öğretmen için: kurulu bir derse makalenin bir şeklini ekler. Pakete şeklin kendisi değil yalnız "
                       "yeri (makale, sayfa, bölge) girer; her öğrencinin bilgisayarı şekli onun kendi PDF'inden çizer. "
                       "Abonelikli makalelerin şekilleri için tek doğru yol budur. Önce makale_sayfasi_bak ile bölgeyi "
                       "bul; bu araç kesilen şekli gösterir, kenarlar kesik ya da fazlaysa bolge'yi düzeltip yeniden "
                       "çağır. Tahtada tahta aracının image komutunda gorsel adıyla kullanılır.",
        "inputSchema": {"type": "object", "properties": {
            "ders": {"type": "string"}, "ad": {"type": "string", "description": "görsel adı, ör. sekil1"},
            "kaynak": {"type": "string"}, "sayfa": {"type": "integer"},
            "bolge": {"type": "array", "items": {"type": "number"}, "description": "[sol, üst, sağ, alt] 0–1"},
            "baslik": {"type": "string", "description": "ör. Şekil 1"}, "aciklama": {"type": "string"}},
            "required": ["ders", "ad", "kaynak", "sayfa"]},
    },
    {
        "name": "degerlendirme_notu",
        "description": "Ders sırasında DERSİN KENDİSİNDE bir sorun fark edince HEMEN çağır; ders sonu değerlendirme "
                       "formuna 'Eğitmenin (Claude) tespitleri' olarak girer, öğrenci göndermeden önce görür ve "
                       "çıkarabilir. tur: yanlis_bilgi (derste yanlış/çelişkili bilgi), eksik_kaynak (kaynakta olmayan "
                       "ya da çok sorulan ama derste olmayan konu), anlatim (anlaşılmayan, çok uzun/kısa ya da yeniden "
                       "anlatmak zorunda kaldığın adım), soru (cevap anahtarı belirsiz/yanlış soru), teknik (araç "
                       "hatası, gecikme, açılmayan görsel, ses), dikte (tanıyıcının bozduğu terim: ham → doğru), diger. "
                       "ayrinti: kısa ve somut; yer: kanıt (bölüm/adım/soru kimliği). Öğrencinin başarısını, adını ya "
                       "da kişisel bilgisini yazma.",
        "inputSchema": {"type": "object", "properties": {
            "ogrenci": {"type": "string"}, "ders": {"type": "string"},
            "tur": {"type": "string", "enum": ["yanlis_bilgi", "eksik_kaynak", "anlatim", "soru", "teknik", "dikte", "diger"]},
            "ayrinti": {"type": "string"}, "yer": {"type": "string"}},
            "required": ["ogrenci", "ders", "tur", "ayrinti"]},
    },
    {
        "name": "degerlendirme_ozeti",
        "description": "Öğretmen için: öğrencilerin gönderdiği değerlendirme formlarını (bir klasördeki .json/.txt/.eml "
                       "dosyaları ya da e-postadan kaydedilmiş metinler) toplar; ölçekli soru ortalamaları, seçmeli "
                       "dağılımlar, açık uçlu cevaplar, Claude tespitleri ve hedef durumlarını tek özet yapar. "
                       "Klasör verilmezse Belgeler/KlinikKoç Değerlendirmeler.",
        "inputSchema": {"type": "object", "properties": {
            "klasor": {"type": "string"}, "kaydet": {"type": "boolean", "description": "özeti klasöre .md olarak yaz"},
            "deneme_dahil": {"type": "boolean"}}},
    },
    {
        "name": "tekrar_karti_yaz",
        "description": "tekrar_listesi'ndeki bir tekrar kartının sonucunu işler (ders arşivde olsa bile). dogru: öğrenci "
                       "yardımsız doğru cevapladı mı. Doğru → kart daha seyrek gelir; yanlış → ertesi gün yeniden.",
        "inputSchema": {"type": "object", "properties": {
            "ogrenci": {"type": "string"}, "ders": {"type": "string"},
            "kart": {"type": "string", "description": "kartın id'si"}, "dogru": {"type": "boolean"}},
            "required": ["ogrenci", "ders", "kart", "dogru"]},
    },
    {
        "name": "depolama",
        "description": "Derslerin bu bilgisayarda kapladığı yeri, sınırı (varsayılan 2 GB) ve arşivdeki dersleri gösterir. "
                       "Sınır aşıldıysa öğrenciye 'Hangi dersleri arşive kaldıralım?' diye sor; dersleri boyutları ve son "
                       "açılma tarihleriyle say. Arşivleme otomatik değildir. ac true ise depolama sayfası tarayıcıda açılır.",
        "inputSchema": {"type": "object", "properties": {"ac": {"type": "boolean"}}},
    },
    {
        "name": "ders_arsivle",
        "description": "Bir dersi arşive kaldırır. YALNIZ öğrenci o dersi açıkça seçip onaylayınca çağır. Arşiv zip'i "
                       "(Belgeler/KlinikKoç Arşiv) tamamlama raporlarını, ilerlemeyi ve makale listesini taşır; PDF'ler "
                       "makale klasöründe kalır. Zip denetlendikten sonra dersin işlenmiş parçaları silinir. Tekrar kartları kalır.",
        "inputSchema": {"type": "object", "properties": {"ders": {"type": "string"}}, "required": ["ders"]},
    },
    {
        "name": "arsivden_geri_yukle",
        "description": "Arşive kaldırılmış bir dersi geri getirir: ders kurulur, ilerleme kaldığı yerden sürer, PDF'ler önce "
                       "makale klasöründe aranır, olmayanlar yeniden indirilmeye çalışılır.",
        "inputSchema": {"type": "object", "properties": {
            "ders": {"type": "string", "description": "arşiv listesindeki ders (depolama aracı listeler)"},
            "dosya": {"type": "string", "description": "ya da arşiv zip'inin tam yolu"}}},
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
                       "Zamanı gelen tekrar kartlarını da verir (zorlanılan sorular; ders arşivde olsa bile). "
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
        "description": "Bilgisayardaki dersleri, bölümlerini ve görsellerini listeler. Öğrenci 'kendi makalem', 'kendi "
                       "makalelerimden', 'eklediğim PDF' gibi bir şey derse ders='kendi-makalelerim' kitaplığını kullan "
                       "(içindeki makaleler bu listede ve makaleler aracında görünür); başka bir makaleli dersi açma.",
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
                       "tahtaya çizilir, sonra anlat metni okunur. Anlatım çok uzun sürerse araç "
                       "'sürüyor' döner; bitişini bekle(no) ile bekle. Kullanıcı tahtada duraklattıysa "
                       "'duraklatildi' döner: hata değil, bekle(no) ile beklemeyi sürdür. Kullanıcı konuşursa "
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
        "description": "Tahtada çoktan seçmeli bir soru kartı açar ve dokunulan cevabı döndürür (cevap gelmeden "
                       "'sürüyor' dönerse bekle(no) ile beklemeyi sürdür). dogru verilirse kart doğru/yanlışı ve "
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
        "description": "Tahtanın durumunu verir. no verilirse o komutun (anlatım ya da soru) bitmesini bekler (bekle(no) ile aynı) "
                       "ve sonucunu döndürür; kullanıcı konuşursa beklemeden 'kullanici_konustu' döner. "
                       "'duraklatildi': kullanıcı anlatımı duraklattı; aynı no ile beklemeyi sürdür. no verilmezse "
                       "kullanıcının bekleyen sözünü de 'kullanici_konustu' alanında verir (kullanıcı 'tahtaya bak' derse).",
        "inputSchema": {"type": "object", "properties": {"no": {"type": "integer"}}},
    },
    {
        "name": "bekle",
        "description": "Tek bekleme aracı. no verilmezse öğrencinin tahtada (mikrofon ya da yazı kutusu) söylediğini bekler "
                       "ve yazı olarak döndürür; no verilirse o anlatımın ya da sorunun bitmesini bekler (öğrenci konuşursa "
                       "hemen 'kullanici_konustu' döner). Bir çağrı birkaç dakikaya kadar açık kalabilir. Kimse konuşmazsa "
                       "'sessiz' döner: 'devam' true ise hemen yeniden çağır. Sesli sohbet döngüsü: anlat → bekle → cevapla → "
                       "bekle. Dikteyle gelen sözde 'metin' terim sözlüğüyle düzeltilmiştir, 'ham_metin' tanıyıcının ilk "
                       "çıktısı, 'motor' duyu|tarayici|yazi.",
        "inputSchema": {"type": "object", "properties": {
            "no": {"type": "integer", "description": "beklenecek tahta komutunun numarası (yoksa söz beklenir)"}}},
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
        "name": "ses_yeniden_baslat",
        "description": "Pocket (doğal Türkçe ses) işçisini kapatıp yeniden açar. tahtayi_ac ya da tahta_durumu 'ses' alanında "
                       "Pocket'in yüklenemediğini söylüyorsa ve kullanıcı bir düzeltme yaptıysa (ör. KUR'u yeniden çalıştırdı) "
                       "kullan; sunucu penceresini kapatmak gerekmez. Yükleme ~1 dk sürer, o arada yedek ses konuşur.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "durdur",
        "description": "Anlatımı hemen keser ve sıradaki komutları iptal eder.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]
