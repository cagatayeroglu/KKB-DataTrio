# M3-02 — BDDK source inventory

What the BDDK bulletins actually publish, established by reading the live public site on 2026-09-09. This exists so that [M12](ROADMAP.md#m12) normalization rules are written against the real source rather than an assumed shape.

Retrieved payloads are **not** committed. They were written to the ignored `data/raw/bddk/` path for inspection; redistribution terms are unresolved under [Q-DATA-03](OPEN_QUESTIONS.md#q-data-03--caching-retention-and-redistribution). Nothing here is an implemented adapter — [M3-06](ROADMAP.md#m3) still owns retrieval, behind safe fetch.

## The three sources are not one source

The brief names three BDDK datasets. They differ in transport, frequency **and scale**, so a single adapter cannot treat them alike.

| Source | Transport | Frequency | Unit | Coverage |
| --- | --- | --- | --- | --- |
| Aylık Bülten | JSON endpoint | Monthly | Milyon TL | 2002 – 2026/7 |
| Haftalık Bülten | Form POST, server-rendered HTML | Weekly, Friday-dated | Milyon TL | 2014 – 2026, 661 periods |
| FinTürk | JSON endpoint | **Quarterly** (3/6/9/12 only) | **Bin TL** (and `%`, `Adet`) | 2007/12 – 2026/6, 75 periods |

Two consequences worth stating plainly. FinTürk is quarterly, not monthly or weekly — a monthly province-level series does not exist to be fetched. And FinTürk is in **thousand** TL while the other two are in **million** TL, so joining them without reading each one's declared unit is a 1000× error that looks entirely plausible on a chart. Unit is a required field for exactly this reason ([M12-10](ROADMAP.md#m12)).

## Aylık Bülten

`POST https://www.bddk.org.tr/BultenAylik/tr/Home/BasitRaporGetir`, form-encoded:

| Parameter | Values |
| --- | --- |
| `tabloNo` | 1–17, see the table list below |
| `yil` | 2002 – 2026 |
| `ay` | 1 – 12 |
| `paraBirimi` | `TL` or `USD` |
| `taraf` | `10001` Sektör, `10002` Mevduat, `10003` Katılım, `10004` Kalkınma ve Yatırım, `10005` Yerli Özel, `10006` Kamu, `10007` Yabancı, `10008` Mevduat-Yerli Özel, `10009` Mevduat-Kamu, `10010` Mevduat-Yabancı. Repeatable for several bank groups in one call. |

Response:

```json
{"success": true,
 "Json": {"caption": "Tüketici Kredileri (milyon TL), Dönem:2026/6",
          "colNames": ["", "", "", "BasitFont", "TP", "YP", "Toplam"],
          "colModels": [...],
          "data": {"page": "1", "total": "1", "records": "1",
                   "rows": [{"id": "2",
                             "cell": ["Sektör", 2, "Tüketici Kredileri - Konut", "", 801376, 62, 801438]}]}}}
```

Each `cell` is `[bank group, row number, item label, font hint, TP, YP, Toplam]`. Values are numbers, not formatted strings, so no locale parsing is needed on this path. A failure returns `success: false` with `error`.

**`caption` is the only place the unit and period appear.** Parse it; do not hard-code `milyon TL`, and treat a caption that does not match the expected shape as an unknown-unit failure rather than defaulting.

Tables: 1 Bilanço, 2 Kar Zarar, 3 Krediler, 4 Tüketici Kredileri, 5 Sektörel Kredi Dağılımı, 6 KOBİ Kredileri, 7 Sendikasyon Seküritizasyon Kredileri, 8 Menkul Kıymetler, 9 Mevduat Türler İtibarıyla, 10 Mevduat Vade İtibarıyla, 11 Likidite Durumu, 12 Sermaye Yeterliliği, 13 Yabancı Para Pozisyonu, 14 Bilanço Dışı İşlemler, 15 Rasyolar, 16 Diğer Bilgiler, 17 Yurt Dışı Şube Rasyoları.

## Cumulative behaviour is per table, not per source

The brief warns that some BDDK series are cumulative from first publication and some reset yearly. Both statements are true of the monthly bulletin, and which one applies depends on the table. All 66 periods from 2021/1 to 2026/6 were retrieved for the two tables below.

**Table 4, Tüketici Kredileri — stock, end of period, no reset.** `Tüketici Kredileri - Konut` runs 276,785 (2021/1) to 801,438 (2026/6) and **decreases in 8 of 65 month-over-month steps**, the largest being −2,875 between 2023/9 and 2023/10. A cumulative series cannot decrease, so this is an outstanding balance. Differencing it would produce net change in the stock, which is not disbursement.

**Table 2, Kar Zarar — year-to-date cumulative, resets every January.** `DÖNEM NET KARI (ZARARI)` at each year boundary:

| December | January | Delta |
| --- | --- | --- |
| 2021/12 = 92,942 | 2022/1 = 20,089 | −72,853 |
| 2022/12 = 431,614 | 2023/1 = 39,320 | −392,294 |
| 2023/12 = 620,495 | 2024/1 = 31,954 | −588,541 |
| 2024/12 = 660,278 | 2025/1 = 47,347 | −612,931 |
| 2025/12 = 940,183 | 2026/1 = 87,249 | −852,934 |

Five resets in five year boundaries, with no exception. `Kredilerden Alınan Faizler` behaves the same way. For these series the monthly flow is the first difference **within a calendar year**, and January's published value is already the month itself — differencing across the boundary yields a large negative number that is an artefact, not an economic event.

Detection must therefore be per series, not per source or per file ([M12-05](ROADMAP.md#m12)). A usable heuristic from this evidence: a series that ever decreases outside a January boundary is not cumulative; a series that drops sharply at every January and rises monotonically within each year is yearly-reset cumulative. Neither test is conclusive on a short window, so low confidence must be reported rather than resolved by guessing.

## The reference scenario needs a clarification, not a lookup

The organizer's first question asks for "Türkiye'de kullanılan toplam konut kredileri". BDDK's monthly bulletin publishes `Tüketici Kredileri - Konut` as an outstanding **stock**. Disbursement — the flow sense of "kullanılan" — is not that row and is not elsewhere in table 4.

So the honest behaviour is the one [DEC-119](DECISIONS.md#dec-119--verifier-gates-the-answer) already requires: the system must either ask which sense is meant or present both with their definitions labelled. Silently answering with the stock, or silently differencing the stock and calling it disbursement, both produce a confident chart that answers a different question than the one asked.

## Haftalık Bülten

Form POST to `https://www.bddk.org.tr/BultenHaftalik/tr/Home/DonemDegistir` with `yil`, `donemId` and `para`. Unlike the monthly bulletin this renders **server-side HTML**; there is no row JSON, so this path needs table parsing. A separate `/BultenHaftalik/tr/Home/KiyaslamaJsonGetir` serves the comparison chart only.

`donemId` is a sequential integer, not a date: `661` is the week labelled `Ağustos/28 (35. Hafta)`, and the rendered caption reads `Sektör / Krediler (28 Ağustos 2026 Cuma) (Milyon TL)`. Observations are dated to a **Friday**, and week numbering is within the year, so week 1 and week 53 boundaries and weeks spanning two months both occur. This is the input [M12-08](ROADMAP.md#m12) has to align, and the `donemId`-to-date mapping must be read from the option list rather than computed.

## FinTürk

`POST /BultenFinturk/tr/Home/VeriGetir` — note the path spells `Finturk` with a lower-case `t` while the page URL uses `FinTurk`. Also exposes `/BultenFinturk/tr/Home/ExceleAktar` and `/BultenFinturk/tr/Home/MetaveriPdfIndir`; the metadata PDF is worth reading before trusting any FinTürk column.

Selectors are period (`2026-6` style, quarter-end only), bank group (7 values), province (83 options: 81 provinces plus `HEPSİ` and one aggregate), and table:

| Table | Unit |
| --- | --- |
| Krediler | Bin TL |
| Mevduat | Bin TL |
| Bireysel Bankacılık | Bin TL |
| Seçilmiş Sektörel Krediler | Bin TL |
| Oranlar | % |
| Şubeler ve Nüfusa Göre Dağılım | Adet and TL |
| Altın Kredileri ve Altın Mevduatı | Bin TL |

The unit appears **only in the table's display label**, and one table mixes two units across its columns. A column cannot be admitted from FinTürk without resolving its unit explicitly.

## Retrieval will fail on certificate verification

`www.bddk.org.tr` serves only its leaf certificate and omits the intermediate CA. Browsers and `curl` succeed because they complete the chain themselves; Python's OpenSSL does not:

```
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate
```

`httpx` ([DEC-124](DECISIONS.md#dec-124--dependency-manifest-and-excluded-technologies)) verifies against certifi and **will fail exactly this way**. The M3-06 adapter must supply the missing intermediate in an explicit trust bundle. Do not resolve this by disabling verification — the fix is to add the specific issuer certificate, not to stop checking. This also has to be reproduced in the demo environment, so it belongs in the deployment checklist rather than being discovered on demo day.

## What this does not establish

No adapter, no schedule, no retention decision. Access terms, permitted request rates and redistribution remain [Q-DATA-01](OPEN_QUESTIONS.md#q-data-01--bddkevds-and-provided-source-access) and Q-DATA-03; this inspection read published pages at roughly three requests per second and stored nothing shared. Revision behaviour is untested — whether BDDK restates a prior period is a real question for [M12-12](ROADMAP.md#m12) and is not answered here. USD-denominated variants, the remaining 15 monthly tables and all bank-group breakdowns were not inspected beyond their selector values. EVDS is [M3-03](ROADMAP.md#m3) and is not covered by this document.
