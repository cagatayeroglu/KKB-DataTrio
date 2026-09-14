/** Exact known diagnostics only; unfamiliar source text is retained, never paraphrased by a model. */
const notices: Record<string, string> = {
  "Numbers are bound to these results' values, not to any stored value":
    "Sayısal ifadeler bu analizin sonuçlarıyla eşleştirildi; depodaki rastgele bir değerle değil.",
  "No external cross-check was performed":
    "Başka bir dış kaynakla bağımsız çapraz kontrol yapılmadı.",
  "Explicit identifiers, calendar and financial qualifiers use a bounded deterministic vocabulary; arbitrary prose and causal meaning are not proved":
    "Kimlik, dönem ve finansal nitelemeler tanımlı kurallarla kontrol edilir. Bu kontrol her serbest metin ifadesini veya nedensellik iddiasını kanıtlamaz.",
  "The store recheck is a second read keyed on series and period, not an independent derivation: it catches a wrong join, period or altered figure, not a value that was stored wrongly":
    "Veri, seri ve dönem üzerinden depodan yeniden okunarak kontrol edildi. Bu işlem yanlış eşleşme veya değişmiş sayı yakalayabilir; baştan yanlış kaydedilmiş bir değeri bağımsız olarak doğrulamaz.",
};
export function noticeText(value: string) {
  return notices[value] ?? value;
}
