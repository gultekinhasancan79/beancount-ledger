# Gerçekçilik denetimi — openai/gpt-oss-120b, 2026-08-29

*Model, ajanın gördüğü sistem mesajını, görev metnini ve 8 dünya dosyasını satır numaralı olarak gördü; ayrıca denetçi-only olarak görev tanımını ve cevap anahtarını. Tek istek, araç yok, temperature 0.3.*

*Token: 4778 giriş, 5710 çıkış.*

---

## A. Genel izlenim
Genel bakışta dosyalar tutarlı bir küçük ticaret şirketinin muhasebe defteri ve bir banka ekstresi gibi görünüyor; ancak tutarlılık “sentetik” izleri taşıyan birkaç nokta var. Özellikle tutarlarda (ör. 6200, 4800, 3500) tekrarlanan yuvarlak sayılar, tarihlerin haftalık periyotlarla eşit aralıkta olması ve bazı işlem açıklamalarının (ör. “ACH OUT …”) çok standart biçimde tekrarlanması, dosyaların gerçek bir işletmeden ziyade bir test ortamı için elle hazırlanmış olduğunu düşündürüyor.

---

## B. Dosya dosya bulgular  

### 1. `manifest.md`  
- **Satır 6**: “8 rows” ifadesi banka ekstresinin sadece 8 satır içerdiğini söylüyor; gerçek bir ayda 8 işlem çok azdır.  
  **Düzeltme:** Gerçekçi bir ay için 20‑30 işlem satırı eklenebilir.  

### 2. `policy.md`  
- **Satır 34‑35**: “Alpine does not operate a suspense or plug account.” Gerçek işletmelerde bazen geçici hatalar için kısa vadeli “Suspense” hesapları bulunur; bu kuralın mutlak olması gerçekçi olmayabilir.  
  **Düzeltme:** “Genellikle kullanılmaz, ancak gerekli durumlarda geçici bir suspense hesabı açılabilir.” şeklinde not eklenebilir.  

### 3. `accounts.csv`  
- **Satır 2‑13**: Hesap adları ve tipleri tutarlı, ancak **type** sütununda “asset”, “liability” gibi tekil isimler yerine “Asset”, “Liability” gibi büyük harfle başlamak yaygın bir konvansiyondur.  
  **Düzeltme:** Tip değerlerini “Asset”, “Liability”, “Income”, “Expense”, “Equity” olarak güncelle.  

### 4. `customers.csv` & `vendors.csv`  
- **Satır 2‑4**: Müşteri ve tedarikçi isimleri “Ltd”, “Group” gibi kurumsal eklerle bitiyor; tek bir karakteristik örnek olması (3 satır) gerçek bir veri seti için çok sınırlı.  
  **Düzeltme:** En az 5‑7 farklı müşteri/tedarikçi eklenebilir.  

### 5. `archive_prior_period.csv`  
- **Satır 2‑6**: Tüm tutarlar yuvarlak ve aynı para birimi (USD). Gerçek geçmiş dönemlerde bazı kurlar, kâr/zarar farkları veya küsuratlı tutarlar bulunur.  
  **Düzeltme:** Birkaç satıra %0.5‑%1.5 arasında küsurat eklenebilir.  

### 6. `ledger.beancount`  

