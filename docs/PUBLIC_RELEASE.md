# Public kod paylaşımına geçiş

Bu işlem GitHub deposunun görünürlüğünü değiştirir. Backend/frontend'i internete
açmaz, API erişimi sağlamaz ve açık kaynak lisansı vermez. Haklar
[COPYRIGHT.md](../COPYRIGHT.md) dosyasında açıklanır.

## Kapsam ve karar

- Yayın temeli: final `main`, `b6f8a3d409216413f6ce04f517631be53e42cf61`.
- Hazırlık: [PR #322](https://github.com/cagatayeroglu/KKB-DataTrio/pull/322);
  yalnız dokümantasyon. Runtime, kaynak/test dosyaları, `.env` ve hazırlanmış
  veriler değişmez. Eski `dev` ürün değişiklikleri bu yayına taşınmaz.
- Çağatay, 27 Ekim 2026'da kodun paylaşılabildiğini teyit etti ve açık kaynak
  kullanım izni verilmemesini seçti. Bu, veri yeniden dağıtım izni değildir.
  Karar kaydı: [DEC-192](DECISIONS.md#dec-192--public-code-visibility-without-an-open-source-license).
- Kontrol kapsamı ve sınırları:
  [yayın öncesi inceleme](EVALUATION.md#public-visibility-review-2026-10-27).

## Görünürlüğü değiştirmeden önce

1. PR #322'yi inceleyip `main` dalına birleştirin. `COPYRIGHT.md` ve README'deki
   paylaşım notunun `main` üzerinde bulunduğunu doğrulayın.
2. İncelemeden sonra yeni kod, veri, yorum, ek veya Actions çıktısı eklenmişse
   değişen içeriği de kontrol edin. Kontrol sonucu yalnız incelenen kapsam ve
   revizyonlar için geçerlidir.
3. `.env`, API anahtarları, konuşma/state klasörleri, özel belgeler ve
   `data/processed/` içeriğini eklemeyin. `.gitignore`, daha önce commit edilmiş
   bir dosyayı geçmişten silmez. Gerçek bir anahtar bulunursa önce iptal/rotasyon
   yapılmalı; geçmiş veya log temizliği ayrıca planlanmalıdır.
4. Yalnız `main` değil, deponun diğer dalları, Git geçmişi, PR/issue yazışmaları
   ve erişilebilir Actions logları da görünür hale gelir. Public olduktan sonra
   alınan kopyalar ve fork'lar, depoyu tekrar private yapmakla geri alınmaz.

## GitHub'da yapılacak işlem

1. [Repository Settings](https://github.com/cagatayeroglu/KKB-DataTrio/settings)
   sayfasını açın.
2. **General → Danger Zone → Change repository visibility → Change to public**
   yolunu izleyin.
3. Gösterilen deponun `cagatayeroglu/KKB-DataTrio` olduğunu kontrol edip GitHub'ın
   görünürlük onayını tamamlayın.
4. Oturum açılmamış bir pencerede README ve haklar bildirimini kontrol edin.
   **Settings → Code security** altında sunulan secret scanning/push protection
   durumunu inceleyin; bir gerçek anahtar uyarısını yalnız kapatmak yerine ilgili
   anahtarı iptal edin. İmkân varsa private vulnerability reporting'i açın;
   anahtar veya özel belge içeren güvenlik bildirimlerini public issue'ya koymayın.

Bu hazırlık otomatik merge, görünürlük değişikliği, geçmişin yeniden yazılması
veya runtime deployment yapmaz.

## Kurulum ve veri

Kurulum komutları [README](../README.md#1-jüri--fresh-clone-quickstart) içindedir.
Hazır lakehouse ve katalog indeksinin Git dışında olması bilinçlidir. Kullanıcı
kendi yetkili erişimiyle veri hazırlamalı ve gerekli Kloudeks erişimini
sağlamalıdır. Kaynak kodun public olması, veri sağlayıcılarının kullanım
koşullarını veya mevcut runtime sağlayıcı sınırlarını değiştirmez.

GitHub referansları:
[görünürlük değişikliği](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)
ve [lisans olmadan public paylaşım](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository).
