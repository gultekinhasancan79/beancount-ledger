# Gerçekçilik denetimi — minimaxai/minimax-m3, 2026-08-29

*Model, ajanın gördüğü sistem mesajını, görev metnini ve 8 dünya dosyasını satır numaralı olarak gördü; ayrıca denetçi-only olarak görev tanımını ve cevap anahtarını. Tek istek, araç yok, temperature 0.3.*

*Token: 5074 giriş, 2846 çıkış.*

---

## A. Genel izlenim

İlk bakışta "sentetik" diye ele veren şeyler az ama var: banka ekstresi 8 satır, defter 8 posting bloğu, müşteri/tedarikçi 3'er tane — hepsi küsurat içermeyen yuvarlak sayılarla (3500, 420, 8000, 4800, 9800, 14400, 12000, 7800, 2600, 5100, 6200). Gerçek bir küçük ticaret şirketinde KDV hariç tutarlar genelde tam sayı olabilir ama KDV'li satışlar, envanter alışları ve banka ücretleri bu kadar pürüzsüz olmaz; özellikle 85.00 dolarlık "monthly account service charge" gerçek bir bankada nadiren tam sayıdır. Yine de küçük bir şirket için "idare eder" düzeyinde; asıl sentetik iz, defterdeki her posting'in banka ekstresinde birebir karşılığının olması (yani defter zaten neredeyse mükemmen mutabık, sadece iki eksik var) — gerçek hayatta bir ayda en az bir tarih kayması, bir çift kayıt veya bir transpoze olur.

## B. Dosya dosya bulgular

### manifest.md
- Satır 6: "8 rows" ve "5 rows" (arşiv) doğru, ekstre formatı gerçekçi. Sorun yok.

