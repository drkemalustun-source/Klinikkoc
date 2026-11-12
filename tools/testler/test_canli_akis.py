"""Tahta ile Claude arasındaki konuşmanın donma testleri ("sahte Claude").

Gerçek tools/sunucu.py (bu süreçte) ve gerçek tools/tahta-mcp.py (ayrı süreç, stdin/stdout) çalışır; Claude'un
yerine bu test JSON-RPC iletileri gönderir, tahta sayfasının yerine de HTTP istekleri. Denenenler: Claude bir
beklemeyi iptal edince söz kaybolmaz; bekleme sürerken ping ve başka çağrılar donmaz; teslim onayı gelmeyen söz
kuyruğa döner; otomatik uyandırma ne zaman çalışır; uzun anlatım tek çağrıda beklenir.
Çalıştırma:  python -m unittest discover -s tools/testler -v
"""
import http.server
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(KOK, "tools"))


class SahteClaude:
    """tahta-mcp.py'yi alt süreç olarak açar; iletileri id'ye göre toplar."""

    def __init__(self, port, veri, nabiz=None):
        ortam = dict(os.environ, KLINIK_KOC_PORT=str(port), KLINIK_KOC_VERI=veri, KLINIK_KOC_KAYIT=os.path.join(veri, "k"))
        if nabiz:
            ortam["KLINIK_KOC_NABIZ_SN"] = str(nabiz)
        self.p = subprocess.Popen([sys.executable, os.path.join(KOK, "tools", "tahta-mcp.py")], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=ortam)
        self.yanitlar = {}
        self.bildirimler = []
        self.kosul = threading.Condition()
        threading.Thread(target=self._oku, daemon=True).start()
        self.no = 0
        self.cagir_bekle("initialize", {"protocolVersion": "2025-06-18"})
        self.gonder({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _oku(self):
        for satir in self.p.stdout:
            m = json.loads(satir)
            with self.kosul:
                if "id" in m and m.get("id") is not None:
                    self.yanitlar[m["id"]] = m
                else:
                    self.bildirimler.append(m)
                self.kosul.notify_all()

    def gonder(self, m):
        self.p.stdin.write((json.dumps(m) + "\n").encode())
        self.p.stdin.flush()

    def cagir(self, yontem, params=None):
        self.no += 1
        self.gonder({"jsonrpc": "2.0", "id": self.no, "method": yontem, "params": params or {}})
        return self.no

    def arac(self, ad, arg=None, meta=None):
        p = {"name": ad, "arguments": arg or {}}
        if meta:
            p["_meta"] = meta
        return self.cagir("tools/call", p)

    def yanit(self, no, sure=10):
        bitis = time.time() + sure
        with self.kosul:
            while no not in self.yanitlar:
                kalan = bitis - time.time()
                if kalan <= 0:
                    return None
                self.kosul.wait(kalan)
            return self.yanitlar[no]

    def cagir_bekle(self, yontem, params=None, sure=10):
        return self.yanit(self.cagir(yontem, params), sure)

    @staticmethod
    def icerik(y):
        return json.loads(y["result"]["content"][0]["text"])

    def kapat(self):
        try:
            self.p.stdin.close()
        except OSError:
            pass
        self.p.kill()
        self.p.wait(timeout=10)
        self.p.stdout.close()


class AkisTemeli(unittest.TestCase):
    def setUp(self):
        import sunucu
        self.sunucu = sunucu
        self.eski_canli = sunucu.CANLI
        sunucu.CANLI = self.c = sunucu.Canli()
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), sunucu.Isleyici)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.port = self.srv.server_address[1]
        self.gecici = tempfile.TemporaryDirectory()
        self.c.son_gorulme = time.time() + 3600  # tahta sayfası açık sayılsın
        self.claude = None

    def tearDown(self):
        if self.claude:
            self.claude.kapat()
        self.srv.shutdown()
        self.srv.server_close()
        self.sunucu.CANLI = self.eski_canli
        self.gecici.cleanup()

    def sahte_claude(self, **kw):
        self.claude = SahteClaude(self.port, self.gecici.name, **kw)
        return self.claude

    def soyle(self, metin):
        r = urllib.request.Request("http://127.0.0.1:%d/api/canli/soyle" % self.port,
                                   data=json.dumps({"metin": metin}).encode(), headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(r, timeout=5).read())

    def bekle_ki(self, kosul, sure=5):
        bitis = time.time() + sure
        while time.time() < bitis:
            if kosul():
                return True
            time.sleep(0.05)
        return False


