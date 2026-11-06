# Gerçek hastadan vaka hazırlarken: anonimleştirme listesi

Gerçek bir hastadan uyarlanan vaka kartında (`"kurgusal": false`) `anonimlik` bölümü zorunludur ve
aşağıdaki maddeler karşılanmadan vaka denetimden geçmez. Bu liste hukuki danışmanlık değildir;
kurumunuzun etik kurul ve kişisel veri (KVKK) kurallarına da uyun.

## Metin

- [ ] Ad, soyad, baş harf, dosya ya da protokol numarası, T.C. kimlik numarası yok.
- [ ] Tam tarih yok: "3 gün önce", "6 ay sonra" gibi göreli süre kullanıldı.
- [ ] Tam yaş yerine on yıllık aralık yazıldı (`40-49`). 90 yaş üstü `90+`.
- [ ] Meslek, adres, okul, kurum, nadir hastalık gibi kişiyi tanıtabilecek ayrıntılar çıkarıldı ya da genelleştirildi.
- [ ] Telefon, e-posta, adres yok.

## Görseller

- [ ] Yüz, göz, dövme, takı, belirgin ben gibi tanıtıcı bölgeler kırpıldı; yalnız ağız içi görünüm kaldı.
- [ ] Radyografi ve fotoğraf üzerinde ad, tarih, kurum yazısı yok.
- [ ] Dosya adlarında kişisel bilgi yok (`v1-on.jpg` gibi adlandırıldı).
- [ ] Fotoğrafın dosya bilgileri (EXIF: tarih, cihaz, konum) silindi.

## Onam ve onay

- [ ] Hastanın eğitimde kullanım için onamı var (`"egitim_onayi": true`).
- [ ] Denetimi yapan öğretmenin adı ya da baş harfleri ve tarih yazıldı (`denetleyen`, `tarih`).
- [ ] Klinik içerik öğretmen tarafından gözden geçirildi (`ogretmen_onayi`).

## Dağıtım

- Gerçek hastadan uyarlanan vakalar varsayılan olarak **fakülteye özeldir**: dosya adını `ozel-` ile başlatın
  ve `"dagitim": "fakulte"` yazın. Böyle bir kart açık depoya giremez.
- Meslektaşlarla paylaşılacak anonim vaka havuzu 4. aşamadadır; her vaka orada ayrıca öğretmen onayından geçecektir.