### policy.md
- Satır 22–26: Prepayment kuralı net ve doğru (Aralık kirası Kasım'da ödenirse prepayment). Sorun yok.
- Satır 33–35: "Suspense/plug yok" kuralı iyi; ajanı yanlış yola çekmez. Sorun yok.

### accounts.csv
- 12 hesap, hepsi ledger'da açılmış. Sorun yok.
- Eksik: `Expenses:BankFees` zaten var, iyi. Gerçekçi.

### customers.csv / vendors.csv
- 3 müşteri, 3 tedarikçi — küçük şirket için makul. Sorun yok.
- "Harbor Freight Ltd" / "Summit Wholesale" / "Ridgeline Retail" isimleri biraz şablon gibi (coğrafi tema) ama küçük şirket için olağan.

### archive_prior_period.csv
- Satır 2: PI-2180, 4100.00 — Kasım'daki PI-2211 (6200) ile tutarlı bir artış. Sorun yok.
- Satır 3: SI-1029, 7250.00 — Kasım'daki satışlar 4000+12000 = 16000, tahsilatlar 9800+8000+4800 = 22600; önceki dönem 7250 ile uyumlu. Sorun yok.
- Satır 4: Check 1036, 3500.00 kira — Kasım'da check 1037 (3500) ve check 1038 (3500) var; check numarası sıralı artıyor, gerçekçi.

### ledger.beancount
- Satır 19–24: Açılış dengesi 42150.00 = Ekim kapanışı (arşiv satır 6). Tutuyor. Sorun yok.
- Satır 30–32: PI-2211, 6200.00 — ekstre satır 3 ile birebir. Sorun yok.
- Satır 34–36: SI-1043 tahsilat 9800.00 — ekstre satır 4 ile birebir. Sorun yok.
- Satır 38–41: SI-1044 satış 4800.00 (4000+800 KDV) — ekstre satır 8'de 4800.00 tahsilat var ama defterde bu tahsilat **yok**. Bu kasıtlı planted item.
- Satır 47–49: Kira 3500.00 check 1037 — ekstre satır 5 ile birebir. Sorun yok.
- Satır 51–54: SI-1051 satış 14400 (12000+2400 KDV) — KDV oranı %20, Kasım satışlarında tutarlı. Sorun yok.
- Satır 60–62: Office Depot 420.00 — ekstre satır 6 ile birebir. Sorun yok.
- Satır 64–66: PI-2240 alış 5100.00 — envanter hareketi, banka dışı. Sorun yok.
- Satır 68–70: Summit tahsilat 8000.00 — ekstre satır 7 ile birebir. Sorun yok.
- Satır 72–74: Check 1038, 3500.00 December prepayment — bankada görünmüyor (trap). Sorun yok, doğru bırakılmış.

### bank_statement.csv
- Satır 2: Açılış 42150.00 — defterle uyumlu. Sorun yok.
- Satır 8: 2025-11-26 ACH IN HARBOR FREIGHT LTD, SI-1044, 4800.00 — defterde karşılığı yok (planted).
- Satır 9: 2025-11-30 MONTHLY ACCOUNT SERVICE CHARGE, 85.00 — defterde karşılığı yok (planted). 85.00 tam sayı, gerçek banka ücretleri genelde 12.50, 15.00, 25.00 gibi küçük veya kuruşlu olur; buradaki 85.00 biraz sentetik.
- Genel format: "ACH OUT/IN", "CHECK ####", "DEBIT CARD", "MONTHLY ACCOUNT SERVICE CHARGE" — Cascade Bank gibi ABD bölgesel bankaların tipik ekstre dili. Gerçekçi.

## C. Görev senaryosu

- Görev metni kısa ve net: "ekstreyi al, defteri mutabık kıl, politika ne diyorsa onu uygula." Gerçek bir muhasebecinin alacağı iş. Sorun yok.
- Planted item'lar gerçekçi: kaydedilmemiş müşteri tahsilatı ve kaydedilmemiş banka ücreti, mutabakatlarda en sık karşılaşılan iki fark türü.
- Trap gerçekçi: henüz çıkış yapmamış çek (outstanding check) tipik bir zamanlama farkı.
- **Eksik fark türleri** (gerçek mutabakatlarda sık, burada yok):
  - NSF / karşılıksız çek (müşterinin çeki geri dönmüş)
  - Tarih kayması (defterde Aralık'ta, bankada Kasım'da görünen işlem)
  - Çift kayıt (aynı fatura iki kez ödenmiş)
  - Transpoze rakam (9800 yerine 8900 yazılmış)
  - Kesinti yapılmış tahsilat (müşteri 9800 yerine 9700 ödemiş, 100 kesinti)
  - Faiz / mevduat faizi
  - Otomatik ödeme (ACH OUT) ile manuel ödeme karışması
- Politika ile puanlama arasında haksız bir beklenti yok: her iki planted item da politika tarafından doğrudan emredilen hesaplara gidiyor (Expenses:BankFees ve Assets:AR). Sorun yok.

## D. Kanıt ve belirlenebilirlik

- **SI-1044 tahsilatı (4800.00):** Ekstre satır 8'de "ACH IN HARBOR FREIGHT LTD, SI-1044, 4800.00" yazıyor. Hem payee hem referans hem tutar üçlüsü tek bir sonuca işaret ediyor. Ajan başka bir faturaya yönlendirilemez. **Belirlenebilir.**
- **Banka ücreti (85.00):** Ekstre satır 9'da "MONTHLY ACCOUNT SERVICE CHARGE, 85.00". Payee yok, referans yok; ajan "Cascade Bank" yazmak zorunda (puanlama bunu şart koşuyor). Defterde Cascade Bank adı geçen tek yer `accounts.csv` satır 2 ("Cascade Bank checking account"). Ajan bunu bulabilir, ama "MONTHLY ACCOUNT SERVICE CHARGE" gibi jenerik bir açıklamadan "Cascade Bank" çıkarmak hafif tahmin gerektiriyor. **Kısmen belirlenebilir.**
- **Trap (check 1038):** Defterde narration'da "check 1038" açıkça yazıyor, banka ekstresinde yok. Ajan bunu kolayca outstanding olarak tanır. **Belirlenebilir.**
- Genel olarak ekstre, ajanın doğru kaydı tek şekilde yazmasına yetecek kanıt veriyor; başka bir muhasebeci aynı sonuca varır.

## E. Puanlar (1–5, tek satır gerekçe)

- **Gerçekçilik: 3** — Yuvarlak sayılar, tekdüze tutarlar, eksik fark çeşitliliği (NSF, tarih kayması, transpoze yok) sentetik iz bırakıyor.
- **Zorluk: 2** — Junior muhasebeci için çok kolay: sadece iki eksik posting, bir outstanding check, hepsi net.
- **Belirsizlik yokluğu: 4** — Kanıtlar yeterli, politika net, trap açıkça işaretlenmiş; tek hafif belirsizlik banka ücretinin payee'si.
- **Tuzak adilliği: 5** — Outstanding check gerçek hayatta en klasik zamanlama farkı, ajanı haksız yere cezalandırmıyor.

## F. En önemli 5 düzeltme

1. **Banka ücreti 85.00 tam sayı** — `bank_statement.csv` satır 9: gerçek bankalar 85.00 gibi yuvarlak bir service charge vermez; 12.50, 15.00 veya 87.43 gibi bir tutar daha inandırıcı olur.
2. **Defterdeki tüm tutarlar küsuratsız** — `ledger.beancount` genel: 420.00, 3500.00, 4800.00, 8000.00, 9800.00, 14400.00; en az bir-iki posting'e 17.43, 412.67 gibi küsuratlı tutar ekleyin.
3. **Tek bir fark türü seti** — Senaryo: NSF/karşılıksız çek veya tarih kayması gibi ikinci bir fark türü ekleyin; şu an iki planted item da "kaydedilmemiş banka hareketi" şablonunda.
4. **Müşteri/tedarikçi isim çeşitliliği** — `customers.csv` ve `vendors.csv`: üçü de coğrafi/doğa temalı ("Harbor", "Summit", "Ridgeline", "Northwind", "Cedar"); birinde endüstriyel veya kişisel isim olsa daha gerçekçi.
5. **Banka ücreti payee kanıtı zayıf** — `bank_statement.csv` satır 9: "MONTHLY ACCOUNT SERVICE CHARGE" açıklaması Cascade Bank adını içermiyor; ajanın doğru payee'yi bulması için ekstre açıklamasına "CASCADE BANK" ekleyin veya `accounts.csv`'deki banka adını ekstre başlığına taşıyın.
