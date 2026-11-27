# Eğitmen metinleri: değişiklik günlüğü

Bu dosya eğitmenlere gönderilmez; yalnız bizim içindir. `ortak.md`, `inci.md` ve `mercan.md` dosyalarında neyin, ne zaman ve neden değiştiğini tutar.

Program her öğrenci kaydına bir **sürüm damgası** yazar: programın sürümü, eğitmen ve eğitmen metninin parmak izi ("kural izi": `ortak.md` ile kişilik dosyasından hesaplanan on haneli kod). Metin değişince iz kendiliğinden değişir. İz neyin değiştiğini söylemez; onu bu günlük söyler. Güncel izleri görmek için: `python tools/tahta-mcp.py --kural-izi`.

Kural: Eğitmen metinleri Kemal Üstün'ün onayı olmadan değişmez. Her değişiklik buraya tarihiyle yazılır; sürüm yayımlanınca o sürümün izleri eklenir.

## 4.1.2 (yayımlandı: 27 Kasım 2026)

Yayımdaki kural izleri: `inci` 73aa226834, `mercan` e01a157225, `nilgun` 698004732a.

Kemal Üstün'ün yayım kararı (27 Kasım 2026, 18:50): sürüm yayımlanır, denemeleri gerçek öğrenciler yapar, sonraki düzenlemeler gelen veriye göre yapılır. Bu yüzden Nilgün'ün yayım öncesi güvenceleri (akut lezyonlardan üç sınavın cevap anahtarı denetimi, aynı on cevabın üç kez puanlatılması) ve iki kural yükü önlemi yayım koşulu olmaktan çıktı; yayımdan sonra izlenecek. Dayanak eşiği değişmedi (`ZAYIF_KABUL = False`: dayanağı zayıf soru sınava girmez); öğrenci verisiyle yeniden değerlendirilecek.

### 2026-11-27 — Kemal Üstün'ün tek tek onayladığı değişiklikler

| Dosya | Değişiklik | Neden |
| --- | --- | --- |
| `inci.md` | Klinik akıl yürütme yöntemlerine "Tedavi kararı (kural ve istisna)" eklendi. | İnci'nin yöntemlerinin hepsi tanıya yönelikti; işlemsel hedefler (ör. akut lezyonlarda NG bakımı, perikoronitis, apse, antibiyotik kararı) yöntemsiz kalıyordu. |
| `ortak.md` §2 | Bitiş önerisi: yaklaşık 20. dakikada bir kez; "devam" denirse yinelenmez; cevapla aynı cümlede verilmez. | Kemal'in 14 Kasım 2026 işleyiş kararı metne girmemişti. |
| `ortak.md` §2 | Yeni madde: "Senin çalışmak istediğin bir konu var mı, yoksa ben mi seçeyim?" (oturumda bir kez). Sonraki maddelerin numarası bir kaydı. | Öz düzenleme: hedefi öğrencinin de seçebilmesi. Cümle Kemal'in. |
| `ortak.md` §6 | Güven sorusu yalnız olgu sorularında değil, bilinen bir yanılgıyı yoklayan sorularda da sorulur; aynı yanılgı için oturumda en çok bir kez. Bölüm başlığı değişti. | "Emin ama yanlış" düzeltmesi en çok yanılgılarda işe yarar; Mercan az olgu kullandığı için güven sorusu orada neredeyse hiç sorulmuyordu. |
| `ortak.md` §9 | Kapanış sorusu: "Bugün anlamakta en çok zorlandığın neydi?" Cevap `oturum.zorlandigi` alanına yazılır ve sonraki oturumda kayıt özetinde (`son_zorlandigi`) görünür. | Öz düzenleme: öğrencinin kendi zayıf yerini adlandırması. Cümle Kemal'in. |
| `mercan.md` | "Konu ve klinik protokol araç seti (ikinci araç seti)" eklendi. | Üç Mercan dersi de makale inceleme setine bağlıydı; irigasyon dersinin 8 hedefinden 7'si makale eleştirisi değil, konu ve klinik karar. Uzmanlık düzeyinde klinik akıl yürütme yöntemi de yoktu. |
| `mercan.md` giriş | Konu tanımı elindeki araçlarla sınırlandı: makale inceleme, konu ve klinik protokol; istatistik bu tartışmaların içindeki yanılgılar üzerinden. Tez değerlendirme için araç seti olmadığı açıkça yazıldı. | Metin "tez değerlendirme, istatistik ve araştırma yöntemi" vaat ediyordu ama bunların yöntemi yoktu. Tez seti, ilk tez dersi gerektiğinde yazılacak. |
| `mercan.md` Üslup | Dört satır eklendi: doğru gözlemi adıyla teslim etme, otoriteyle değil kaynakla konuşma, emin olunmayan yeri gösterme, ölçülü espri. | Mercan'ın dosyası üç satır üslup, gerisi araç listesiydi; İnci kadar belirgin bir sesi yoktu. |
| `nilgun.md` (yeni) | Nilgün'ün metni: üslup, değişmeyen kurallar, sınavdan önce, sınav, sınavdan sonra. Ortak çekirdeği yüklemez; kendi kısa çekirdeği var. | Yeni sınav personası (aşağıda). Program desteği gelene kadar dosya hiçbir yerde yüklenmez. |
| `ortak.md` §11 (yeni) | Sınav isteği Nilgün'e bırakılır; eğitmen sınav yapmaz, sınav önermez. Sınavdan dönüşte öğrenci "sen seç" derse sınavda zayıf kalan hedeflerden başlanır; puan gündeme getirilmez. | Nilgün'ün gelişiyle eğitmenlerin sınav işi ona geçti (`sozlu_prova` aracı kalktı). |

Aynı gün alınan, metne girmeyen karar: ara düzeyler için şimdilik değişiklik yok (yalnız not).

### Nilgün: Kemal Üstün'ün 27 Kasım 2026 kararları

- Yalnız öğrenci isteyince açılır. İnci ve Mercan sınav yapmaz, sınav önermez.
- Öğrencinin öz denetimi ve sınava hazırlığı içindir; bizim için değildir. Sonuç öğrencinin cihazında kalır, öğretmene gitmez, anonim araştırma aktarımına girmez.
- Soruları, cevap anahtarını ve rubriği sınavdan önce hazırlar. Sınav planı: dersin hedefleri × Bloom düzeyi.
- Kapsam sabit, güçlük değişir. Puan hedef başına: hedef düzeyinde tam 2, kısmen ya da yalnız alt düzeyde 1, hiçbiri 0.
- İlk sürümde yalnız programdaki derslerden sınav yapar. Pilot ölçme formları Nilgün'e kapalıdır.
- Sözlüde cevap kendiliğinden gönderilmez; öğrenci düzeltebilir ve "Cevapla" ile gönderir.