| Satır | Bulgu | Neden gerçekçi değil? | Düzeltme önerisi |
|------|-------|----------------------|------------------|
| 30‑33 | **Satın alma** “Northwind Supplies” kaydında **Assets:Inventory** hiç etkilenmemiş. | Stok alımı gerçekleştiği halde envanter hesabı güncellenmemiş; gerçek bir defterde stok artışı mutlaka kaydedilir. | Satır 30‑33’a `Assets:Inventory 6200.00 USD` eklenmeli ve **Liabilities:AP** satırı “‑6200.00” yerine “6200.00” (artı) olmalı. |
| 64‑66 | **Satın alma** “Northwind Supplies” (PI‑2240) kaydında **Liabilities:AP** negatif (“‑5100.00”). | Politikada “liability” hesabı negatif gösterilse de, “increase” işlemi pozitif olmalı; negatif işaret bir azalışı gösterir ve muhasebe mantığıyla çelişir. | `Liabilities:AP 5100.00 USD` olarak düzeltilmeli. |
| 68‑71 | **Ödeme** “Summit Wholesale” (partial) doğru, fakat **Harbor Freight Ltd** için **11‑26** tarihli **4800** tutarlı bir tahsilat **eksik**. | Banka ekstresinde 11‑26’da 4800 kredi var, ama defterde karşılığı yok; gerçek mutabakatta bu eksik olmaz. | 2025‑11‑26 tarihli yeni bir işlem eklenmeli (aşağıda detayları). |
| 72‑74 | **Prepayment** “Cedar Property Group” (check 1038) doğru şekilde **Outstanding check** olarak bırakılmış. | Bu bir “tuzağa” (trap) hizmet ediyor, gerçek dünyada böyle bir “outstanding check” kaydı bulunur; ancak açıklama satırında “December rent prepaid, check 1038” ifadesi **payee** alanında “Cedar Property Group” yerine “Cedar Property Group” olarak verilmiş; trap’da “payee” kontrolü yok, sadece narration. Bu tutarlı. | **Sorun yok**. |
| 30‑33, 64‑66 gibi **negatif/pozitif işaret** tutarlılığı: **Assets** hesabı artışı pozitif, azalışı negatif; **Liabilities** ise ters (negatif artış). Bu karışık konvansiyon gerçek dünyada kafa karıştırıcıdır. | **Düzeltme:** Tüm varlık ve gider hesapları pozitif artış, negatif azalış; tüm borç ve özkaynak hesapları da aynı yön (pozitif artış) kullanılmalı. |
| 30‑33, 64‑66 | **Narration/payee dili**: “Northwind Supplies” gibi payee sadece tedarikçi adı, açıklama “Payment of purchase invoice PI‑2211”. Gerçek bankalar genellikle referans numarası ve işlem türü (ACH, Check) içerir; burada eksik. | **Düzeltme:** Payee alanına “Cascade Bank” gibi banka adı eklenebilir, açıklamaya referans numarası konulabilir. |

### 7. `bank_statement.csv`  

| Satır | Bulgu | Neden gerçekçi değil? | Düzeltme önerisi |
|------|-------|----------------------|------------------|
| 2 | Açılış satırı “Opening balance carried forward” içinde **debit/credit** boş, sadece **balance**. | Çoğu banka CSV’si açılış bakiyesini ayrı bir satırda “Balance” sütununda verir, ancak debit/credit alanları genellikle doldurulur (0). | Debit ve credit sütunlarını “0.00” olarak doldur. |
| 5 | “CHECK 1037 CEDAR PROPERTY GROUP” açıklaması, ledger’de **check numarası** yok (sadece “Cedar Property Group”). | Gerçek mutabakatta aynı referans numarası (check 1037) ledger’de de bulunmalı. | Ledger’e “CHECK 1037” içeren bir satır eklenmeli (ancak trap’tan dolayı bu check zaten var; burada tutarsızlık). |
| 8 | “ACH IN HARBOR FREIGHT LTD, SI‑1044” – aynı satırda **credit** 4800, ancak ledger’de bu tutar **satış** (gelir) olarak kaydedilmiş, tahsilat eksik. | Banka ekstresi tahsilatı gösteriyor; defterde eksik. | Yukarıdaki “missing receipt” ile aynı düzeltme. |
| 9 | “MONTHLY ACCOUNT SERVICE CHARGE” tutarı 85, ancak **debit** sütunu “85.00” ve **credit** boş; bu format gerçek bankalarda “Fee” olarak **debit** gösterilir, doğru. | **Sorun yok**. |

---

## C. Görev senaryosu  

- **Görev metni** (“Bring the ledger into agreement with the statement…”) gerçek bir muhasebecinin ay sonu mutabakat görevine çok benziyor.  
- **Politika** içinde “Outstanding checks” ve “Deposits in transit” tanımları mevcut; bu, trap’taki “check 1038” için doğru bir yönlendirme.  
- **Eksik kayıtlar** (4800 tahsilatı ve 85 banka ücreti) politikada açıkça “must be posted” olarak tanımlanmış; bu, puanlama kodunun beklediği davranışla uyumlu.  
- **Belirsizlik**: “must_be_payee” kısmı, payee alanının **tam olarak** “Harbor Freight Ltd” ve “Cascade Bank” olmasını şart koşuyor; bu, ajan için ekstra bir zorunluluk (case‑sensitive, noktalama yok) ve gerçek dünyada genelde “Harbor Freight Ltd” gibi tam eşleşme zorunlu değildir. Bu, görevde **haksız bir kısıtlama** oluşturuyor.  
- **Gerçek mutabakatlarda** sık görülen ama burada **olmayan** fark türleri:  
  - **NSF/karşılıksız çek** (bankada çek geri dönmüş, ledger’de düzeltme gerekir).  
  - **Tarih kayması** (bankada 2025‑11‑02 tarihli işlem, ledger’de 2025‑11‑03).  
  - **Çift kayıt** (aynı fatura iki kez kaydedilmiş).  
  - **Yanlış tutar** (ör. 3500 yerine 350.00).  
  - **Kesinti yapılmış tahsilat** (bankada net tutar, fatura brüt).  

