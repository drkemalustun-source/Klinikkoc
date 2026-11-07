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

ORNEK_VAKA = os.path.join(KOK, "lessons", "peri-implantitis-cerrahi", "vakalar", "ornek-implant-kanama.json")


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

    def test_degismeyen_ders_atlanir(self):
        bilgi_bankasi.dizinle(yol=self.db, sessiz=True)
        r = bilgi_bankasi.dizinle(yol=self.db, sessiz=True)
        self.assertTrue(all(x["durum"] == "güncel" for x in r))


class VakaDenetimi(unittest.TestCase):
    def kart(self, degistir):
        v = json.load(open(ORNEK_VAKA, encoding="utf-8"))
        degistir(v)
        klasor = tempfile.mkdtemp()
        yol = os.path.join(klasor, v["id"] + ".json")
        json.dump(v, open(yol, "w", encoding="utf-8"), ensure_ascii=False)
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
            srv.shutdown()

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
            r = urllib.request.urlopen(url, timeout=5)
            self.assertEqual((r.status, len(r.read()), r.headers["Accept-Ranges"]), (200, 10240, "bytes"))
        finally:
            srv.shutdown()
            sunucu.KOK = eski


class YayinDenetimi(unittest.TestCase):
    def test_depo_temiz(self):
        r = subprocess.run([sys.executable, os.path.join(KOK, "tools", "yayin_denetimi.py")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
