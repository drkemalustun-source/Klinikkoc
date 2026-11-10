"""KlinikKoç temel testleri. Çalıştırma:  python -m unittest discover -s tools/testler -v

Yalnız Python'un kendi kitaplığını kullanır; anlam araması sahte bir modelle denenir.
"""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zlib

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(KOK, "tools"))

import bilgi_bankasi  # noqa: E402
import karne  # noqa: E402
import vaka_denetle  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ornek_ders  # noqa: E402


def setUpModule():
    ornek_ders.kur()


def tearDownModule():
    ornek_ders.kaldir()


def _metin_yaz(yol, metin, **ek):
    with open(yol, "w", encoding="utf-8", **ek) as f:
        f.write(metin)


def _metin_oku(yol):
    """Dosyayı okuyup hemen kapatır (açık kalan dosya Windows'ta kilitlenmeye yol açar)."""
    with open(yol, encoding="utf-8") as f:
        return f.read()


def _json_oku(yol):
    with open(yol, encoding="utf-8") as f:
        return json.load(f)


ORNEK_VAKA = os.path.join(KOK, "ornek-dersler", "peri-implantitis-cerrahi", "vakalar", "ornek-implant-kanama.json")


class SahteModel:
    """Harf üçlülerinden vektör: anlamı değil, yazım benzerliğini yakalar. Karma aramanın akışını sınamaya yeter."""
    hazir = True
    ad = "sahte"
    BOYUT = 64

    def _v(self, m):
        v = [0.0] * self.BOYUT
        m = bilgi_bankasi.kucuk(m)
        for i in range(len(m) - 2):
            v[zlib.crc32(m[i:i + 3].encode()) % self.BOYUT] += 1
        n = sum(x * x for x in v) ** 0.5 or 1
        return [x / n for x in v]

    def vektorler(self, metinler):
        return [self._v(m) for m in metinler]

    def sorgu_vektoru(self, s):
        return self._v(s)


class BilgiBankasi(unittest.TestCase):
    def setUp(self):
        self.gecici = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.gecici.name, "bilgi.sqlite")

    def tearDown(self):
        self.gecici.cleanup()

    def test_turkce_kucuk_harf_ve_sorgu(self):
        self.assertEqual(bilgi_bankasi.kucuk("IŞIK İltihabı"), "ışık iltihabı")
        self.assertEqual(bilgi_bankasi.fts_sorgusu("İltihabı"), '"iltih"*')
        self.assertEqual(bilgi_bankasi.fts_sorgusu("a"), "")

    def test_hafif_kok_bulucu(self):
        ok = bilgi_bankasi.onekler
        self.assertEqual(ok("apsede"), ["apse"])      # 5 harflik önek "apsed" yalın "apse"yi kaçırırdı
        self.assertEqual(ok("apseler"), ["apse"])
        self.assertEqual(ok("dişlerin"), ["diş"])
        self.assertEqual(ok("hastaya"), ["hasta"])
        self.assertEqual(ok("kaybı")[:2], ["kayb", "kayıp"])  # ünlü düşmesi
        self.assertIn("kayb", ok("kayıp"))
        self.assertEqual(ok("periodontitis"), ["perio"])  # uzun sözcükte önceki davranış korunur
        self.assertEqual(ok("kanal"), ["kanal"])
        self.assertEqual(bilgi_bankasi.fts_sorgusu("apsede drenaj"), '"apse"* OR "drena"*')

    def test_parcalama_ortusur(self):
        p = bilgi_bankasi.parcala(" ".join(str(i) for i in range(250)), n=100, ortusme=20)
        self.assertEqual(len(p), 3)
        self.assertTrue(p[1].startswith("80 "))

    def test_sozcuk_aramasi_ve_kaynak(self):
        bilgi_bankasi.dizinle(yol=self.db, sessiz=True)
        r = bilgi_bankasi.ara("keratinize mukoza", yol=self.db, k=5)
        self.assertTrue(r)
        self.assertTrue(any("eratinize" in x["metin"] for x in r))
        self.assertEqual(r[0]["yontem"], "sözcük")

    def test_suzgec_ders_ve_tur(self):
        bilgi_bankasi.dizinle(yol=self.db, sessiz=True)
        r = bilgi_bankasi.ara("implant", ders="peri-implantitis-cerrahi", tur="vaka", yol=self.db)
        self.assertTrue(r)
        self.assertTrue(all(x["tur"] == "vaka" and x["ders"] == "peri-implantitis-cerrahi" for x in r))

    def test_karma_arama_anlam_ile(self):
        m = SahteModel()
        bilgi_bankasi.dizinle(model=m, yol=self.db, sessiz=True)
        r = bilgi_bankasi.ara("destekleyici bakıma uyum", model=m, yol=self.db, k=5)
        self.assertTrue(any("anlam" in x["yontem"] for x in r))
        self.assertTrue(any(set(x["yontem"].split("+")) == {"sözcük", "anlam"} for x in r))

    # ---- Dayanak etiketi ----
    DERS_DISI = "Diş beyazlatmada hangi jel daha etkilidir?"

    def ders_cumlesi(self):
        """Dersin kendi anlatımından uzunca bir cümle."""
        with open(os.path.join(KOK, "lessons", "peri-implantitis-cerrahi", "ders.json"), encoding="utf-8") as f:
            d = json.load(f)
        for s in d["sections"]:
            for st in s.get("steps", []):
                c = bilgi_bankasi.duz(st.get("say"))
                if len(c.split()) >= 12:
                    return c
        self.fail("derste cümle yok")

    def test_dayanak_model_kapaliyken(self):
        bilgi_bankasi.dizinle(yol=self.db, sessiz=True)
        r, oz = bilgi_bankasi.ara_ve_dayanak(self.DERS_DISI, yol=self.db)
        self.assertTrue(r)  # RRF yine sonuç döndürür; dayanak etiketi bunu ayırt etmeli
        self.assertNotEqual(oz["dayanak"], "guclu")
        self.assertFalse(oz["anlam_aramasi"])
        self.assertIsNone(oz["en_iyi_benzerlik"])
        self.assertTrue(all("sozcuk_eslesti" in x and "sozcuk_kapsami" in x for x in r))
        self.assertEqual(bilgi_bankasi.ara_ve_dayanak("Karnıyarık nasıl yapılır?", yol=self.db)[1]["dayanak"], "yok")
        self.assertEqual(bilgi_bankasi.ara_ve_dayanak(self.ders_cumlesi(), yol=self.db)[1]["dayanak"], "guclu")

    def test_dayanak_anlam_ile(self):
        m = SahteModel()
        bilgi_bankasi.dizinle(model=m, yol=self.db, sessiz=True)
        r, oz = bilgi_bankasi.ara_ve_dayanak(self.DERS_DISI, model=m, yol=self.db)
        self.assertNotEqual(oz["dayanak"], "guclu")
        self.assertTrue(oz["anlam_aramasi"])
        self.assertIsNotNone(oz["en_iyi_benzerlik"])
        self.assertTrue(all("anlam_benzerligi" in x for x in r if "anlam" in x["yontem"]))
        self.assertEqual(bilgi_bankasi.ara_ve_dayanak(self.ders_cumlesi(), model=m, yol=self.db)[1]["dayanak"], "guclu")

    def test_dayanak_dolgu_sozcukleri_sayilmaz(self):
        self.assertEqual(bilgi_bankasi.anlamli_sozcukler("Hangi jel daha etkili, nasıl?"), ["jel", "etkili"])
        self.assertEqual(bilgi_bankasi.dayanak([])["dayanak"], "yok")

    def test_dayanak_esigi_ortam_degiskeniyle(self):
        os.environ["KLINIK_KOC_DENEME_ESIK"] = "0.5"
        try:
            self.assertEqual(bilgi_bankasi._esik("DENEME_ESIK", 0.9), 0.5)
        finally:
            del os.environ["KLINIK_KOC_DENEME_ESIK"]
        self.assertEqual(bilgi_bankasi._esik("YOK_BOYLE_ESIK", 0.9), 0.9)

    def test_degismeyen_ders_atlanir(self):
        bilgi_bankasi.dizinle(yol=self.db, sessiz=True)
        r = bilgi_bankasi.dizinle(yol=self.db, sessiz=True)
        self.assertTrue(all(x["durum"] == "güncel" for x in r))


