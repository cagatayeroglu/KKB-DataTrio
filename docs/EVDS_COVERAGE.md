# Reviewed EVDS expansion — credit rates and CPI divisions

Arda's 2026-09-14 local-pool expansion (M3-07/08, M13-08; PR #160).
This is a bounded reviewed set, not arbitrary catalog ingestion or all EVDS.
The original four EVDS declarations, prepared v2 and historical source notes
remain unchanged. Runtime still cannot fetch on a catalog miss.

## Source evidence and interpretation

Two public GET `https://evds3.tcmb.gov.tr/igmevdsms-dis/serieList/fe/type=json&code=<group>`
responses were retrieved on 2026-09-14 without credentials. Their UTF-8 content
hashes exactly match the earlier M3-07 reviewed datagroup evidence:

| Group | Bytes | SHA-256 |
| --- | ---: | --- |
| `bie_kt100h` | 4112 | `b05143c4693d5b9e6057b5caaeb07123baefcbf594d1f57d9847481bbcde14c9` |
| `bie_tukfiy2025` | 145832 | `e9e556bed380546ce930ae192171f71f5e37e3a6e0367b370e66c2bb60d62f67` |

`bie_kt100h` is the previously reviewed deposit/development/investment-bank
new-loan interest-rate group. All ten records declare HAFTALIK(CUMA), default
avg, AVG/FIRST/LAST/MIN/MAX allowed and SUM forbidden. Nine additional series
are selected below; the original housing rate is retained. They are RATE,
percent/one, non-cumulative, Friday-anchored; "Akım" describes the new-lending
basis of the rate and does not make the percentage a summable monetary flow.
Loan currency remains in the title: a USD-denominated loan rate is not USD/TRY.
KMH inclusion/exclusion and corporate-card scope are never silently collapsed.

The thirteen explicitly listed two-digit CPI divisions all declare AYLIK and
the same aggregation flags. The source group establishes 2025=100; these are
INDEX levels, not inflation percentages or weights. A housing/utilities CPI
division is not KFE or a general-purpose replacement for headline CPI.
Active/archived status and coverage are not inferred from names. Local
materialization separately establishes actual periods, nulls and lineage.

## Reviewed additional identities

| Code | Source title | Native cadence |
| --- | --- | --- |
| `TP.KTF10` | İhtiyaç Kredisi (TL, Akım, %) | HAFTALIK(CUMA) |
| `TP.KTF101` | İhtiyaç Kredisi (KMH Dahil) (TL, Akım, %) | HAFTALIK(CUMA) |
| `TP.KTF11` | Taşıt Kredisi (TL, Akım, %) | HAFTALIK(CUMA) |
| `TP.KTF17` | Ticari Krediler (TL, Akım, %) | HAFTALIK(CUMA) |
| `TP.KTF17.EUR` | Ticari Krediler (Euro, Akım, %) | HAFTALIK(CUMA) |
| `TP.KTF17.USD` | Ticari Krediler (ABD doları, Akım,%) | HAFTALIK(CUMA) |
| `TP.KTF18` | Ticari Krediler (Tüzel Kişi KMH ve Kurumsal Kredi Kartları Hariç) (TL, Akım, %) | HAFTALIK(CUMA) |
| `TP.KTFTUK` | Tüketici Kredisi (İhtiyaç+Taşıt+Konut) (TL, Akım, %) | HAFTALIK(CUMA) |
| `TP.KTFTUK01` | Tüketici Kredisi (KMH Dahil) (İhtiyaç+Taşıt+Konut) (TL, Akım, %) | HAFTALIK(CUMA) |
| `TP.TUKFIY2025.01` | 01. Gıda Ve Alkolsüz İçecekler | AYLIK |
| `TP.TUKFIY2025.02` | 02. Alkollü İçecekler, Tütün Ve Tütün Ürünleri | AYLIK |
| `TP.TUKFIY2025.03` | 03. Giyim Ve Ayakkabı | AYLIK |
| `TP.TUKFIY2025.04` | 04. Konut, Su, Elektrik, Gaz Ve Diğer Yakıtlar | AYLIK |
| `TP.TUKFIY2025.05` | 05. Mobilya, Mefruşat Ve Evde Kullanılan Ekipmanlar İle Rutin Ev Bakım Ve Onarımı | AYLIK |
| `TP.TUKFIY2025.06` | 06. Sağlık | AYLIK |
| `TP.TUKFIY2025.07` | 07. Ulaştırma | AYLIK |
| `TP.TUKFIY2025.08` | 08. Bilgi Ve İletişim | AYLIK |
| `TP.TUKFIY2025.09` | 09. Eğlence, Dinlence, Spor Ve Kültür | AYLIK |
| `TP.TUKFIY2025.10` | 10. Eğitim Hizmetleri | AYLIK |
| `TP.TUKFIY2025.11` | 11. Lokantalar Ve Konaklama Hizmetleri | AYLIK |
| `TP.TUKFIY2025.12` | 12. Sigorta Ve Finansal Hizmetler | AYLIK |
| `TP.TUKFIY2025.13` | 13. Kişisel Bakım, Sosyal Koruma Ve Çeşitli Mal Ve Hizmetler | AYLIK |

## Operation and remaining coverage

Use the existing `python -m kkb_agent.ingest.evds_operator prepare --root ...
--start 2021-01-01 --end 2026-06-30 --series <reviewed code>` command, repeating
`--series` for explicitly selected codes. The same closed worker, DNS/peer/TLS,
body/time budgets, original native frequency, parser, immutable manifest,
calendar checks and lineage apply. No retry or unknown-code fallback is added.
Keep raw responses/observations and the DuckDB/Parquet pool out of Git.

`docs/catalog/prepared_v3.json` is the expanded discovery snapshot. Use it with
the expanded pool in `python -m kkb_agent.api --check --prepared-root ...
--catalog docs/catalog/prepared_v3.json --env-file ...`. v2 remains suitable for
its old pool only. Rebuild a catalog vector index explicitly for the new digest;
an old digest/index mismatch must refuse instead of mixing embeddings.

Live measurements are recorded separately in EVALUATION and the handoff so this
reviewed declaration's evidence digest does not change with each preparation.
Full-source coverage, daily/business-day data, BDDK Weekly/FinTürk, revisions,
automated refresh, live embedding quality and unseen-query model reliability
remain separate work. No model or embedding call is part of this preparation.
