# Video Studio

Senaryo yaz -> sesli, altyazılı, yapay zeka görselli video al. Tamamen ücretsiz katmanlarla.

Vercel (arayüz + API) -> Supabase (veritabanı + video depolama) -> GitHub Actions (ffmpeg ile render)

## Kurulum

1. **Supabase**: yeni proje aç. SQL Editor'da `supabase/schema.sql` dosyasını çalıştır.
   Project Settings > API: `Project URL` ve `service_role` anahtarını not al.
2. **GitHub**: bu klasörü yeni bir repoya (örn. `acusoftware/video-studio`) `main` dalına yükle.
   - Repo > Settings > Secrets and variables > Actions: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` ekle.
   - Hesap > Settings > Developer settings > Fine-grained tokens: sadece bu repo, izin `Actions: Read and write`. Token'ı not al.
3. **Vercel**: repoyu import et. Environment Variables: `.env.example` içindeki 6 değişkeni gir. Deploy.
4. Siteyi aç, şifreyi gir, senaryoyu yaz, "Videoyu oluştur".

## Senaryo biçimi

- Her satır bir sahne. Uzun satırlar cümle sınırından bölünür.
- Görsel tarifi için satıra `[img: ingilizce tarif]` ekle. Yazmazsan sahne metni tarif olarak kullanılır.

## Süre

- En fazla 11500 karakter (≈ 12 dakika). Sınırı `lib/limits.js` içinden değiştirebilirsin.
- 12 dakikalık video için render 10-25 dakika sürer.

## Sınırlar

- Supabase ücretsiz: dosya başına 50 MB (12 dk video yaklaşık 15-30 MB), toplam 1 GB (eski videoları Storage'dan sil), 1 hafta işlem olmazsa proje duraklar.
- GitHub Actions: public repoda sınırsız, private repoda ayda 2000 dk.
- Ses (edge-tts) ve görsel (Pollinations) ücretsiz ama resmi garantisi olmayan servislerdir.
