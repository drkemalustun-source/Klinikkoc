"""Konuşma tanımanın bozduğu alan terimlerini düzeltir (yalnız bu bilgisayarda, internetsiz).

Örnek: tanıyıcı "nekrotizan gingivitis" yerine "nekrotizangin gibi test" yazarsa metin
"nekrotizan gingivitis" olarak düzeltilir. Ham metin her zaman ayrıca saklanır; Claude ikisini de görür.

Sözlüğün kaynakları:
  1. ses/terimler.json             programla gelen genel terimler ve bozuk → doğru eşlemeleri
  2. <kalıcı veri>/terimler.json   öğretmenin kendi eklediği terimler (güncellemede silinmez)
  3. ses/telaffuz.json             ters yönü: okunuş → yazım ("bon fil" → "bone fill"); kısaltmalar hariç
  4. derslerin dosyaları           term komutlarındaki terimler ve kısa hedef başlıkları

terimler.json biçimi:
  {"terimler": ["birleşim epiteli", ...],
   "duzeltmeler": [{"bozuk": "nekrotizangin gibi test", "dogru": "nekrotizan gingivitis"}, ...]}

İki adım: (a) bozuk → doğru eşlemeleri birebir uygulanır; (b) sözlükteki terimlere yazımca çok benzeyen
sözcük öbekleri (birleşik ya da ayrık yazılmış, sonuna Türkçe ek almış) terime çevrilir.
Yalnız Python'un kendi kitaplığını kullanır.
"""
import difflib
import glob
import json
import os
import re

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_KATLA = str.maketrans("çğıöşüâîûÇĞIİÖŞÜÂÎÛ", "cgiosuaiucgiiosuaiu")
SOZCUK = re.compile(r"[0-9A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]+(?:['’\-][0-9A-Za-zÇĞİÖŞÜçğıöşüÂÎÛâîû]+)*")
UNLU = set("aeıioöuü")
# Terimin sonuna gelebilecek ekler (yazımı katlanmış). Ünlüyle biten terimde ek ünsüzle başlamalı.
EKLER = sorted({
    "i", "ı", "u", "ü", "e", "a", "in", "ın", "un", "ün", "de", "da", "te", "ta", "den", "dan", "ten", "tan",
    "le", "la", "ler", "lar", "leri", "ları", "lerin", "ların", "lere", "lara", "lerde", "larda", "le", "yle", "yla",
    "nin", "nın", "nun", "nün", "ne", "na", "nde", "nda", "nden", "ndan", "ni", "nı", "nu", "nü", "ye", "ya",
    "yi", "yı", "yu", "yü", "si", "sı", "su", "sü", "sine", "sına", "sinde", "sında", "sini", "sını", "sinin", "sının",
    "dir", "dır", "tir", "tır", "dur", "tur", "dür", "tür", "li", "lı", "lu", "lü", "siz", "sız", "e", "ce", "ca",
}, key=len, reverse=True)
BAGLAC = {"ve", "ile", "veya", "ya", "mi", "mu", "da", "de", "bu", "bir", "icin", "ama", "ki", "o", "su", "ne"}
ESIK_TEK = 0.86      # tek sözcüklü terim için en düşük benzerlik
ESIK_COK = 0.80      # çok sözcüklü terim için
EN_KISA = 7          # bundan kısa (katlanmış) terimler bulanık düzeltilmez
EN_KISA_TEK = 9      # tek sözcüklü terimde ("iyileşme" gibi gündelik sözcüklerle karışmasın)


def kucuk(s):
    return (s or "").replace("I", "ı").replace("İ", "i").lower()


def katla(s):
    return kucuk(s).translate(_KATLA)


def anahtar(s):
    return "".join(c for c in katla(s) if c.isalnum())


def _ek_uygun(terim, ek):
    if not ek:
        return True
    son = kucuk(terim)[-1:]
    if son in UNLU:  # ünlüyle biten terime ünlüyle başlayan ek gelmez ("epiteli" + "i" olmaz)
        return ek[0] not in UNLU
    return True


def _ortak_disi(a, b):
    """Ortak baş ve son atıldıktan sonra kalan parçalar ve terim tarafının başladığı yer."""
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    j = 0
    while j < min(len(a), len(b)) - i and a[-1 - j] == b[-1 - j]:
        j += 1
    return a[i:len(a) - j], b[i:len(b) - j], i


