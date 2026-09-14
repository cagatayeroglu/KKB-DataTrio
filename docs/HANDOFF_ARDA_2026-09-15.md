# DataTrio — Arda oturumu devir notu

Tarih: 15 Eylül 2026 (Türkiye saati). Görev: M10-18 seçili sonuç üzerinden takip sorusunun doğru tabloya bağlanması.

## Doğrulanmış Git durumu

- PR #166 **dev içine birleştirildi**: https://github.com/cagatayeroglu/KKB-DataTrio/pull/166
- Merge commit: `de11f3eb919ccf13920852501e359d8476117e9a`.
- Birleştirilen görev HEAD'i: `09eb827c3efdea88e65187f5482437bb38fb3876`.
- Tam bu HEAD için **Fast PR gate** ve **Web client gate** başarılı. Kontrollerin kendi head_sha alanı doğrulandı.
- Fetch sonrasında görev HEAD'inin ve merge commit'inin `origin/dev` geçmişinde olduğu doğrulandı.
- #165 doküman kapanışı da `0a3cf4e2ee28168b348ae5e6ff57d4647529ac49` ile dev içine birleştirildi; kendi HEAD'inin Fast PR/Web CI kontrolleri başarılı.
- `main` değiştirilmedi. Bu son devir güncellemesi #167 üzerinden taşınır; yeni ürün işi sahiplenilmez.

## Neler yapıldı?

1. Kullanıcının ekranda seçtiği yayımlanmış sonuç, sonraki sorunun açık kaynak tablo kimliği olarak API'ye taşınıyor. En son sonuç yerine daha eski bir tablo seçilebilir.
2. API seçimin aynı oturuma ait, kabul edilmiş ve yayımlanmış bir sonuç olduğunu denetliyor. Sonuç kimliği, workspace içindeki tablo/artifact ve sürümle bağlanıyor.
3. Registry'nin tanımladığı tablo girdileri üzerinden planner ve executor seçili kaynak bağlantısını zorunlu kontrol ediyor. Yanlış tablodan hesaplama sessizce kabul edilmiyor; sınırlı plan düzeltmesi var.
4. Yayımlanan türetilmiş sonuç, kaynak tablo bağımlılığını atomik olarak kaydediyor. Seçili kaynak yeniden bağlandığında bu türevler eski olarak işaretleniyor. Önceki yayımlanmış sonuçlar başarısız takip sorusunda kaybolmuyor.
5. Arayüz soru metnini, istek kimliğini ve seçili kaynak kimliğini POST'tan önce birlikte kaydediyor. Yeniden deneme aynı kaydı kullanıyor; güncel ekran seçimini sonradan isteğe uygulamıyor.
6. Sayfa yenilendiğinde eski tablo seçimi korunuyor. Kesin API reddi ile sonucu belirsiz bağlantı hatası ayrılıyor. Bekleyen istek varken kaynak seçimi kilitleniyor; kurtarma gerektiğinde doğru istek kullanılıyor.
7. “Seçili tabloyla devam et” kapatılınca belirli tabloya sabitlenmeyen serbest soru gönderiliyor. Bu seçenek backend analiz geçmişini silmiyor.
8. Tekrarlanabilir, yalnız sentetik veri ve önceden belirlenmiş planlar kullanan manuel prova başlatıcısı eklendi: `tests/manual/selected_client.py`. Altı adımlık kullanım tarifi `docs/LOCAL_CLIENT.md` içinde.

## Kabul kanıtı

- Önceki backend gate: 3326 test başarılı, 2 atlandı; Ruff, strict mypy, Bandit ve sır taraması başarılı. Sonradan mevcut executor sınırı ve seçili çalışma regresyonları için 50 test de geçti.
- Arayüz: 23 test, TypeScript, biçim kontrolü ve üretim derlemesi başarılı.
- Yeni manuel prova başlatıcısı: başlangıç denemesi ve Ruff lint/format başarılı.
- Son doküman kontrolü: 466 yerel bağlantı/anchor, `git diff --check` ve sır taraması başarılı.
- Üretim Next arayüzü + gerçek PreparedRunner/API/hesaplama araçları + sentetik havuzla tarayıcı kabulü geçti: ilk tablo; TÜFE ekleme; eski tablo seçip yenileme; sunucu kabulünden sonra bir defalık 503; yenilemeden sonra aynı isteği kurtarma; havuzda olmayan seride çekimser yanıt; kontrollü 422 reddi; ardından serbest soru.
- İlk stok değerleri 100/120/150 milyon TL korundu; eklenen endeks değerleri 100/110/120 idi. Kayıp yanıtın tekrarında aynı istek/kaynak kimliği kullanıldı, ek model işi oluşmadı.
- 390×844 dar ekranda seçim kontrolleri çalıştı; belge genişliği ve kaydırma genişliği 375px idi, yatay taşma yoktu. Geçici ekran boyutu geri alındı; prova sunucuları kapatıldı.
- Bunlar önceden belirlenmiş sentetik planların kabulüdür. Canlı Kloudeks veya gerçek veri üzerinde keyfi soru başarısı olarak yorumlanmamalıdır.

