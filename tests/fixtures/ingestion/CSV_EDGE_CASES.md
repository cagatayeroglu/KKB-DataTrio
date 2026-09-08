# M1-05 synthetic CSV edge fixtures

These small, invented inputs have no real-source data or financial declarations.
Unit, frequency, time role, stock/flow, cumulative and reset semantics remain
unknown. Dates and numeric-looking cells stay strings; empty fields remain empty
and represent missing values under these fixture declarations, never zero.

The [targeted tests](../../unit/test_csv_edge_fixtures.py) pin every header and
cell, row order, delimiter and BOM flag using the standard-library CSV reader.
This defines test expectations, not an application loader or a parser dependency
decision. All files use UTF-8 and LF newlines, a header row, double-quote quoting
with doubled-quote escapes, and no trimming or numeric conversion.

| File | Explicit parsing declaration and expected result |
| --- | --- |
| [semicolon.csv](semicolon.csv) | Semicolon delimiter, no BOM; 2 rows × 3 columns (`as_of`, `measure`, `label`). Second `measure` is empty. |
| [quoted_fields.csv](quoted_fields.csv) | Comma delimiter, no BOM; 3 rows × 3 columns. Labels are `A, quoted`, `B "quoted"`, and `C\ncontinued` (a literal LF inside one quoted cell). Commas, escaped quotes and embedded LF do not add columns/rows. |
| [utf8_bom.csv](utf8_bom.csv) | Comma delimiter, leading bytes `EF BB BF`; decode explicitly as UTF-8 with BOM handling (`utf-8-sig`). 2 rows × 3 columns with labels `Örnek` and `çığ`; first header is `as_of` without a BOM character. Second `measure` is empty. |
| [numeric_separators.csv](numeric_separators.csv) | Semicolon delimiter, no BOM; 2 rows × 4 columns. Preserve `measure_comma` values `1,234`, `2,345` and `measure_dot` values `1.234`, `2.345` exactly. No numeric locale is declared or selected. |

For `measure_comma`, decimal-comma/no-grouping interpretation gives `1.234` and
`2.345`; dot-decimal/comma-grouping gives `1234` and `2345`. For `measure_dot`,
dot-decimal/no-grouping gives `1.234` and `2.345`; comma-decimal/dot-grouping gives
`1234` and `2345`. Both interpretations cover both nonmissing cells in each
column. A future profile must retain `candidate_state.numeric: ambiguous` and
`AMBIGUOUS_NUMBER` under [INGESTION_PROFILE](../../../docs/INGESTION_PROFILE.md),
without selecting either interpretation or replacing the original strings.
The tests validate fixture contents only; they do not claim profiling exists.