Bu tipler test ortamında bulunmadığı için ajan “sadece eksik kayıtları ekle” stratejisiyle kolayca ilerleyebilir; bu da **zorluk seviyesini düşürüyor**.

---

## D. Kanıt ve belirlenebilirlik  

- **Bank statement** satır 8 (SI‑1044, 4800 kredi) doğrudan **müşteri** “Harbor Freight Ltd” ile eşleşiyor; aynı referans numarası ledger’de satış satırı (11‑07) bulunuyor, bu da tahsilatın hangi faturaya ait olduğunu kesin olarak gösteriyor.  
- **Bank statement** satır 9 (service charge 85) sadece “MONTHLY ACCOUNT SERVICE CHARGE” ifadesi var; politika “Bank service charges” bölümünden bu tutarın **Expenses:BankFees** hesabına kaydedilmesi gerektiği açık, dolayısıyla tek başına yeterli kanıt sağlanıyor.  
- **Outstanding check 1038** bank statement’ta görünmüyor; politikada “timing difference” olarak bırakılması gerektiği belirtilmiş, bu yüzden ajanın bu satırı değiştirmemesi kanıtlanabilir.  
- **Diğer hesaplar** (ör. Inventory, AP) zaten ledger’de tutarlı; ekstreyle çelişen tek şey eksik iki işlem. Bu yüzden ajanın doğru sonuca ulaşması **tamamen** bank statement ve mevcut ledger üzerinden mümkün.

---

## E. Puanlar  

| Kriter | Puan (1‑5) | Tek satır gerekçe |
|--------|-----------|-------------------|
| Gerçekçilik | 3 | Tutarların yuvarlak olması, çok az işlem ve tutarsız payee/description formatı sentetik izler taşıyor. |
| Zorluk (junior muhasebeci için) | 2 | Eksik iki işlem ve basit sign‑uyumsuzluklar; politikada net yönergeler ve trap sayesinde çözüm düşük çaba gerektiriyor. |
| Belirsizlik yokluğu | 2 | “must_be_payee” kısıtlaması gereksiz derecede katı ve gerçek dünyada nadir; bu durum ajanın hata yapma riskini artırıyor. |
| Tuzağın adilliği | 4 | Outstanding check 1038’in değiştirilmemesi gerektiği açıkça belirtilmiş; ajanın bu tuzağa düşmesi düşük. |

---

## F. En önemli 5 düzeltme  

1. **Missing receipt – 2025‑11‑26**  
   - Dosya: `ledger.beancount`, **yeni satır** eklenmeli (örnek):  
     ```
     2025-11-26 * "Harbor Freight Ltd" "ACH receipt for SI-1044"
       Assets:Bank:Checking                     4800.00 USD
       Assets:AR                               -4800.00 USD
     ```
2. **Missing bank fee – 2025‑11‑30**  
   - Dosya: `ledger.beancount`, **yeni satır** eklenmeli:  
     ```
     2025-11-30 * "Cascade Bank" "Monthly account service charge"
       Expenses:BankFees                        85.00 USD
       Assets:Bank:Checking                   -85.00 USD
     ```
3. **Purchase of inventory – 2025‑11‑04**  
   - Dosya: `ledger.beancount`, satır 30‑33’a şu eklemeler yapılmalı:  
     ```
       Assets:Inventory                       6200.00 USD
       Liabilities:AP                         6200.00 USD   ; (artış, negatif işaret kaldırılmalı)
     ```
4. **Sign error on AP for PI‑2240**  
   - Dosya: `ledger.beancount`, satır 64‑66’da `Liabilities:AP -5100.00 USD` → `Liabilities:AP 5100.00 USD`.  
5. **Bank statement opening‑balance row format**  
   - Dosya: `bank_statement.csv`, satır 2’de `debit` ve `credit` sütunlarını `0.00` olarak doldur:  
     ```
     2025-11-01,Opening balance carried forward,,0.00,0.00,42150.00
     ```

Bu beş düzeltme, hem beklenen hesap bakiyelerini (expected_balances) hem de politikadaki “must_be_payee” ve “trap” kurallarını tam olarak karşılayacak, gerçekçi bir mutabakat sürecine en yakın hâli verecektir.