def degisim_uygun(wa, ta, yazim, n, tn):
    """Değişen bölge küçük ve tek bir sözcüğün içinde mi? "periodontal cep" → "periodontal apse" olmasın
    (sözcüğün tamamı değişiyor); "birleşim epiteliği" → "birleşim epiteli" olsun."""
    x, y, bas = _ortak_disi(wa, ta)
    if not x and not y:
        return True
    if ta.startswith(wa):
        return False  # kısaltılmış biçim çoğu zaman geçerli bir sözcüktür ("lökosit", "gingivostomatit")
    if not y:
        return len(x) <= 2  # pencerede fazladan harf
    if not x:
        return len(y) <= 2  # pencerede eksik harf
    sinirlar, k = [], 0
    for s in yazim.split():
        uz = len(anahtar(s))
        sinirlar.append((k, k + uz))
        k += uz
    L = sum(b - a for a, b in sinirlar if a < bas + len(y) and b > bas) or len(ta)
    oran = 0.6 if n > tn else 0.4  # terim tanıyıcıda birden çok sözcüğe bölünmüşse daha çok değişiklik olağandır
    return len(y) <= oran * L and len(x) <= oran * L + 2


def _json(yol):
    try:
        with open(yol, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _terim_temizle(t):
    """'Anlatı derlemesi (narrative review)' → ['Anlatı derlemesi', 'narrative review']"""
    out = []
    for parca in re.split(r"[()\[\]/;≠=]+", t or ""):
        parca = re.sub(r"\s+", " ", parca).strip(" ,.:-–—")
        if parca and len(parca.split()) <= 5:
            out.append(parca)
    return out


class Sozluk:
    def __init__(self, terimler=(), duzeltmeler=()):
        self.duzeltmeler = []   # [(bozuk anahtar sözcükleri, doğru)]
        self.terimler = {}      # anahtar → yazım
        for b, d in duzeltmeler:
            self.duzeltme_ekle(b, d)
        for t in terimler:
            self.terim_ekle(t)

    def terim_ekle(self, t):
        for p in _terim_temizle(t):
            a = anahtar(p)
            if a and a not in self.terimler:
                self.terimler[a] = p

    def duzeltme_ekle(self, bozuk, dogru):
        sozcukler = [anahtar(s) for s in SOZCUK.findall(bozuk or "")]
        sozcukler = [s for s in sozcukler if s]
        if sozcukler and dogru and anahtar(bozuk) != anahtar(dogru):
            self.duzeltmeler.append((sozcukler, dogru.strip()))
            self.duzeltmeler.sort(key=lambda x: -len(x[0]))
        if dogru:
            self.terim_ekle(dogru)

    def _govdeler(self):
        """Her terimin ek alırken kullanılan gövdeleri: 'derinliği' → 'derinlik', 'epiteli' → 'epitel'."""
        if getattr(self, "_govde_onbellek", None) is None or self._govde_sayi != len(self.terimler):
            g = set()
            yumusama = {"g": "k", "b": "p", "c": "c", "d": "t"}
            for ta, yazim in self.terimler.items():
                g.add(ta)
                if ta.endswith("itis"):
                    g.add(ta[:-2])  # Türkçe biçim: "stomatitis" ~ "stomatit", "periodontit"
                son = anahtar(yazim.split()[-1]) if yazim.split() else ""
                if len(son) >= 6 and son[-1] in "aeiou":  # kısa sözcükte ("apse") gövde çıkarılmaz
                    if son[-2] in yumusama:
                        g.add(ta[:-2] + yumusama[son[-2]])
                    if son[-2] == "s":
                        g.add(ta[:-2])
            self._govde_onbellek = {x for x in g if len(x) >= EN_KISA}
            self._govde_sayi = len(self.terimler)
        return self._govde_onbellek

    def _dogru_terim_sozcukleri(self, anahtarlar, adaylar):
        govdeler = self._govdeler()
        korunan = set()
        for i in range(len(anahtarlar)):
            for n in range(1, 6):
                if i + n > len(anahtarlar):
                    break
                wa = "".join(anahtarlar[i:i + n])
                if wa in self.terimler and n != len(self.terimler[wa].split()):
                    # ayrık ya da bitişik yazılmış ("klor heksidin"): terimin yazımına getir
                    adaylar.append((1, 0.99, i, n, self.terimler[wa]))
                if wa in self.terimler or any(
                        wa.startswith(g) and len(wa) - len(g) <= 9 and len(g) >= 0.6 * len(wa)
                        for g in govdeler if g[:2] == wa[:2]):
                    korunan.update(range(i, i + n))
        return korunan

    def __len__(self):
        return len(self.terimler)

    # ---------- düzeltme ----------
    def duzelt(self, metin):
        """{'metin': düzeltilmiş, 'ham_metin': gelen, 'duzeltmeler': [{'ham', 'terim', 'benzerlik'}]}"""
        ham = metin or ""
        sozcukler = [(m.start(), m.end(), m.group(0)) for m in SOZCUK.finditer(ham)]
        anahtarlar = [anahtar(s[2]) for s in sozcukler]
        adaylar = []  # (öncelik, benzerlik, i, n, yeni metin)
        # (a) birebir eşlemeler: son sözcük ek almış olabilir
        for bozuk, dogru in self.duzeltmeler:
            n = len(bozuk)
            for i in range(len(sozcukler) - n + 1):
                if anahtarlar[i:i + n - 1] != bozuk[:-1]:
                    continue
                son = anahtarlar[i + n - 1]
                if not son.startswith(bozuk[-1]):
                    continue
                ek = son[len(bozuk[-1]):]
                if ek and (ek not in {katla(e) for e in EKLER} or not _ek_uygun(dogru, ek)):
                    continue
                ek_yazim = sozcukler[i + n - 1][2][len(sozcukler[i + n - 1][2]) - len(ek):] if ek else ""
                adaylar.append((2, 1.0, i, n, dogru + ek_yazim))
        # (b) benzer yazımlı öbekler. Metinde zaten doğru yazılmış bir terimin (ek almış olsa da) sözcüklerine dokunulmaz.
        korunan = self._dogru_terim_sozcukleri(anahtarlar, adaylar)
        sozcukler_k = {anahtar(w) for t in self.terimler.values() for w in t.split() if len(anahtar(w)) >= 4}
        ekler_k = [(katla(e), e) for e in EKLER]
        for ta, yazim in self.terimler.items():
            tn = len(yazim.split())
            if len(ta) < (EN_KISA if tn > 1 else EN_KISA_TEK):
                continue
            esik = ESIK_TEK if tn == 1 else ESIK_COK
            for i in range(len(sozcukler)):
                if not anahtarlar[i] or anahtarlar[i][0] != ta[0]:
                    continue
                for n in range(max(1, tn - 1), tn + 3):
                    if i + n > len(sozcukler):
                        break
                    if any(j in korunan for j in range(i, i + n)):
                        continue
                    if n == tn and any(a != b and a in sozcukler_k
                                       for a, b in zip(anahtarlar[i:i + n], (anahtar(w) for w in yazim.split()))):
                        continue  # öbekteki farklı sözcük başka bir terimin gerçek sözcüğü: "nekrotizan periodontal"
                    if any(ham[sozcukler[j][1]:sozcukler[j + 1][0]].strip() for j in range(i, i + n - 1)):
                        break  # öbek noktalama, ayraç ya da kısaltmanın üstünden geçmesin: "stomatit (NS"
                    wa = "".join(anahtarlar[i:i + n])
                    if len(wa) < 0.75 * len(ta) or len(wa) > 1.3 * len(ta) + 5:
                        continue
                    if n < tn and len(wa) < 0.92 * len(ta):
                        continue  # terimin bir sözcüğü eksik: "kemik defekti" "kemik içi defekt" değildir
                    if n > 1 and (anahtarlar[i + n - 1] in BAGLAC or anahtarlar[i] in BAGLAC) and wa != ta:
                        continue  # öbek "ve", "ile" gibi bir bağlaçla başlıyor ya da bitiyor
                    if wa == ta:
                        break  # zaten doğru
                    en_iyi, ek_iyi = 0.0, ""
                    for ek_k, _ in [("", "")] + ekler_k:
                        if ek_k and not (wa.endswith(ek_k) and len(wa) - len(ek_k) >= EN_KISA):
                            continue
                        govde = wa[:len(wa) - len(ek_k)] if ek_k else wa
                        if ek_k and govde == ta:
                            en_iyi = -1  # terim + doğru ek: dokunma
                            break
                        if ek_k and not _ek_uygun(yazim, ek_k):
                            continue
                        if not degisim_uygun(govde, ta, yazim, n, tn):
                            continue
                        sm = difflib.SequenceMatcher(None, govde, ta, autojunk=False)
                        if sm.real_quick_ratio() < esik or sm.quick_ratio() < esik:
                            continue
                        r = sm.ratio()
                        if r > en_iyi + 1e-9:
                            en_iyi, ek_iyi = r, ek_k
                    if en_iyi == -1:
                        break
                    if en_iyi >= esik:
                        son = sozcukler[i + n - 1][2]
                        ek_yazim = son[len(son) - len(ek_iyi):] if ek_iyi else ""
                        adaylar.append((1, en_iyi, i, n, yazim + ek_yazim))
        # örtüşmeyen en iyi adaylar
        adaylar.sort(key=lambda a: (-a[0], -a[1], -a[3]))
        dolu, secilen = set(), []
        for oncelik, benzerlik, i, n, yeni in adaylar:
            if any(j in dolu for j in range(i, i + n)):
                continue
            dolu.update(range(i, i + n))
            secilen.append((i, n, yeni, benzerlik))
        if not secilen:
            return {"metin": ham, "ham_metin": ham, "duzeltmeler": []}
        secilen.sort()
        out, kon, duz = [], 0, []
        for i, n, yeni, benzerlik in secilen:
            bas, son = sozcukler[i][0], sozcukler[i + n - 1][1]
            eski = ham[bas:son]
            if eski.replace("\xad", "").replace("\n", "") == yeni:
                continue
            if eski[:1].isupper() and yeni[:1].islower():
                yeni = (yeni[0].upper() if yeni[0] not in "iı" else ("İ" if yeni[0] == "i" else "I")) + yeni[1:]
            out.append(ham[kon:bas])
            out.append(yeni)
            kon = son
            duz.append({"ham": eski, "terim": yeni, "benzerlik": round(benzerlik, 2)})
        out.append(ham[kon:])
        return {"metin": "".join(out), "ham_metin": ham, "duzeltmeler": duz}


# ---------- dosyalardan yükleme ----------
def kaynak_dosyalari(kok=KOK, veri=None):
    yollar = [os.path.join(kok, "ses", "terimler.json"), os.path.join(kok, "ses", "telaffuz.json")]
    if veri:
        yollar.append(os.path.join(veri, "terimler.json"))
    for d in sorted(glob.glob(os.path.join(kok, "lessons", "*", ""))):
        yollar += [os.path.join(d, "ders.json"), os.path.join(d, "egitmen.json"), os.path.join(d, "terimler.json")]
    return yollar


def _komut_terimleri(x, out):
    if isinstance(x, dict):
        if x.get("type") == "term" and isinstance(x.get("term"), str):
            out.append(x["term"])
        for v in x.values():
            _komut_terimleri(v, out)
    elif isinstance(x, list):
        for v in x:
            _komut_terimleri(v, out)


def yukle(kok=KOK, veri=None):
    s = Sozluk()
    for yol in kaynak_dosyalari(kok, veri):
        j = _json(yol)
        if not isinstance(j, dict):
            continue
        ad = os.path.basename(yol)
        if ad == "telaffuz.json":
            for e in j.get("entries") or []:
                if not e.get("tam") and e.get("okunus") and e.get("yazim"):
                    s.duzeltme_ekle(e["okunus"], e["yazim"])
        elif ad == "terimler.json":
            for d in j.get("duzeltmeler") or []:
                s.duzeltme_ekle(d.get("bozuk"), d.get("dogru"))
            for t in j.get("terimler") or []:
                s.terim_ekle(t)
        elif ad == "ders.json":
            t = []
            _komut_terimleri(j.get("sections"), t)
            for x in t:
                s.terim_ekle(x)
            for g in j.get("goals") or []:
                for sg in g.get("subgoals") or []:
                    if len((sg.get("text") or "").split()) <= 4:
                        s.terim_ekle(sg["text"])
        elif ad == "egitmen.json":
            for h in j.get("hedefler") or []:
                if len((h.get("baslik") or "").split()) <= 4:
                    s.terim_ekle(h["baslik"])
            for t in j.get("terimler") or []:
                s.terim_ekle(t)
    return s


class Onbellek:
    """Dosyalar değişince sözlüğü yeniden yükler."""

    def __init__(self, kok=KOK, veri=None):
        self.kok, self.veri, self.imza, self.sozluk = kok, veri, None, None

    def _imza(self):
        out = []
        for y in kaynak_dosyalari(self.kok, self.veri):
            try:
                out.append((y, os.path.getmtime(y)))
            except OSError:
                pass
        return tuple(out)

    def al(self):
        imza = self._imza()
        if imza != self.imza:
            self.sozluk, self.imza = yukle(self.kok, self.veri), imza
        return self.sozluk

    def duzelt(self, metin):
        return self.al().duzelt(metin)


if __name__ == "__main__":
    import sys
    s = yukle()
    print("%d terim, %d eşleme" % (len(s), len(s.duzeltmeler)))
    for m in sys.argv[1:]:
        print(json.dumps(s.duzelt(m), ensure_ascii=False))