class VakaDenetimi(unittest.TestCase):
    def kart(self, degistir):
        v = _json_oku(ORNEK_VAKA)
        degistir(v)
        klasor = tempfile.mkdtemp()
        yol = os.path.join(klasor, v["id"] + ".json")
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(v, f, ensure_ascii=False)
        return vaka_denetle.denetle(yol)

    def test_ornek_vaka_gecer(self):
        H, U, _ = vaka_denetle.denetle(ORNEK_VAKA)
        self.assertEqual(H, [])

    def test_gercek_vakada_anonimlik_zorunlu(self):
        H, _, _ = self.kart(lambda v: v.update(kurgusal=False))
        self.assertTrue(any("anonimlik" in h for h in H))

    def test_tam_yas_ve_tarih_yakalanir(self):
        def d(v):
            v["kurgusal"] = False
            v["anonimlik"] = {"kimliksizlestirildi": True, "egitim_onayi": True, "denetleyen": "KÜ", "tarih": "2026-11-06"}
            v["hasta"]["yas_araligi"] = "54"
            v["basvuru"]["oyku"] = "03.05.2025 tarihinde başvurdu."
        H, _, _ = self.kart(d)
        self.assertTrue(any("yas_araligi" in h for h in H))
        self.assertTrue(any("tarih" in h for h in H))

    def test_kopuk_baglanti_ve_sonsuz_yol(self):
        def d(v):
            v["dugumler"][1]["secenekler"][1]["sonraki"] = "olmayan"
        H, _, _ = self.kart(d)
        self.assertTrue(any("olmayan düğüme" in h for h in H))
        self.assertTrue(any("sona varılamıyor" in h for h in H))

    def test_acik_uclu_rubrik_ister(self):
        H, _, _ = self.kart(lambda v: v["dugumler"][2].pop("rubrik"))
        self.assertTrue(any("rubrik" in h for h in H))


class Karne(unittest.TestCase):
    def test_hesap(self):
        kayit = {"ogrenci": "Deneme", "ders": "x", "hedefler": {}, "cevaplar": [
            {"soru": "a", "hedef": "H1", "bloom": "hatirla", "puan": 1, "en_yuksek": 1, "ilk_deneme": True},
            {"soru": "b", "hedef": "H1", "bloom": "hatirla", "puan": 1, "en_yuksek": 1, "ilk_deneme": True},
            {"soru": "c", "hedef": "H2", "bloom": "cozumle", "puan": 1, "en_yuksek": 4, "ilk_deneme": True,
             "eksik_olcutler": ["gerekçe"]},
            {"soru": "d", "hedef": "H2", "bloom": "cozumle", "puan": 0, "en_yuksek": 1, "tehlikeli": True, "vaka": "v1", "dugum": "n"}]}
        hed = [{"id": "H1", "baslik": "bir", "bloom": "hatirla"}, {"id": "H2", "baslik": "iki", "bloom": "cozumle"},
               {"id": "H3", "baslik": "üç"}]
        k = karne.hesapla(kayit, hed, "2026-11-06")
        self.assertEqual(k["guclu"], ["H1"])
        self.assertEqual(k["gelistirilecek"], ["H2"])
        self.assertEqual(k["yoklanmayan"], ["H3"])
        self.assertEqual([b["duzey"] for b in k["bloom"]], ["hatirla", "cozumle"])
        self.assertAlmostEqual(k["bloom"][1]["oran"], 0.2)
        self.assertEqual(len(k["tehlikeli_secimler"]), 1)
        self.assertEqual(k["sorular"][0]["gucluk"], "zor")
        md = karne.markdown(k, "Ders", "2026-11-06")
        self.assertIn("Çözümle", md)
        self.assertIn("zarar verebilecek", md)


class McpSunucusu(unittest.TestCase):
    def test_araclar_ve_karne(self):
        with tempfile.TemporaryDirectory() as d:
            ortam = dict(os.environ, KLINIK_KOC_KAYIT=os.path.join(d, "kayit"), KLINIK_KOC_DIZIN=os.path.join(d, "b.sqlite"))
            p = subprocess.Popen([sys.executable, os.path.join(KOK, "tools", "tahta-mcp.py")], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, env=ortam)
            no = [0]

            def cagir(yontem, params=None):
                no[0] += 1
                p.stdin.write((json.dumps({"jsonrpc": "2.0", "id": no[0], "method": yontem, "params": params or {}}) + "\n").encode())
                p.stdin.flush()
                return json.loads(p.stdout.readline())["result"]

            def arac(ad, **arg):
                r = cagir("tools/call", {"name": ad, "arguments": arg})
                self.assertFalse(r.get("isError"), r)
                return json.loads(r["content"][-1]["text"])

            try:
                self.assertEqual(cagir("initialize")["serverInfo"]["name"], "klinik-koc")
                adlar = {t["name"] for t in cagir("tools/list")["tools"]}
                self.assertTrue({"bilgi_ara", "vakalar", "vaka_oku", "karne", "kayit_yaz", "anlatima_devam"} <= adlar)
                self.assertTrue(arac("bilgi_ara", sorgu="süpürasyon", k=3)["sonuclar"])
                dd = arac("bilgi_ara", sorgu="Diş beyazlatmada hangi jel daha etkilidir?")
                self.assertIn(dd["dayanak"], ("yok", "zayif"))
                self.assertIn("talimat", dd)
                self.assertEqual(arac("bilgi_ara", sorgu="Karnıyarık nasıl yapılır?")["dayanak"], "yok")
                self.assertEqual(arac("vakalar", ders="peri-implantitis-cerrahi")["vakalar"][0]["vaka"], "ornek-implant-kanama")
                self.assertIn("talimat", arac("vaka_oku", ders="peri-implantitis-cerrahi", vaka="ornek-implant-kanama"))
                arac("kayit_yaz", ogrenci="Test Öğrenci", ders="peri-implantitis-cerrahi", cevaplar=[
                    {"soru": "Tanı", "vaka": "ornek-implant-kanama", "dugum": "tani", "hedef": "H2.b", "bloom": "uygula",
                     "tur": "vaka_karar", "puan": 1, "en_yuksek": 1, "ilk_deneme": True}])
                k = arac("karne", ogrenci="Test Öğrenci", ders="peri-implantitis-cerrahi", yaz=True)
                self.assertEqual(k["karne"]["cevap_sayisi"], 1)
                self.assertTrue(os.path.exists(os.path.join(d, "kayit", "test-ogrenci", "karneler")))
                # Sözlü prova: vakanın açık uçlu düğümü hazır sorular arasında, rubriğiyle
                s = arac("sozlu_prova", ders="peri-implantitis-cerrahi", ogrenci="Test Öğrenci", soru_sayisi=12)
                self.assertIn("talimat", s)
                self.assertTrue(any(m.get("vaka") == "ornek-implant-kanama" and m.get("rubrik") for m in s["hazir_sorular"]))
                # Dersler arası tekrar: düşük puanlı hedef listeye girer
                self.assertEqual(arac("tekrar_listesi", ogrenci="Test Öğrenci")["liste"], [])
                arac("kayit_yaz", ogrenci="Test Öğrenci", ders="peri-implantitis-cerrahi", cevaplar=[
                    {"soru": "Prognoz", "hedef": "H4.a", "bloom": "cozumle", "tur": "sozlu", "puan": 1, "en_yuksek": 5}])
                t = arac("tekrar_listesi", ogrenci="Test Öğrenci")
                self.assertEqual(t["liste"][0]["hedef"], "H4.a")
                self.assertEqual(t["liste"][0]["ders"], "peri-implantitis-cerrahi")
            finally:
                p.stdin.close()
                p.wait(timeout=10)
                p.stdout.close()