class SozKaybolmaz(AkisTemeli):
    def test_iptal_edilen_bekleme_sozu_yutmaz(self):
        """Eski hata: Claude 'dinle'yi iptal ettikten (ya da zaman aşımından) sonra konuşulan söz kayboluyordu."""
        cl = self.sahte_claude()
        no = cl.arac("bekle")
        self.assertTrue(self.bekle_ki(lambda: self.c.dinleyen > 0))
        cl.gonder({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": no, "reason": "kullanıcı durdurdu"}})
        self.assertTrue(self.bekle_ki(lambda: self.c.dinleyen == 0), "iptal edilen bekleme sunucuda sürmemeli")
        self.assertFalse(self.soyle("periimplantitis nedir")["claude_dinliyor"])
        y = cl.icerik(cl.yanit(cl.arac("bekle"), 15))
        self.assertEqual((y["durum"], y["metin"]), ("konustu", "periimplantitis nedir"))
        self.assertIsNone(cl.yanit(no, 0.5), "iptal edilen çağrıya yanıt yazılmamalı")
        self.assertTrue(self.bekle_ki(lambda: not self.c.ayrilan), "teslim onayı gelmeli")
        self.assertEqual(self.c.konusmalar, [])

    def test_iptalle_yaris_soz_geri_doner(self):
        """Söz verildiği anda çağrı iptal edildiyse söz kuyruğa geri konur (Claude'a yazılmadı)."""
        self.c.soyle("ilk")
        y = self.c.dinle(1, teslim=True)
        self.assertEqual(y["metin"], "ilk")
        self.assertEqual(self.c.konusmalar, [])
        self.c.teslim_et(y["teslim"], False)
        self.assertEqual([x["metin"] for x in self.c.konusmalar], ["ilk"])

    def test_onaysiz_soz_sure_dolunca_doner(self):
        self.sunucu.TESLIM_SN = 0.3
        try:
            self.c.soyle("unutulan söz")
            y = self.c.dinle(1, teslim=True)
            self.assertIn("teslim", y)
            time.sleep(0.4)
            self.assertEqual(self.c.dinle(1)["metin"], "unutulan söz")
        finally:
            self.sunucu.TESLIM_SN = 20.0

    def test_eski_arac_teslimsiz_calisir(self):
        self.c.soyle("eski")
        y = self.c.dinle(1)
        self.assertNotIn("teslim", y)
        self.assertEqual(self.c.ayrilan, {})


class Donmaz(AkisTemeli):
    def test_bekleme_surerken_ping_ve_baska_cagri(self):
        cl = self.sahte_claude()
        uzun = cl.arac("bekle")
        self.assertTrue(self.bekle_ki(lambda: self.c.dinleyen > 0))
        t = time.time()
        self.assertIsNotNone(cl.cagir_bekle("ping", sure=3), "bekleme sürerken ping hemen yanıtlanmalı")
        self.assertIsNotNone(cl.yanit(cl.arac("dersler"), 10), "bekleme sürerken başka araç çalışmalı")
        self.assertLess(time.time() - t, 8)
        self.soyle("tamam")
        self.assertEqual(cl.icerik(cl.yanit(uzun, 10))["metin"], "tamam")

    def test_uzun_anlatim_tek_cagrida_beklenir_ve_nabiz_gider(self):
        """İlerleme jetonu varsa tahta aracı 25 sn'lik parçalarla bekler, aralarda ilerleme bildirimi gönderir."""
        cl = self.sahte_claude(nabiz=0.5)

        def sayfa():  # anlatımı 2 sn'de bitiren sahte tahta sayfası
            r = json.loads(urllib.request.urlopen("http://127.0.0.1:%d/api/canli/al?son=0" % self.port, timeout=30).read())
            time.sleep(2)
            for k in r["komutlar"]:
                self.c.bitti(k["no"], {"durum": "bitti"}, {})
        threading.Thread(target=sayfa, daemon=True).start()
        no = cl.arac("tahta", {"adimlar": [{"anlat": "Merhaba."}]}, meta={"progressToken": "j1"})
        y = cl.icerik(cl.yanit(no, 20))
        self.assertEqual(y["durum"], "bitti")
        self.assertTrue(any(b.get("method") == "notifications/progress" for b in cl.bildirimler))

    def test_soz_kesme_aninda_doner(self):
        cl = self.sahte_claude()
        no = cl.arac("tahta", {"adimlar": [{"anlat": "Uzun bir anlatım."}]})
        self.assertTrue(self.bekle_ki(lambda: self.c.claude_bekliyor > 0))
        self.assertTrue(self.soyle("durun bir sorum var")["claude_dinliyor"])
        y = cl.icerik(cl.yanit(no, 10))
        self.assertEqual(y["durum"], "kullanici_konustu")
        self.assertEqual(y["kullanici_konustu"], "durun bir sorum var")
        self.assertNotIn("teslim", y)


class Ogrenme(unittest.TestCase):
    def test_zaman_asimindan_sinir_ogrenilir(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("tahta_mcp_ogren", os.path.join(KOK, "tools", "tahta-mcp.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        yazilan = {}
        m._ayar_yaz = lambda k, v: yazilan.update({k: v})
        m._ogren({"araci": "bekle", "neden": "McpError: MCP error -32001: Request timed out"}, 60.2)
        self.assertEqual(yazilan, {"arac_bekleme_sn": 48})
        yazilan.clear()
        m._ogren({"araci": "bekle", "neden": "kullanıcı durdurdu"}, 70)
        self.assertEqual(yazilan, {})
        m._ayar = lambda k, v=None: 48
        self.assertEqual(m.bekleme_butcesi(True), 48)
        m._ayar = lambda k, v=None: None
        self.assertEqual(m.bekleme_butcesi(True), m.DENEME_BEKLEME_SN)
        self.assertEqual(m.bekleme_butcesi(False), m.VARSAYILAN_BEKLEME_SN)


class ProfilVeKurulum(unittest.TestCase):
    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("tahta_mcp_profil", os.path.join(KOK, "tools", "tahta-mcp.py"))
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)

    def test_ogrenci_ogretmen_araclarini_gormez(self):
        self.m.profil = lambda: "ogrenci"
        adlar = {a["name"] for a in self.m.araclar()}
        self.assertIn("bekle", adlar)
        self.assertNotIn("dinle", adlar)
        self.assertFalse(adlar & self.m.OGRETMEN_ARACLARI)
        self.m.profil = lambda: "ogretmen"
        self.assertTrue(self.m.OGRETMEN_ARACLARI <= {a["name"] for a in self.m.araclar()})
        self.assertIn("dinle", self.m.ISLEYICILER)  # eski sohbetler çağırırsa çalışır

    def test_profil_ayari(self):
        os.environ["KLINIK_KOC_PROFIL"] = "öğretmen"
        try:
            self.assertEqual(self.m.profil(), "ogretmen")
            os.environ["KLINIK_KOC_PROFIL"] = "ogrenci"
            self.assertEqual(self.m.profil(), "ogrenci")
        finally:
            del os.environ["KLINIK_KOC_PROFIL"]

    def test_kur_eski_tahtayi_cikarir(self):
        with tempfile.TemporaryDirectory() as d:
            yol = os.path.join(d, "claude_desktop_config.json")
            with open(yol, "w", encoding="utf-8") as f:
                json.dump({"mcpServers": {"akilli-tahta": {"command": "py", "args": ["C:/x/tools/tahta-mcp.py"]},
                                          "baska": {"command": "npx", "args": ["x"]}}, "preferences": {"a": 1}}, f)
            self.assertEqual(self.m.ayara_yaz(yol), ["akilli-tahta"])
            with open(yol, encoding="utf-8") as f:
                a = json.load(f)
            self.assertEqual(set(a["mcpServers"]), {"klinik-koc", "baska"})
            self.assertEqual(a["preferences"], {"a": 1})
            self.assertTrue(os.path.exists(yol + ".yedek"))


class SihirbazOgretmenYapar(unittest.TestCase):
    def test_sihirbaz_acilinca_profil_ogretmen(self):
        import sunucu
        with tempfile.TemporaryDirectory() as d:
            eski = os.environ.get("KLINIK_KOC_VERI")
            os.environ["KLINIK_KOC_VERI"] = d
            try:
                sunucu.ogretmen_profili_isaretle()
                with open(os.path.join(d, "ayarlar.json"), encoding="utf-8") as f:
                    self.assertEqual(json.load(f)["profil"], "ogretmen")
                with open(os.path.join(d, "ayarlar.json"), "w", encoding="utf-8") as f:
                    json.dump({"profil": "ogrenci"}, f)
                sunucu.ogretmen_profili_isaretle()  # elle seçilen profile dokunulmaz
                with open(os.path.join(d, "ayarlar.json"), encoding="utf-8") as f:
                    self.assertEqual(json.load(f)["profil"], "ogrenci")
            finally:
                if eski is None:
                    del os.environ["KLINIK_KOC_VERI"]
                else:
                    os.environ["KLINIK_KOC_VERI"] = eski


class Uyandirma(unittest.TestCase):
    def setUp(self):
        import sunucu
        self.c = sunucu.Canli()
        self.giden = []
        self.sonuc = (True, "gönderildi")

    def gonderici(self, metin):
        self.giden.append(metin)
        return self.sonuc

    def test_claude_dinlemiyorsa_soz_sohbete_gider(self):
        self.c.soyle("apse nasıl drene edilir")
        self.assertIsNone(self.c.uyandir_bir_kez(self.gonderici), "söz hemen gönderilmez, Claude'a süre tanınır")
        self.c.konusmalar[-1]["t"] -= 10
        self.assertEqual(self.c.uyandir_bir_kez(self.gonderici), (True, "gönderildi"))
        self.assertEqual(self.giden, ["apse nasıl drene edilir"])
        self.assertEqual((self.c.konusmalar, self.c.ayrilan), ([], {}))
        self.assertEqual(self.c.uyandirma["durum"], "gonderildi")

    def test_claude_calisirken_uyandirmaz(self):
        self.c.soyle("soru")
        self.c.konusmalar[-1]["t"] -= 10
        self.c.arac_etkin()  # Claude az önce bir araç kullandı: sırası sürüyor olabilir
        self.assertIsNone(self.c.uyandir_bir_kez(self.gonderici))
        self.c.son_arac -= 60
        self.c.dinleyen = 1  # Claude dinliyor: söz zaten ona gider
        self.assertIsNone(self.c.uyandir_bir_kez(self.gonderici))
        self.assertEqual(self.giden, [])

    def test_basarisizsa_soz_kalir(self):
        self.sonuc = (False, "Claude masaüstü uygulaması açık değil.")
        self.c.soyle("soru")
        self.c.konusmalar[-1]["t"] -= 10
        self.assertEqual(self.c.uyandir_bir_kez(self.gonderici)[0], False)
        self.assertEqual([x["metin"] for x in self.c.konusmalar], ["soru"])
        self.assertEqual(self.c.uyandirma["durum"], "olmadi")

    def test_basarisiz_soz_yeniden_denenmez(self):
        """Gönderilemeyen söz için Claude penceresi tekrar tekrar öne getirilmez; yeni söz gelince bir kez daha denenir."""
        self.sonuc = (False, "izin yok")
        self.c.soyle("soru")
        self.c.konusmalar[-1]["t"] -= 10
        self.assertEqual(self.c.uyandir_bir_kez(self.gonderici)[0], False)
        self.c.uyandirma["t"] -= 60   # iki deneme arasındaki bekleme geçmiş olsa bile
        self.c.son_arac -= 60
        self.assertIsNone(self.c.uyandir_bir_kez(self.gonderici))
        self.assertEqual(len(self.giden), 1)
        self.c.soyle("yeni soru")
        self.c.konusmalar[-1]["t"] -= 10
        self.assertEqual(self.c.uyandir_bir_kez(self.gonderici)[0], False)
        self.assertEqual(len(self.giden), 2)

    def test_tahta_kapaliyken_uyandirmaz(self):
        self.c.soyle("soru")
        self.c.konusmalar[-1]["t"] -= 10
        self.c.son_gorulme -= 60      # tahta sayfası bir süredir görünmüyor
        self.assertIsNone(self.c.uyandir_bir_kez(self.gonderici))
        self.assertEqual(self.giden, [])

    def test_mac_betigi_claudeu_acmaz(self):
        import uyandirma
        b = uyandirma._MAC_BETIK
        self.assertLess(b.index('is not running'), b.index('to activate'))
        self.assertLess(b.index('UI elements enabled'), b.index('to activate'))


SAHTE_ISCI = """import sys, json, time, base64
print("@@" + json.dumps({"hazir": True, "sure": 0}), flush=True)
for satir in sys.stdin:
    r = json.loads(satir)
    if "takil" in r["metin"]:
        time.sleep(30)
    print("@@" + json.dumps({"no": r["no"], "wav": base64.b64encode(b"RIFF").decode()}), flush=True)
"""


class SesTakilmaz(unittest.TestCase):
    """Pocket işçisi bir cümlede takılırsa beklenen süre dolunca hata verir (yedek ses konuşur) ve kendini yeniler."""

    def test_takilan_isci_yeniden_baslar(self):
        import pocket_ses
        with tempfile.TemporaryDirectory() as d:
            isci = os.path.join(d, "isci.py")
            with open(isci, "w", encoding="utf-8") as f:
                f.write(SAHTE_ISCI)
            eski = (pocket_ses.ortam_python, pocket_ses.isci_komutu, pocket_ses.CUMLE_SINIR_SN)
            pocket_ses.ortam_python = lambda: sys.executable
            pocket_ses.isci_komutu = lambda py: [py, isci]
            pocket_ses.CUMLE_SINIR_SN = 1
            p = pocket_ses.PocketIsci()
            try:
                p.baslat()
                self.assertTrue(p.hazir.wait(10))
                self.assertEqual(p.wav("merhaba"), b"RIFF")
                t = time.time()
                with self.assertRaises(RuntimeError):
                    p.wav("takil")
                self.assertLess(time.time() - t, 5)
                bitis = time.time() + 10
                while p.durum != "hazır" and time.time() < bitis:
                    time.sleep(0.1)
                self.assertEqual(p.wav("yeniden", bekle=5), b"RIFF")
            finally:
                p.kapat()
                pocket_ses.ortam_python, pocket_ses.isci_komutu, pocket_ses.CUMLE_SINIR_SN = eski


if __name__ == "__main__":
    unittest.main()
