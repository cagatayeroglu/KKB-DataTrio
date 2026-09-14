# Arda oturumu — ekip için çalışma özeti

Bu özet, Eray'dan alınan `2394aa7` devir sürümünden `31bb506` sürümüne kadar
yaptığımız işleri kapsar. Önceki ekibin yazdığı temel lakehouse, araçlar, ilk
kredi/faiz analizi ve enflasyondan arındırma bize ait yeni işler olarak sayılmadı.
İlk görev commitinden son uygulama birleştirmesine Git'te yaklaşık **5 saat
7 dakika** görünüyor; bu süre aktif yazma süresinin ayrı bir ölçümü değildir.

| Ölçüm | Devralınan durum | Bu oturum sonunda |
|---|---:|---:|
| Hazır veri kapsamındaki seri | 7 | **29** |
| Sayısal gözlem | 683 | **4.124** |
| Katalogdaki seri kaydı | 10 | **37** |
| Katalogdaki kavram | 14 | **46** |
| Katalogdaki alternatif ifade kaydı | 51 | **139** |
| Python test senaryosu | 2.885 | **3.283** |
| Frontend test senaryosu | 0 | **16** |
| Python kaynak dosyası | 83 | **98** |
| Python birim test dosyası | 68 | **81** |
| Çalışan tarayıcı arayüzü | Yok | **İlk sürüm hazır** |

**Veriyi hazırladık ve genişlettik.** Önce devraldığımız yedi seriyi Arda'nın
bilgisayarında hazırladık. Sonra dokuz haftalık kredi faiz serisi ve on üç aylık
TÜFE harcama grubu ekledik. İhtiyaç, taşıt, ticari ve tüketici kredisi faizleri;
gıda, sağlık, eğitim ve ulaşım gibi fiyat endeksleri artık havuzda. Böylece
**22 seri ve 3.441 gözlem** eklendi. Kaynak hâlâ BDDK ve TCMB EVDS; 29 seri,
29 ayrı kurum veya dosya demek değil. Yerel havuz yaklaşık **8,13 MiB**.
Eski yedi-serilik kopya korundu. Tüm BDDK/EVDS kapsamı henüz hazır değil.

**Üçüncü sorunun hesaplama kısmını tamamladık.** Mevcut tabloya yeni seri ekleyen
`add_series` işlemini ve tablodaki serilerin birlikte hareketini hesaplayan
`table_co_movement` işlemini yazdık. Bunlar yalnız KFE adına bağlı işlemler değil;
desteklenen anlam ve aylık dönem kurallarını sağlayan başka serilerde de
kullanılabilir. İlk tablolar korunuyor, yeni sonuç ayrı sürüm oluyor.
KFE eklenirken önceki **302 değer** korundu, eklenen **60 KFE değeri** ayrı
hesapla kontrol edildi. Ortak koşulu sağlayan **22 dönem**, bağımsız hesapla
eşleşti. Bu sonuç neden-sonuç kanıtı olarak sunulmuyor.

**Modelin bilgiye erişmesini geliştirdik.** Katalog artık kullanıcının ifadesini
daha fazla gerçek veri serisiyle eşleştirebiliyor. LanceDB üzerinde
**4.096 boyutlu** vektör saklama/arama ve BM25 ile vektör adaylarını birleştirme
altyapısı eklendi. Ayrıca modelin katalogdan gelen adayları okuyup bir sonraki
analiz planını kurabildiği sınırlı devam adımı yazıldı. Gerçek Kloudeks
embedding kullanımı ve anlamsal arama başarısı henüz canlı olarak kabul edilmiş
değil; bunu tamamlanmış bir canlı RAG sistemi diye anlatmıyoruz.

**Harness'ın zorunlu kontrollerini artırdık.** Hazırlanmış veriyi kullanan
yapılandırmada, hesap öncesi serinin katalogdaki tanımıyla depodaki tanımı
karşılaştırılıyor: birim, ölçek, dönem sıklığı, stok/akım/faiz/endeks ayrımı,
kümülatiflik ve gerekli baz yılı gibi bilgiler. Model bu denetimi isteğe bağlı
olarak atlayamıyor. Yanlış veya bilinmeyen bilgi varsa sistemin durması ya da
netleştirme istemesi sağlanıyor. Genel veri kalitesi ve kaynaklar arası
uzlaştırmanın bütün kapsamı henüz bitmedi.

**Backend'i arayüze bağladık.** Python uygulamasına oturum açma, soru gönderme,
işlem durumunu öğrenme, yayımlanan sonucu ve hazır veri kapsamını alma uçları
eklendi. Her oturumun verisi ayrılıyor; yinelenen isteklerin aynı analizi
yanlışlıkla tekrar başlatması ve başarısız yanıtta eski tablonun kaybolması
kontrol ediliyor. Yerel sınırlar: **8 oturum, oturum başına 24 soru, aynı anda
1 analiz**. Bu, internete açık çok kullanıcılı ürün değil.