class CanliSozKesme(unittest.TestCase):
    """Canlı tahta: kullanıcının sesli sözü Claude'a anlatım bitmeden ulaşır."""

    def setUp(self):
        import threading
        import time
        sys.path.insert(0, os.path.join(KOK, "tools"))
        import sunucu
        self.th, self.time = threading, time
        self.c = sunucu.Canli()
        self.c.son_gorulme = time.time()  # sayfa bağlı say
        self.c.bekleyen_sayfa = 1

    def sonra(self, sn, f, *a):
        t = self.th.Timer(sn, f, a)
        t.start()
        return t

    def test_anlatim_surerken_konusunca_hemen_doner(self):
        self.c.sayfa_durumu = {"kaldigi_yer": {"no": 1, "adim": 2, "toplam": 4}}
        self.sonra(0.3, self.c.soyle, "periapikal apseden farkı ne")
        t0 = self.time.time()
        r = self.c.gonder({"tur": "adimlar", "adimlar": [{"anlat": "uzun anlatım"}]}, 40)
        self.assertLess(self.time.time() - t0, 3)
        self.assertEqual(r["durum"], "kullanici_konustu")
        self.assertEqual(r["kullanici_konustu"], "periapikal apseden farkı ne")
        self.assertEqual(r["kaldigi_yer"]["adim"], 2)
        self.assertIn("anlatima_devam", r["not"])
        self.assertEqual(self.c.konusmalar, [])  # bir kez teslim edilir

    def test_bekleyen_tahta_durumu_da_hemen_doner(self):
        self.c.gonder({"tur": "adimlar", "adimlar": []}, 0)
        self.sonra(0.3, self.c.soyle, "bir saniye")
        r = self.c.sonuc(1, 40)
        self.assertEqual(r["durum"], "kullanici_konustu")

    def test_soru_kartinda_not_farkli(self):
        self.sonra(0.3, self.c.soyle, "anlamadım")
        r = self.c.gonder({"tur": "soru", "soru": "?", "secenekler": ["a", "b"]}, 40)
        self.assertIn("soru kartı", r["not"])

    def test_cevaplanmamis_soz_varken_yeni_komut_gitmez(self):
        self.c.soyle("bir sorum var")
        r = self.c.gonder({"tur": "adimlar", "adimlar": []}, 1)
        self.assertTrue(r.get("gonderilmedi"))
        self.assertEqual(r["kullanici_konustu"], "bir sorum var")
        self.assertEqual(self.c.kuyruk, [])
        # devam ve dur her zaman gider
        self.c.soyle("yine")
        self.c.gonder({"tur": "devam"}, 0)
        self.assertEqual(self.c.kuyruk[-1]["tur"], "devam")

    def test_durum_bekleyen_metni_verir(self):
        self.c.soyle("tahtaya bak")
        d = self.c.durum()
        self.assertEqual(d["konusma_bekleyen"], 1)
        self.assertNotIn("kullanici_konustu", d)  # yalnız bakmak sözü tüketmez
        d = self.c.durum(al=True)
        self.assertEqual(d["kullanici_konustu"], "tahtaya bak")
        self.assertEqual(d["bekleyen_konusmalar"][0]["metin"], "tahtaya bak")
        self.assertEqual(self.c.konusmalar, [])

    def test_dinliyor_isigi(self):
        self.assertFalse(self.c.soyle("x")["claude_dinliyor"])
        self.c.birak_konusmalari()
        self.c.gonder({"tur": "adimlar", "adimlar": []}, 0)
        self.sonra(0.2, lambda: self.assertTrue(self.c.dinliyor()))
        self.c.sonuc(1, 0.6)
        r = self.c.al(1, 0.5, sayfa_dinliyor=True, sayfa_bekleyen=0)
        self.assertFalse(r["dinliyor"])

    def test_kanal_arac_beklerken_sozu_almaz(self):
        sonuc = {}
        self.c.dinleyen = 1  # Claude dinle ile bekliyor
        self.c.soyle("merhaba")
        t = self.th.Thread(target=lambda: sonuc.update(self.c.kanal(1.5)))
        t.start()
        t.join()
        self.assertEqual(sonuc["durum"], "sessiz")
        self.c.dinleyen = 0
        r = self.c.kanal(3)
        self.assertEqual((r["durum"], r["metin"]), ("konustu", "merhaba"))