## Açık sınırlar

- Seçili tablo zincirinin canlı Kloudeks kabulü henüz yapılmadı; bu oturumda canlı model/kaynak çağrısı yok.
- Eski/seçimsiz bütün analizlerin ve resmi veri yenilemesinin genel bağımlılık/geçersizleşme kapsamı tamamlanmadı.
- Tam kaynak → dönüşüm → hücre kanıt grafiği arayüzü ayrı iş olarak açık.
- Genericlik, desteklenen yeni finansal kaynak/veri kümesi/şemaların çekirdeği yeniden yazmadan eklenmesidir; rastgele alanlar veya sağlık verisi desteği vaat edilmez.

## Dal temizliği ve devir

`codex/selected-workspace-resolution` (#166) ve `codex/docs-genericity-completion` (#165) dalları kullanıcı onayıyla GitHub'dan ve yerelden silindi. Silmeden önce commit'lerin `origin/dev` içinde olduğu ve başka worktree/PR bağımlılığı bulunmadığı doğrulandı.

Bu not son [doküman kapanışı #167](https://github.com/cagatayeroglu/KKB-DataTrio/pull/167) için hazırlanmıştır. M10-18 ürün kodu #166 ile zaten dev'e girmiştir. [ROADMAP](ROADMAP.md#current-project-status) M10-18'i merge kanıtıyla DONE olarak kaydeder. Geçici doküman hazırlık claim'i yeni bir ürün görevi veya başka bir kapanış PR'ı gerektirmez. Devir alan kişi açık PR ve branch durumunu Git üzerinden doğrulamalıdır.

Desktop checkout: `C:/Users/Cabaroglu/Desktop/KKB-DataTrio`. Takip edilen yerel değişiklik bulunmadığı ve çalışan Git süreci olmadığı doğrulandı. Eski sıfır baytlık kilide münhasır erişim kontrolü yapıldı; `.git/index.lock`, silinmeden `.git/index.lock.handoff-20260915` adıyla yedeklendi. Desktop dev yalnız `pull --ff-only` ile güncel ürün checkpointini içerecek biçimde güncellendi. Takip edilmeyen `Claude outputs/` kullanıcı içeriği, stash ve main korundu. Yeni çalışmaya başlamadan yine Git durumunu kontrol et.

İzole çalışma kopyaları `work/kkb-selected-result`, `work/kkb-genericity-scope`, `work/kkb-active` ve `work/kkb-coverage` içindedir; geçici/önceki checkout'lar yeni özellik dalları değildir. Yeni işe başlamadan güncel dev'i esas al; eski detached checkout'tan devam etme.

## Sıradaki güvenli adım

1. Güncel dev'i fetch/pull --ff-only ile al; çalışma ağacını, açık PR'ları ve AGENTS.md kurallarını kontrol et. Ürün kodu ve devir dokümanını aynı güncel dev üzerinden oku.
2. Yeni ürün görevini güncel ROADMAP ve sahiplik durumuna göre seç. Bu devirde yeni bir ürün görevi veya canlı çağrı sahiplenilmedi.
3. Önerilen sonraki kabul çalışması, ayrıca açık canlı çağrı izni ve sınırlı çağrı bütçesiyle gerçek hazırlanmış havuzda seçili/eski tablo üzerinden Kloudeks üç turlu tekrar denemesidir. Canlı sonuçlarla doğrulanmayan davranışı tamamlanmış sayma. Genel refresh, tam kanıt arayüzü ve diğer açık işleri bu dar kabulün içine gizlice ekleme.

Başlangıç için: [AGENTS](../AGENTS.md), [ROADMAP](ROADMAP.md#current-project-status), [yerel arayüz ve tekrar tarifi](LOCAL_CLIENT.md#repeat-the-finite-synthetic-selection-rehearsal), [tarayıcı kabul kanıtı](EVALUATION.md#m10-18-browser-selection-2026-09-15).