**İlk frontend'i yaptık.** Next.js ile tek ekranlı, masaüstü ve mobil uyumlu
analiz alanı; soru kutusu, tablolar, eski sonuç sürümleri, hücre ayrıntıları,
veri havuzu paneli ve bilgi amaçlı ayarlar eklendi. Tabloyu model yeniden
yazmıyor; arayüz hesaplama kodunun yayımladığı değerleri gösteriyor. Üç soruluk
prova **242 → 302 → 368 kayıtlı değer** üretti. Sayfa yenileme, önceki sonuca
dönme ve belirsiz soruda son tabloyu koruma kontrol edildi. Grafik, dosya
yükleme, veri yenileme işi ve değiştirilebilir agent ayarları sonraki işler.

**Teknik sorunları giderdik.** Windows'ta bağlantı işçisinin ilerlemesini yanlış
yorumlayan zaman aşımı davranışı, dosya/işlem kapatma ve satır sonu sorunları
düzeltildi. Yeni ölçümde görülen **64 tip kontrolü hatası sıfırlandı**; bu kontrol
her PR'ın normal kontrolüne alındı. Frontend bağımlılıklarının örnek dosyaları
secret taramasını bozunca yalnız üretilen klasörler dışarıda bırakıldı; kendi
kaynaklarımızın ve ayar dosyalarımızın taranması korundu.

**Test ve Git özeti:** Net **398 Python + 16 frontend = 414 ek test senaryosu**.
Python tarafında 168 yeni adlandırılmış test fonksiyonu var; bir eski fonksiyon
adı değiştiği/kalktığı için fonksiyon sayısı net 167 arttı. Senaryo sayısına
parametreli testlerin farklı girdileri de dahildir; binlerce eski testi yeni
yazmışız gibi saymıyoruz. Son yerel koşum: **3.281 geçti, 2 Windows yetki testi
atlandı**. Frontend'in 16 testi, üretim derlemesi, tip/lint/güvenlik kontrolleri
geçti. #159'un iki GitHub kontrolü de başarılı.

İşler **13 PR** (#148–160), **41 normal commit** ve birleştirme kayıtlarıyla
saklandı. Toplam 114 dosya değişti; 63 yeni dosya eklendi. Git farkı 21.195 ek,
222 çıkarılmış satır gösteriyor; bunun katalog ve bağımlılık kilidi gibi
bildirim dosyalarını da içerdiğini unutmamak gerekir. Salt uygulama kaynakları
ve arayüz dosyalarında 7.089 ek satır var. Satır sayısı kalite puanı değildir.
Bu rapor/devir dokümantasyonu PR #161 bu geliştirme sayılarına dahil değildir.

**Kurallar ve gerçek durum:** Python hesaplama motoru, kendi harness'ımız,
DuckDB/Parquet ve yerel LanceDB yaklaşımı korundu. Uygulamanın model yolu
Kloudeks; çalışma sırasında Claude/Codex/OpenAI-hosted ajanına analiz
yaptıran yol eklenmedi. Anahtarlar frontend'e veya Git'e konmadı; hazırlanmış
veri Git dışında tutuldu. Repo private, geliştirmeler ayrı görev dallarında,
izinli birleştirmeler `dev` dalında; `main` değiştirilmedi.

Canlı Kloudeks ile bu oturumda **iki soruluk başarılı prova** var; ilk denemede
zaman aşımı da görüldü. Yeni üçüncü soru ve frontend akışı ise gerçek veriler
üzerinde **scripted/kontrollü prova** ile doğrulandı. Üç tur canlı Qwen, canlı
embedding kalitesi, bütün istenen veri kapsamı, genel günlük/haftalık işlemler,
üretim web araması, tam kanıt ekranı ve dağıtım henüz tamamlanmadı. Dolayısıyla
teknoloji/güvenlik sınırlarına uygun ilerledik; ürünün bütün yarışma beklentilerini
tamamladığını veya jüriye kesin hazır olduğunu söylemiyoruz.

Kanıtlar: [EVALUATION](EVALUATION.md), [çalıştırma rehberi](LOCAL_CLIENT.md),
[teknik devir](HANDOFF_ARDA_2026-09-14.md). Sayım aralığı değişmeden sabittir:
`2394aa785f7cc13abb8e263b8f22d86ce62da31f` →
`31bb506e27a5917eebb4e6851938a3b2a7ada7b2`.