class CanliKanal(unittest.TestCase):
    """--kanal: Claude dinlemiyorken söz, Claude Code oturumuna notifications/claude/channel olarak düşer."""

    def test_soz_bildirim_olarak_gider(self):
        import http.server
        import threading
        import urllib.request
        sys.path.insert(0, os.path.join(KOK, "tools"))
        import sunucu
        sunucu.CANLI = sunucu.Canli()
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), sunucu.Isleyici)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        port = srv.server_address[1]
        ortam = dict(os.environ, KLINIK_KOC_PORT=str(port))
        p = subprocess.Popen([sys.executable, os.path.join(KOK, "tools", "tahta-mcp.py"), "--kanal"],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=ortam)
        try:
            p.stdin.write(b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n')
            p.stdin.flush()
            ilk = json.loads(p.stdout.readline())["result"]
            self.assertEqual(ilk["capabilities"]["experimental"], {"claude/channel": {}})
            p.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
            p.stdin.flush()
            import time
            for _ in range(50):
                if sunucu.CANLI.kanal_bekleyen:
                    break
                time.sleep(0.1)
            r = urllib.request.Request("http://127.0.0.1:%d/api/canli/soyle" % port,
                                       data=json.dumps({"metin": "lezyon neden ağrılı"}).encode(),
                                       headers={"Content-Type": "application/json"})
            self.assertTrue(json.loads(urllib.request.urlopen(r, timeout=5).read())["claude_dinliyor"])
            m = json.loads(p.stdout.readline())
            self.assertEqual(m["method"], "notifications/claude/channel")
            self.assertEqual(m["params"]["content"], "lezyon neden ağrılı")
            self.assertEqual(sunucu.CANLI.konusmalar, [])
        finally:
            p.stdin.close()
            p.kill()
            p.wait(timeout=10)
            p.stdout.close()
            srv.shutdown()
            srv.server_close()

    def test_kanalsiz_yetenek_yok(self):
        p = subprocess.run([sys.executable, os.path.join(KOK, "tools", "tahta-mcp.py")],
                           input=b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n', capture_output=True, timeout=20)
        self.assertNotIn("experimental", json.loads(p.stdout.splitlines()[0])["result"]["capabilities"])


class Video(unittest.TestCase):
    """Ders klasöründeki videolar listelenir, tahta komutunda kimlik dosya yoluna çevrilir, sunucu parça parça verir."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("tahta_mcp", os.path.join(KOK, "tools", "tahta-mcp.py"))
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.gecici = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.gecici, "lessons", "deneme", "videolar"))
        with open(os.path.join(self.gecici, "lessons", "deneme", "videolar", "nug klip.mp4"), "wb") as f:
            f.write(bytes(range(256)) * 40)
        with open(os.path.join(self.gecici, "lessons", "deneme", "videolar", "videolar.json"), "w", encoding="utf-8") as f:
            json.dump({"nug klip.mp4": {"baslik": "NUG muayenesi", "credit": "K. Üstün"}}, f)
        with open(os.path.join(self.gecici, "lessons", "deneme", "egitmen.json"), "w", encoding="utf-8") as f:
            json.dump({"baslik": "Deneme", "videolar": {"yt": {"youtube": "https://youtu.be/dQw4w9WgXcQ", "baslik": "Açık video"}}}, f)
        self.m.KOK = self.gecici

    def test_liste_ve_cozum(self):
        v = self.m.ders_videolari("deneme")
        self.assertEqual(v["nug klip"]["src"], "/lessons/deneme/videolar/nug%20klip.mp4")
        self.assertFalse(v["nug klip"]["internet"])
        self.assertTrue(v["yt"]["internet"])
        adimlar = [{"komutlar": [{"type": "video", "video": "nug klip", "bitis": 3}, {"type": "video", "video": "yt"}]}]
        self.m.videolari_coz(adimlar, "deneme")
        a, b = adimlar[0]["komutlar"]
        self.assertEqual((a["src"], a["bitis"], a["caption"], a["credit"]), ("/lessons/deneme/videolar/nug%20klip.mp4", 3, "NUG muayenesi", "K. Üstün"))
        self.assertNotIn("video", a)
        self.assertEqual(b["youtube"], "https://youtu.be/dQw4w9WgXcQ")
        with self.assertRaises(ValueError):
            self.m.videolari_coz([{"komutlar": [{"type": "video", "video": "yok"}]}], "deneme")

    def test_sunucu_parca_verir(self):
        import http.server
        import threading
        import urllib.request
        sys.path.insert(0, os.path.join(KOK, "tools"))
        import sunucu
        eski = sunucu.KOK
        sunucu.KOK = self.gecici
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), sunucu.Isleyici)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            url = "http://127.0.0.1:%d/lessons/deneme/videolar/nug%%20klip.mp4" % srv.server_address[1]
            r = urllib.request.urlopen(urllib.request.Request(url, headers={"Range": "bytes=256-511"}), timeout=5)
            self.assertEqual(r.status, 206)
            self.assertEqual(r.headers["Content-Range"], "bytes 256-511/10240")
            self.assertEqual(r.headers["Content-Type"], "video/mp4")
            self.assertEqual(r.read(), bytes(range(256)))
            r.close()
            with urllib.request.urlopen(url, timeout=5) as r:
                self.assertEqual((r.status, len(r.read()), r.headers["Accept-Ranges"]), (200, 10240, "bytes"))
        finally:
            srv.shutdown()
            srv.server_close()
            sunucu.KOK = eski


class Kayitlar(unittest.TestCase):
    """Öğrenci kayıtları: taşıma, atomik yazma, bozuk dosyadan kurtarma, aynı ad, deneme kaydı, aktarma."""

    def setUp(self):
        import importlib.util
        import kayit_deposu
        import kayit_aktar
        self.kd, self.ka = kayit_deposu, kayit_aktar
        self.gecici = tempfile.TemporaryDirectory()
        self.d = os.path.join(self.gecici.name, "Application Support", "Klinik Koc")  # boşluklu yol
        self.eski = os.path.join(self.gecici.name, "eski program", "kayitlar")
        spec = importlib.util.spec_from_file_location("tahta_mcp_kayit", os.path.join(KOK, "tools", "tahta-mcp.py"))
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.m.KAYIT_KOK = os.path.join(self.d, "kayitlar")
        self.m.ESKI_KAYIT_KOK = self.eski
        self.m._DEPO = None
        self.eski_ortam = os.environ.pop("KLINIK_KOC_KAYIT", None)

    def tearDown(self):
        if self.eski_ortam is not None:
            os.environ["KLINIK_KOC_KAYIT"] = self.eski_ortam
        self.gecici.cleanup()

    def arac(self, ad, **a):
        r = self.m.ISLEYICILER[ad](a)
        t = r["content"][0]["text"]
        if r.get("isError"):
            raise AssertionError(t)
        return json.loads(t)

    def yaz_json(self, yol, veri):
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False)

    def test_kalici_yer_ortam_degiskeni_once(self):
        import veri_yeri
        os.environ["KLINIK_KOC_KAYIT"] = os.path.join(self.gecici.name, "özel yer")
        try:
            self.assertEqual(veri_yeri.kayit_kok(), os.path.join(self.gecici.name, "özel yer"))
        finally:
            del os.environ["KLINIK_KOC_KAYIT"]
        self.assertTrue(veri_yeri.kayit_kok().endswith(os.path.join("KlinikKoc", "kayitlar")))
        self.assertNotIn(KOK, veri_yeri.kayit_kok())

    def test_eski_yerden_bir_kez_tasima_silmeden(self):
        ders = "peri-implantitis-cerrahi"
        self.yaz_json(os.path.join(self.eski, "ayse-yilmaz", ders + ".json"),
                      {"ogrenci": "Ayşe Yılmaz", "ders": ders, "hedefler": {"H1.1": {"durum": "bagimsiz_yapti"}},
                       "yanilgilar": {}, "guven": [], "sorular": [], "testler": [], "oturumlar": [{"tarih": "2026-11-01"}]})
        os.makedirs(os.path.join(self.eski, "ayse-yilmaz", "raporlar"))
        _metin_yaz(os.path.join(self.eski, "ayse-yilmaz", "raporlar", "r.md"), "rapor")
        k = self.arac("kayit_oku", ogrenci="Ayşe Yılmaz", ders=ders)
        self.assertEqual(k["oturum_sayisi"], 1)
        yeni = os.path.join(self.d, "kayitlar", "ayse-yilmaz")
        self.assertTrue(os.path.exists(os.path.join(yeni, ders + ".json")))
        self.assertTrue(os.path.exists(os.path.join(yeni, "raporlar", "r.md")))
        self.assertTrue(os.path.exists(os.path.join(self.eski, "ayse-yilmaz", ders + ".json")), "eski dosya silinmemeli")
        self.assertTrue(os.path.exists(os.path.join(self.eski, "TASINDI.txt")))
        # ikinci açılışta yeniden taşımaz: eskide değişen dosya yenisinin üstüne yazılmaz
        self.yaz_json(os.path.join(self.eski, "ayse-yilmaz", ders + ".json"), {"ogrenci": "x", "ders": ders})
        depo = self.kd.Depo(os.path.join(self.d, "kayitlar"), self.eski)
        depo.hazirla()
        self.assertIsNone(depo.tasima_raporu)
        self.assertEqual(_json_oku(os.path.join(yeni, ders + ".json"))["ogrenci"], "Ayşe Yılmaz")

    def test_atomik_yazma_ve_bes_yedek(self):
        yol = os.path.join(self.d, "kayitlar", "a-1", "d.json")
        for i in range(8):
            self.kd.atomik_yaz(yol, {"n": i})
        self.assertEqual(_json_oku(yol)["n"], 7)
        y = self.kd.yedekler(yol)
        self.assertEqual(len(y), 5)
        self.assertEqual(_json_oku(y[0])["n"], 6)  # en yeni yedek bir önceki sürüm
        self.assertFalse([a for a in os.listdir(os.path.dirname(yol)) if a.endswith(".tmp")])

    def test_bozuk_dosya_yedekten_acilir(self):
        ders = "peri-implantitis-cerrahi"
        self.arac("egitmen_hazirla", ders=ders, ogrenci="Can Demir", ayirt="123")
        self.arac("kayit_yaz", ogrenci="can-demir-123", ders=ders, mola="bölüm 2")
        self.arac("kayit_yaz", ogrenci="can-demir-123", ders=ders, mola="bölüm 3")
        yol = os.path.join(self.d, "kayitlar", "can-demir-123", ders + ".json")
        _metin_yaz(yol, '{"ogrenci": "Can", "hedef')  # yarım kalmış yazım
        k = self.arac("kayit_oku", ogrenci="can-demir-123", ders=ders)
        self.assertEqual(k["mola"], "bölüm 2")
        self.assertTrue(any("yedekten" in u for u in k["uyarilar"]))
        self.assertTrue([a for a in os.listdir(os.path.dirname(yol)) if ".bozuk-" in a], "bozuk dosya saklanmalı")
        self.assertEqual(_json_oku(yol)["mola"], "bölüm 2")  # geri yazıldı

    def test_kalici_kimlik_ve_ayni_ad(self):
        ders = "peri-implantitis-cerrahi"
        r = self.arac("egitmen_hazirla", ders=ders, ogrenci="Elif Kaya")
        self.assertEqual(r["ogrenci"]["durum"], "ayirt_gerekli")
        r = self.arac("egitmen_hazirla", ders=ders, ogrenci="Elif Kaya", ayirt="042")
        kim = r["ogrenci"]["kimlik"]
        self.assertEqual(kim, "elif-kaya-042")
        self.arac("kayit_yaz", ogrenci=kim, ders=ders, mola="m1")
        # aynı ad + aynı ayırt edici → aynı kayıt, soru yok
        self.assertEqual(self.arac("egitmen_hazirla", ders=ders, ogrenci="elif kaya", ayirt="042")["ogrenci"]["kimlik"], kim)
        # aynı ad, başka ayırt edici → "Bu adla kayıt var, sen misin?"
        r = self.arac("egitmen_hazirla", ders=ders, ogrenci="Elif Kaya", ayirt="777")
        self.assertEqual(r["ogrenci"]["durum"], "ayni_ad_var")
        self.assertIn("sen misin", r["ogrenci"]["soru"])
        self.assertEqual([x["kimlik"] for x in r["ogrenci"]["kayitlar"]], [kim])
        # hayır: ayrı kayıt
        r = self.arac("egitmen_hazirla", ders=ders, ogrenci="Elif Kaya", ayirt="777", yeni_ogrenci=True)
        kim2 = r["ogrenci"]["kimlik"]
        self.assertNotEqual(kim2, kim)
        self.assertIsNone(r["ogrenci"]["kayit"]["mola"])
        # artık ad tek başına belirsiz: araçlar kimlik ister
        with self.assertRaises(self.kd.AyniAdBelirsiz):
            self.arac("kayit_oku", ogrenci="Elif Kaya", ders=ders)
        self.assertEqual(self.arac("kayit_oku", ogrenci=kim, ders=ders)["mola"], "m1")
        # evet: kimlikle devam
        self.assertEqual(self.arac("egitmen_hazirla", ders=ders, ogrenci_kimligi=kim)["ogrenci"]["kayit"]["mola"], "m1")

    def test_eski_ada_gore_kayit_okunur_ve_baglanir(self):
        ders = "peri-implantitis-cerrahi"
        kok = os.path.join(self.d, "kayitlar")
        self.yaz_json(os.path.join(kok, "mert-oz", ders + ".json"),
                      {"ogrenci": "Mert Öz", "ders": ders, "olusturma": "2026-10-01", "mod": "once_anlat",
                       "hedefler": {}, "yanilgilar": {}, "guven": [], "sorular": [], "testler": [],
                       "oturumlar": [], "mola": "eski mola", "cevaplar": [], "vakalar": []})
        self.assertEqual(self.arac("kayit_oku", ogrenci="Mert Öz", ders=ders)["mola"], "eski mola")
        r = self.arac("egitmen_hazirla", ders=ders, ogrenci="Mert Öz", ayirt="55")
        self.assertEqual(r["ogrenci"]["durum"], "ayni_ad_var")
        self.assertTrue(r["ogrenci"]["kayitlar"][0]["eski_kayit"])
        r = self.arac("egitmen_hazirla", ders=ders, ogrenci_kimligi="mert-oz", ayirt="55")
        self.assertEqual(r["ogrenci"]["kayit"]["mola"], "eski mola")
        # artık ad + ayırt edici doğrudan eski klasöre gider
        self.assertEqual(self.arac("egitmen_hazirla", ders=ders, ogrenci="Mert Öz", ayirt="55")["ogrenci"]["kimlik"], "mert-oz")

    def test_ipucu_merdiveni_ve_aralikli_tekrar(self):
        yk = self.m.yeni_kutu
        # iskele yoksa eski kural aynen
        self.assertEqual((yk(2, True, True), yk(2, True, False), yk(3, False, True)), (3, 1, 1))
        # S0 doğru bir üst kutu; S1 doğru kutuyu korur; S2–S4 ya da yanlış 1. kutu
        self.assertEqual([yk(2, True, False, s) for s in self.m.ISKELE], [3, 2, 1, 1, 1])
        self.assertEqual((yk(0, True, False, "S1"), yk(4, True, True, "S0"), yk(3, False, True, "S0")), (1, 4, 1))
        ders = "peri-implantitis-cerrahi"
        kim = self.arac("egitmen_hazirla", ders=ders, ogrenci="Ece Su", ayirt="12")["ogrenci"]["kimlik"]
        h = lambda iskele, **x: dict({"id": "H1.a", "duzey": "hatirla", "dogru": True, "iskele": iskele,
                                      "kanit": "deneme"}, **x)
        self.arac("kayit_yaz", ogrenci=kim, ders=ders, hedefler=[h("S0")])
        self.arac("kayit_yaz", ogrenci=kim, ders=ders, hedefler=[h("S0")])
        v = self.m.kayit_yukle(kim, ders)["hedefler"]["H1.a"]
        self.assertEqual((v["kutu"], v["kanitlar"][-1]["iskele"], v["kanitlar"][-1]["yardim"]), (2, "S0", "yardimsiz"))
        self.arac("kayit_yaz", ogrenci=kim, ders=ders, hedefler=[h("S1")])
        v = self.m.kayit_yukle(kim, ders)["hedefler"]["H1.a"]
        self.assertEqual((v["kutu"], v["kanitlar"][-1]["yardim"]), (2, "destekle"))
        # çelişen yardım uyarı verir, iskele esas alınır; geçersiz basamak uyarı verir
        r = self.arac("kayit_yaz", ogrenci=kim, ders=ders, hedefler=[h("S3", yardim="yardimsiz"), h("S9")])
        self.assertEqual(len(r["uyarilar"]), 2)
        self.assertEqual(self.m.kayit_yukle(kim, ders)["hedefler"]["H1.a"]["kutu"], 1)

    def test_deneme_kaydi_ayri(self):
        ders = "peri-implantitis-cerrahi"
        r = self.arac("egitmen_hazirla", ders=ders, ogrenci="deneme")
        self.assertTrue(r["ogrenci"]["deneme"])
        kd_ = r["ogrenci"]["kimlik"]
        cev = [{"soru": "S1", "hedef": "H1.1", "bloom": "hatirla", "tur": "secmeli", "puan": 1, "en_yuksek": 1}]
        self.arac("kayit_yaz", ogrenci=kd_, ders=ders, cevaplar=cev)
        k = self.arac("karne", ogrenci=kd_, ders=ders, yaz=True)
        self.assertTrue(k["karne"]["deneme"])
        self.assertIn("DENEME KAYDI", _metin_oku(k["dosya"]))
        r = self.arac("egitmen_hazirla", ders=ders, ogrenci="Zeynep Ak", ayirt="901")
        self.arac("kayit_yaz", ogrenci=r["ogrenci"]["kimlik"], ders=ders, cevaplar=cev)
        self.assertNotIn("deneme", self.arac("karne", ogrenci="zeynep-ak-901", ders=ders)["karne"])
        a = self.ka.anonim(self.m.depo())
        self.assertEqual((a["ogrenci_sayisi"], a["haric_tutulan_deneme"]), (1, 1))
        a = self.ka.anonim(self.m.depo(), deneme_dahil=True)
        self.assertEqual(sum(1 for x in a["kayitlar"] if x.get("deneme")), 1)
        # bayrakla açılan deneme de ayrılır
        r = self.arac("egitmen_hazirla", ders=ders, ogrenci="Hoca", deneme=True)
        self.assertTrue(r["ogrenci"]["deneme"])

    def test_disa_ice_aktarma_ve_anonim(self):
        ders = "peri-implantitis-cerrahi"
        kim = self.arac("egitmen_hazirla", ders=ders, ogrenci="Ali Veli", ayirt="314")["ogrenci"]["kimlik"]
        self.arac("kayit_yaz", ogrenci=kim, ders=ders, mola="m", hedefler=[
            {"id": "H1.a", "duzey": "hatirla", "yardim": "yardimsiz", "dogru": True, "kanit": "Ali şunu söyledi"}],
            sorular=[{"soru": "Kişisel bir soru"}], cevaplar=[{"soru": "S1", "hedef": "H1.1", "puan": 1, "en_yuksek": 1}])
        self.arac("rapor_yaz", ogrenci=kim, ders=ders, ogretmen_ozeti="Özet.")
        cikti = os.path.join(self.gecici.name, "masa üstü")
        os.makedirs(cikti)
        r = self.arac("kayit_disa_aktar", ogrenci=kim, cikti=cikti)
        self.assertTrue(os.path.isfile(r["dosya"]))
        # başka bilgisayar
        self.m.KAYIT_KOK = os.path.join(self.gecici.name, "ikinci pc", "kayitlar")
        self.m._DEPO = None
        i = self.arac("kayit_ice_aktar", dosya=r["dosya"])
        self.assertEqual((i["kimlik"], i["alinan_dersler"], i["rapor_karne"]), (kim, [ders], 1))
        self.assertEqual(self.arac("kayit_oku", ogrenci=kim, ders=ders)["mola"], "m")
        self.assertEqual(self.arac("egitmen_hazirla", ders=ders, ogrenci="Ali Veli", ayirt="314")["ogrenci"]["kimlik"], kim)
        # buradaki kayıt daha yeniyse dokunmaz
        self.arac("kayit_yaz", ogrenci=kim, ders=ders, mola="yeni")
        self.assertTrue(self.arac("kayit_ice_aktar", dosya=r["dosya"])["atlanan"])
        self.assertEqual(self.arac("kayit_oku", ogrenci=kim, ders=ders)["mola"], "yeni")
        # öğretmen: dosyadan anonim aktarma — ad, kimlik, ayırt edici, serbest metin ve tam tarih yok
        a = self.ka.anonim(dosyalar=[r["dosya"]], cikti=cikti)
        metin_ = _metin_oku(a["dosya"])
        for yasak in ("Ali", "314", kim, "Kişisel", "şunu söyledi", "2026-"):
            self.assertNotIn(yasak, metin_)
        self.assertEqual(a["kayitlar"][0]["dersler"][0]["hedefler"]["H1.a"]["yardimsiz_duzey"], "hatirla")


    def test_olcme_capraz_formlar(self):
        ders = self.olcmeli_ders(capraz=True)
        tek = self.arac("egitmen_hazirla", ders=ders, ogrenci="Can Er", ayirt="513")["ogrenci"]["kimlik"]
        cift = self.arac("egitmen_hazirla", ders=ders, ogrenci="Ece Su", ayirt="512")["ogrenci"]["kimlik"]
        bicim = lambda kim: [self.arac("olcme_testi", ders=ders, ogrenci=kim, tur=t)["form"]  # noqa: E731
                             for t in ("on", "son", "gecikmeli")]
        self.assertEqual(bicim(cift), ["A", "B", "A"])
        self.assertEqual(bicim(tek), ["B", "A", "B"])
        self.arac("olcme_kaydet", ders=ders, ogrenci=tek, tur="on", yanitlar=[{"no": "B1", "secim": 0}])
        k, _ = self.m.depo().yukle(tek, ders)
        self.assertEqual((k["olcme_grubu"], k["testler"][0]["form"], k["testler"][0]["grup"]), (2, "B", 2))
        # çapraz değilse herkes plana uyar
        ders = self.olcmeli_ders(capraz=False, ad="deneme-duz")
        self.assertEqual(bicim(tek), ["A", "B", "A"])

    def olcmeli_ders(self, capraz=False, ad="deneme-olcme"):
        """Klinik olmayan, iki formlu küçük bir ölçme dersi (geçici klasörde)."""
        kok = os.path.join(self.gecici.name, "program")
        self.yaz_json(os.path.join(kok, "lessons", ad, "egitmen.json"), {
            "baslik": "Deneme", "egitmen": "inci", "hedefler": [{"id": "H1", "baslik": "Oynatıcı", "bloom": "anla"}],
            "olcme": {"durum": "onaylandi", "plan": {"on": "A", "son": "B", "gecikmeli": "A", "capraz": capraz},
                      "formlar": {f: [{"no": f + "1", "hedef": "H1", "tur": "secmeli", "soru": "Hangisi bir düğmedir?",
                                       "secenekler": ["Oynat", "Renk", "Gölge"], "dogru": 0},
                                      {"no": f + "2", "hedef": "H1", "tur": "kisa", "soru": "Duraklat ne yapar?",
                                       "olcut": "2: sesi ve adımları durdurur"}] for f in "AB"}}})
        import shutil
        if not os.path.isdir(os.path.join(kok, "egitmenler")):
            shutil.copytree(os.path.join(KOK, "egitmenler"), os.path.join(kok, "egitmenler"))
        self.m.KOK = kok
        return ad

    def test_olcme_ham_yanit_kaydi_ve_anonim(self):
        ders = self.olcmeli_ders()
        kim = self.arac("egitmen_hazirla", ders=ders, ogrenci="Ayşe Kaya", ayirt="512")["ogrenci"]["kimlik"]
        self.arac("olcme_testi", ders=ders, ogrenci=kim, tur="on")
        ham = "duraklatinca ses ve tahta adimlari duruyor, kaldigi yerden devam ediyor"
        r = self.arac("olcme_kaydet", ders=ders, ogrenci=kim, tur="on", yanitlar=[
            {"no": "A1", "secim": 0, "guven": "emin"},
            {"no": "A2", "puan": 2, "yanit_ozet": "durdurur", "ham_yanit": "  " + ham + " ", "guven": "biraz"}])
        self.assertNotIn("uyarilar", r)
        t = self.arac("kayit_oku", ogrenci=kim, ders=ders)
        k, _ = self.m.depo().yukle(kim, ders)
        y = {x["no"]: x for x in k["testler"][0]["yanitlar"]}
        self.assertEqual(y["A2"]["ham_yanit"], ham)
        self.assertNotIn("ham_yanit", y["A1"])
        self.assertTrue(t)
        # ham yanıt eksikse uyarı verir ama kaydeder
        r = self.arac("olcme_kaydet", ders=ders, ogrenci=kim, tur="son", yanitlar=[{"no": "B2", "puan": 1}])
        self.assertTrue(any("ham_yanit" in u for u in r["uyarilar"]))
        # anonim aktarma: ham metin yalnız açıkça istenirse
        self.assertNotIn(ham, json.dumps(self.ka.anonim(self.m.depo()), ensure_ascii=False))
        a = self.ka.anonim(self.m.depo(), ham_yanitlar=True)
        self.assertTrue(a["ham_yanitlar"])
        metin_ = json.dumps(a, ensure_ascii=False)
        self.assertIn(ham, metin_)
        self.assertNotIn("Ayşe", metin_)


class DikteTerimSozlugu(unittest.TestCase):
    """Konuşma tanımanın bozduğu terimler sözlükle düzelir; doğru metne dokunulmaz (gerçek oturum örnekleri)."""

    def setUp(self):
        import terim_sozlugu
        self.t = terim_sozlugu
        self.s = terim_sozlugu.yukle(KOK)

    def test_gercek_ornekler(self):
        for ham, beklenen in (("nekrotizangin gibi test", "nekrotizan gingivitis"),
                              ("nekro tizangin gibi testi", "nekrotizan gingivitis"),
                              ("birleşim epiteliği", "birleşim epiteli")):
            r = self.s.duzelt("Hocam " + ham + " nedir?")
            self.assertIn(beklenen, r["metin"], ham)
            self.assertEqual(r["ham_metin"], "Hocam " + ham + " nedir?")
            self.assertTrue(r["duzeltmeler"])
        self.assertEqual(self.s.duzelt("Birleşim epiteliği hasar görür.")["metin"], "Birleşim epiteli hasar görür.")

    def test_benzerlikle_eslemesiz_de_duzelir(self):
        s = self.t.Sozluk(terimler=["nekrotizan gingivitis", "birleşim epiteli"])
        self.assertEqual(s.duzelt("Hastada nekrotizangin gibi test var")["metin"], "Hastada nekrotizan gingivitis var")
        self.assertIn("nekrotizan gingivitis", s.duzelt("nekro tizangin gibi testi")["metin"])
        self.assertEqual(s.duzelt("nekrotizan gin givitis")["metin"], "nekrotizan gingivitis")

    def test_dogru_metne_dokunmaz(self):
        for m in ("Birleşim epitelinin yapısı", "nekrotizan gingivitisin tedavisi", "periodontal cep derinliği",
                  "Nekrotizan periodontal hastalıklar", "sondlama derinliklerini ölçtüm", "hastada lökosit sayısı",
                  "primer herpetik gingivostomatitisi düşünürüm", "interdental papillerinde krater var",
                  "nekrotizan stomatit (NS) nadirdir"):
            self.assertEqual(self.s.duzelt(m)["metin"], m, m)
        cumleler = _json_oku(os.path.join(KOK, "ses-testi", "cumleler.json"))["cumleler"]
        for c in cumleler:
            self.assertEqual(self.s.duzelt(c["metin"])["duzeltmeler"], [], c["id"])

    def test_ogretmen_kendi_terimini_ekler(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "terimler.json"), "w", encoding="utf-8") as f:
                json.dump({"duzeltmeler": [{"bozuk": "perio kronik", "dogru": "perikoronitis"}]}, f)
            s = self.t.yukle(KOK, d)
            self.assertEqual(s.duzelt("bu bir perio kronik tablo")["metin"], "bu bir perikoronitis tablo")

    def test_ham_metin_ve_motor_claudea_gider(self):
        import sunucu
        c = sunucu.Canli()
        c.soyle("nekrotizan gingivitis nedir", "nekrotizangin gibi test nedir", "duyu")
        r = c.dinle(1)
        self.assertEqual((r["metin"], r["ham_metin"], r["motor"]),
                         ("nekrotizan gingivitis nedir", "nekrotizangin gibi test nedir", "duyu"))
        c.soyle("yazarak sordum", None, "yazi")
        r = c.dinle(1)
        self.assertNotIn("ham_metin", r)
        self.assertEqual(r["motor"], "yazi")
        c.soyle("eski sayfa")  # eski sayfa ham_metin/motor göndermez: alanlar eklenmez
        self.assertEqual(set(c.dinle(1)), {"durum", "metin", "parcalar"})

    def test_uzun_konusma_tek_parca_yaziya_doner(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy yok")
        import sunucu
        sr = 16000
        t = np.arange(int(70 * sr)) / sr
        ses = (0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        for bas in (9.0, 19.5, 31.0, 44.0, 57.5):  # cümle araları
            ses[int(bas * sr):int((bas + 0.4) * sr)] = 0
        parcalar = sunucu.bolumle(ses, sr)
        self.assertGreaterEqual(len(parcalar), 3)
        self.assertTrue(all(len(p) <= sunucu.PARCA_SN * sr for p in parcalar))
        self.assertEqual(sum(len(p) for p in parcalar), len(ses))

        class SahteModel:
            def transcribe(self, s, lang="mix"):
                return "parça %d" % round(len(s) / sr)
        d = sunucu.Duyu()
        d.model = SahteModel()
        r = d.yaz(ses.tobytes(), duzelt=True)
        self.assertEqual(r["parca"], len(parcalar))
        self.assertEqual(r["saniye"], 70.0)
        self.assertEqual(len(r["metin"].split("parça")) - 1, len(parcalar))
        self.assertIn("ham_metin", r)

    def test_olcum_dosyaya_yazilir(self):
        import sunucu
        with tempfile.TemporaryDirectory() as d:
            yol = sunucu.olcum_kaydet({"sonuc": {"tur": "dikte-karsilastirmasi"}, "md": "# x"}, d)
            self.assertTrue(os.path.exists(yol))
            self.assertTrue(os.path.exists(yol[:-5] + ".md"))


class EgitmenSenaryolari(unittest.TestCase):
    """qa-testi/egitmen-senaryolari.json (ve varsa ozel/egitmen-senaryolari-*.json) yapı denetimi."""
    ALANLAR = ("id", "baslik", "egitmen", "ders", "ogrenci_mesajlari", "beklenen", "kural", "kirmizi_cizgi")

    def dosyalar(self):
        import glob
        return [os.path.join(KOK, "qa-testi", "egitmen-senaryolari.json")] + \
            sorted(glob.glob(os.path.join(KOK, "ozel", "egitmen-senaryolari*.json")))

    @staticmethod
    def basliklar(dosya):
        with open(os.path.join(KOK, "egitmenler", dosya), encoding="utf-8") as f:
            return {x[3:].strip() for x in f if x.startswith("## ")}

    def denetle(self, yol):
        with open(yol, encoding="utf-8") as f:
            d = json.load(f)
        self.assertIsInstance(d.get("senaryolar"), list)
        self.assertTrue(d["senaryolar"])
        idler = [s.get("id") for s in d["senaryolar"]]
        self.assertEqual(len(idler), len(set(idler)), "yinelenen senaryo kimliği")
        for s in d["senaryolar"]:
            ad = "%s: %s" % (os.path.basename(yol), s.get("id"))
            for alan in self.ALANLAR:
                self.assertTrue(s.get(alan), "%s: '%s' eksik" % (ad, alan))
            for alan in ("ogrenci_mesajlari", "beklenen", "kirmizi_cizgi", "kural"):
                self.assertIsInstance(s[alan], list, ad)
            self.assertIn(s["egitmen"], ("inci", "mercan", "ikisi"), ad)
            klasor = os.path.join(KOK, "lessons", s["ders"])
            eg_yol = os.path.join(klasor, "egitmen.json")
            self.assertTrue(os.path.exists(eg_yol), "%s: ders yok: %s" % (ad, s["ders"]))
            with open(eg_yol, encoding="utf-8") as f:
                eg = json.load(f)
            if s["egitmen"] != "ikisi":
                izinli = {eg.get("egitmen")} | set(eg.get("izinliEgitmenler") or [])
                self.assertIn(s["egitmen"], izinli, "%s: dersin eğitmeni değil" % ad)
            if s.get("hedef"):
                self.assertIn(s["hedef"], {h["id"] for h in eg.get("hedefler", [])}, "%s: hedef yok" % ad)
            if s.get("yanilgi"):
                self.assertIn(s["yanilgi"], {y["id"] for y in eg.get("yanilgilar", [])}, "%s: yanılgı yok" % ad)
            if s.get("vaka"):
                vyol = os.path.join(klasor, "vakalar", s["vaka"] + ".json")
                self.assertTrue(os.path.exists(vyol), "%s: vaka yok" % ad)
                if s.get("dugum"):
                    with open(vyol, encoding="utf-8") as f:
                        v = json.load(f)
                    self.assertIn(s["dugum"], {n.get("id") for n in v.get("dugumler", [])}, "%s: düğüm yok" % ad)
            for k in s["kural"]:
                self.assertIn(k.get("dosya"), ("ortak.md", "inci.md", "mercan.md"), ad)
                self.assertIn(k.get("bolum"), self.basliklar(k["dosya"]),
                              "%s: %s içinde '%s' bölümü yok" % (ad, k["dosya"], k.get("bolum")))

    def test_senaryo_dosyalari(self):
        for yol in self.dosyalar():
            with self.subTest(dosya=os.path.basename(yol)):
                self.denetle(yol)

    def test_beklenen_senaryolar_var(self):
        with open(self.dosyalar()[0], encoding="utf-8") as f:
            idler = {s["id"].split("-")[0] for s in json.load(f)["senaryolar"]}
        self.assertTrue({"S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09"} <= idler)

    def test_bozuk_senaryo_yakalanir(self):
        with open(self.dosyalar()[0], encoding="utf-8") as f:
            d = json.load(f)
        d["senaryolar"][0]["hedef"] = "H99"
        d["senaryolar"][1]["kural"] = [{"dosya": "ortak.md", "bolum": "42. Olmayan bölüm"}]
        with tempfile.TemporaryDirectory() as g:
            yol = os.path.join(g, "s.json")
            with open(yol, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False)
            with self.assertRaises(AssertionError):
                self.denetle(yol)


class YerelSunucuGuvenligi(unittest.TestCase):
    """Başka bir site öğrencinin tarayıcısı üzerinden tahtaya istek gönderemez; eğitmen aracı (Python) gönderebilir."""

    def istek(self, **basliklar):
        import sunucu
        i = object.__new__(sunucu.Isleyici)
        i.headers = {k.replace("_", "-"): v for k, v in basliklar.items()}
        return i._yerel_mi()

    def test_baslik_denetimi(self):
        self.assertTrue(self.istek(Host="127.0.0.1:8810"))  # Python aracı
        self.assertTrue(self.istek(Host="localhost:8810", Origin="http://localhost:8810", Sec_Fetch_Site="same-origin"))
        self.assertFalse(self.istek(Host="kotu.example:8810"))  # DNS yeniden bağlama
        self.assertFalse(self.istek(Host="127.0.0.1:8810", Sec_Fetch_Site="cross-site"))  # <img src=...>
        self.assertFalse(self.istek(Host="127.0.0.1:8810", Origin="https://kotu.example"))
        self.assertTrue(self.istek(Host="[::1]:8810"))


class YayinDenetimi(unittest.TestCase):
    def test_gitsiz_kopyada_gitignore_uygulanir(self):
        import yayin_denetimi as yd
        k = yd._gitignore_kurallari()
        for yol in ("lessons/ozel-akut/egitmen.json", "lessons/peri/vakalar/ozel-nug.json", "ozel/not.md",
                    "kayitlar/ali/x.json", "tools/__pycache__/a.pyc", "lessons/peri/audio/a.mp3", "paket.zip",
                    "lessons/peri/egitmen.json"):  # kurulu dersler hiçbir zaman depoya girmez
            self.assertTrue(yd.yok_sayilir_mi(yol, k), yol)
        for yol in ("ornek-dersler/peri/egitmen.json", "ornek-dersler/peri/vakalar/ornek.json",
                    "lessons/katalog.json", "tools/yayin_denetimi.py",
                    "belgeler/ozel-icerik.md"):
            self.assertFalse(yd.yok_sayilir_mi(yol, k), yol)

    def test_depo_temiz(self):
        r = subprocess.run([sys.executable, os.path.join(KOK, "tools", "yayin_denetimi.py")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)


class ClaudeAyarDosyasi(unittest.TestCase):
    """Windows'ta Claude'un okuduğu ayar dosyası bulunur; eski yerler atlanır; öteki ayarlar korunur."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("tahta_mcp_ayar", os.path.join(KOK, "tools", "tahta-mcp.py"))
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.g = tempfile.mkdtemp()
        self.ortam = {"APPDATA": os.path.join(self.g, "Roaming"), "LOCALAPPDATA": os.path.join(self.g, "Local")}
        os.makedirs(os.path.join(self.g, "Roaming", "Claude"))
        self.msix = os.path.join(self.g, "Local", "Packages", "Claude_pzs8sxrjxfjjc", "LocalCache", "Roaming", "Claude")
        os.makedirs(self.msix)

    def _tur(self, adaylar):
        return {os.path.relpath(y, self.g): t for y, t, _ in adaylar}

    def test_tasinmis_msix_yeni_yer_asil(self):
        yeni = os.path.join(self.g, "Local", "Claude-Data", "claude_pzs8sxrjxfjjc")
        os.makedirs(yeni)
        _metin_yaz(os.path.join(self.msix, ".user-data-left.claude_pzs8sxrjxfjjc"), "")
        tur = self._tur(self.m.ayar_adaylari("nt", self.ortam))
        self.assertEqual(tur[os.path.join("Local", "Claude-Data", "claude_pzs8sxrjxfjjc", "claude_desktop_config.json")], "asil")
        self.assertEqual(tur[os.path.relpath(os.path.join(self.msix, "claude_desktop_config.json"), self.g)], "eski")
        self.assertEqual(tur[os.path.join("Roaming", "Claude", "claude_desktop_config.json")], "eski")
        self.assertEqual(list(tur.values()).count("asil"), 1)

    def test_tasinmamis_msix_paket_klasoru_asil(self):
        tur = self._tur(self.m.ayar_adaylari("nt", self.ortam))
        self.assertEqual(tur[os.path.relpath(os.path.join(self.msix, "claude_desktop_config.json"), self.g)], "asil")
        self.assertEqual(tur[os.path.join("Roaming", "Claude", "claude_desktop_config.json")], "eski")

    def test_exe_kurulumu_appdata_asil(self):
        import shutil
        shutil.rmtree(os.path.join(self.g, "Local"))
        tur = self._tur(self.m.ayar_adaylari("nt", self.ortam))
        self.assertEqual(tur, {os.path.join("Roaming", "Claude", "claude_desktop_config.json"): "asil"})

    def test_hic_aday_yoksa_bos(self):
        self.assertEqual(self.m.ayar_adaylari("nt", {"APPDATA": os.path.join(self.g, "yok"), "LOCALAPPDATA": ""}), [])

    def test_yazma_oteki_alanlari_korur_ve_tekrar_yazilabilir(self):
        yol = os.path.join(self.g, "ayar.json")
        asil = {"preferences": {"a": 1}, "coworkUserFilesPath": "C:/x",
                "mcpServers": {"akilli-tahta": {"command": "py", "args": ["t.py"]}}}
        _metin_yaz(yol, "\ufeff" + json.dumps(asil))  # Not Defteri BOM ekleyebilir
        self.m.ayara_yaz(yol)
        self.m.ayara_yaz(yol)
        d = _json_oku(yol)
        self.assertEqual(d["preferences"], {"a": 1})
        self.assertEqual(d["coworkUserFilesPath"], "C:/x")
        self.assertIn("akilli-tahta", d["mcpServers"])
        self.assertIn(self.m.AD, d["mcpServers"])
        self.assertTrue(os.path.exists(yol + ".yedek"))
        self.m.ayara_yaz(yol, kaldir=True)
        d = _json_oku(yol)
        self.assertNotIn(self.m.AD, d["mcpServers"])
        self.assertIn("akilli-tahta", d["mcpServers"])

    def test_kur_ayar_secenegi(self):
        yol = os.path.join(self.g, "elle", "claude_desktop_config.json")
        os.makedirs(os.path.dirname(yol))
        _metin_yaz(yol, json.dumps({"preferences": {}}))
        ortam = dict(os.environ, KLINIK_KOC_KAYIT=os.path.join(self.g, "kayit"))
        r = subprocess.run([sys.executable, os.path.join(KOK, "tools", "tahta-mcp.py"), "--kur", "--ayar", yol],
                           capture_output=True, text=True, encoding="utf-8", env=ortam)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("klinik-koc", _json_oku(yol)["mcpServers"])


class PocketPythonBulma(unittest.TestCase):
    """Pocket için Python 3.10–3.13 aranır; 3.14 atlanır; hiçbiri yoksa kur() açık mesajla 2 döner."""

    def setUp(self):
        import pocket_ses
        self.p = pocket_ses
        self.eski = (pocket_ses._surum, pocket_ses._uv)

    def tearDown(self):
        self.p._surum, self.p._uv = self.eski

    def test_314_atlanir_313_secilir(self):
        def sahte(komut):
            if komut == [sys.executable]:
                return (3, 14), sys.executable
            if komut[-1] in ("-3.13",) or komut[0].endswith("python3.13"):
                return (3, 13), "/yol/python313"
            return None
        self.p._surum = sahte
        self.p._uv = lambda: None
        import shutil
        eski_which = shutil.which
        shutil.which = lambda ad: "/usr/bin/" + ad if ad == "python3.13" else None
        try:
            self.assertEqual(self.p.uygun_python(), "/yol/python313")
        finally:
            shutil.which = eski_which

    def test_hic_yoksa_kur_2_doner(self):
        self.p._surum = lambda komut: ((3, 14), "x") if komut == [sys.executable] else None
        self.p._uv = lambda: None
        import io
        import contextlib
        cikti = io.StringIO()
        with contextlib.redirect_stdout(cikti):
            self.assertEqual(self.p.kur(), 2)
        self.assertIn("Python 3.10–3.13 gerekir", cikti.getvalue())

    def test_surum_siniri(self):
        self.assertTrue(self.p._uygun_mu((3, 10)))
        self.assertTrue(self.p._uygun_mu((3, 13)))
        self.assertFalse(self.p._uygun_mu((3, 14)))
        self.assertFalse(self.p._uygun_mu((3, 9)))


class SesBilgisi(unittest.TestCase):
    """Tahta hangi sesin GERÇEKTEN kullanılacağını söyler: Pocket → Piper (yedek) → tarayıcı sesi."""

    def setUp(self):
        import sunucu
        self.s = sunucu
        self.c = sunucu.Canli()
        self.eski = (sunucu.POCKET.durum, sunucu.pocket_ses.ayar)
        sunucu.pocket_ses.ayar = lambda: {"motor": "pocket", "ses": "female_3", "yedek": "tr_TR-dfki-medium"}

    def tearDown(self):
        self.s.POCKET.durum, self.s.pocket_ses.ayar = self.eski

    def test_pocket_hazir(self):
        self.s.POCKET.durum = "hazır"
        self.assertEqual(self.c.ses_bilgisi()["motor"], "pocket")

    def test_pocket_yok_piper_var(self):
        self.s.POCKET.durum = "Pocket ses ortamı yok"
        self.c.ses = {"hazir": True}
        b = self.c.ses_bilgisi()
        self.assertEqual(b["motor"], "piper")
        self.assertIn("yedek", b["yazi"])

    def test_hicbiri_yok_tarayici(self):
        self.s.POCKET.durum = "Pocket ses ortamı yok"
        self.c.ses_hata = "Piper kurulu değil"
        b = self.c.ses_bilgisi()
        self.assertEqual(b["motor"], "tarayici")
        self.assertIn("tarayıcı", self.c.ses_durumu())


class PocketYenidenDeneme(unittest.TestCase):
    """Windows test raporu: Türkçe harfli kurulum yolu, başarısız Pocket işçisinin yeniden denenmesi."""

    def setUp(self):
        import pocket_ses
        self.p = pocket_ses
        self.eski = (pocket_ses.ortam_python, pocket_ses.YENIDEN_DENE_SN, pocket_ses.subprocess.Popen)
        self.acilan = []

        class SahteSurec:
            def __init__(s, komut, **k):
                s.komut = komut
                s.stdout = __import__("io").StringIO('@@{"hazir": true, "sure": 1}\n')
                s.stdin = __import__("io").StringIO()
                self.acilan.append(s)

            def poll(s):
                return None

            def wait(s, _=None):
                return 0
        pocket_ses.subprocess.Popen = SahteSurec

    def tearDown(self):
        self.p.ortam_python, self.p.YENIDEN_DENE_SN, self.p.subprocess.Popen = self.eski

    def test_komut_utf8_ile(self):
        k = self.p.isci_komutu(os.path.join(tempfile.gettempdir(), "koç deneme", "python.exe"))
        self.assertEqual(k[1:4], ["-I", "-X", "utf8"])
        self.assertTrue(k[-1].endswith("pocket-isci.py"))

    def _bekle(self, isci):
        self.assertTrue(isci.hazir.wait(5))

    def test_ortam_yoksa_sonra_yeniden_dener(self):
        isci = self.p.PocketIsci()
        self.p.ortam_python = lambda: None
        isci.baslat()
        self.assertIn("ortamı yok", isci.durum)
        self.p.ortam_python = lambda: "/sahte/python"
        isci.baslat()  # bekleme süresi dolmadı: yeniden denemez
        self.assertEqual(self.acilan, [])
        self.p.YENIDEN_DENE_SN = 0
        isci.baslat()
        self._bekle(isci)
        self.assertEqual(isci.durum, "hazır")
        self.assertEqual(len(self.acilan), 1)
        isci.baslat()  # hazır ve açık: yeni süreç açılmaz
        self.assertEqual(len(self.acilan), 1)

    def test_zorla_yeniden_baslatir(self):
        self.p.ortam_python = lambda: "/sahte/python"
        isci = self.p.PocketIsci()
        isci.baslat()
        self._bekle(isci)
        isci.baslat(zorla=True)
        self._bekle(isci)
        self.assertEqual(len(self.acilan), 2)
        self.assertEqual(isci.durum, "hazır")


class IkiKurulum(unittest.TestCase):
    """Yan yana iki kurulum: açık sunucu başka klasördense tahtayi_ac bunu fark eder."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("tahta_mcp_iki", os.path.join(KOK, "tools", "tahta-mcp.py"))
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)

    def test_sunucu_kokunu_soyler(self):
        import sunucu
        self.assertTrue(os.path.samefile(sunucu.Canli().durum()["kok"], KOK))

    def test_baska_kurulum(self):
        self.assertIsNone(self.m.baska_kurulum_mu({"kok": KOK}))
        self.assertIsNone(self.m.baska_kurulum_mu({}))  # eski sürüm: yolunu söylemez
        baska = os.path.join(tempfile.gettempdir(), "koç deneme", "klinikkoc-v3")
        self.assertEqual(self.m.baska_kurulum_mu({"kok": baska}), baska)

    def test_uzun_sessizlikte_birak(self):
        self.m.istek = lambda *a, **k: {"durum": "sessiz"}
        y = json.loads(self.m.ar_dinle({"bekle": 40})["content"][0]["text"])
        self.assertTrue(y["devam"])
        self.m._sessizlik["bas"] -= self.m.SESSIZ_SINIR_SN
        y = json.loads(self.m.ar_dinle({"bekle": 40})["content"][0]["text"])
        self.assertFalse(y["devam"])
        self.assertIsNone(self.m._sessizlik["bas"])


if __name__ == "__main__":
    unittest.main()
