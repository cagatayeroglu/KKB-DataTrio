import type { Proof, ProofSource, ProofStep } from "./contracts";

/** Fixed wording for server-recorded proof facts; no inference beyond the payload. */
const operations: Record<string, string> = {
  lakehouse_query: "Hazır veri tablosundan okuma",
  change_detection_compare: "İki dönem karşılaştırması",
  change_detection_co_movement: "Birlikte hareket hesabı",
  table_co_movement: "Tablo sütunlarının birlikte hareketi",
  table_transform_add_series: "Önceki tabloya seri ekleme",
  table_transform_deflate: "Fiyat endeksiyle reel değere çevirme",
};
const producers: Record<string, string> = {
  lakehouse: "Hazır veri sorgusu",
  change_detection: "Değişim hesabı",
  table_transform: "Tablo dönüşümü",
  anomaly: "Olağandışı değer taraması",
  causality: "İlişki ve gecikme analizi",
};
const gaps: Record<Proof["gaps"][number], string> = {
  execution_not_verified:
    "Sonucun yürütme kaydı yeniden doğrulanamadı; zincir gösterilmiyor.",
  input_not_recognized: "Bazı girdi kayıtları tanınmadı ve zincire eklenmedi.",
  input_result_not_verified:
    "Önceki bir tablonun yürütme kaydı doğrulanamadığı için izlenmedi.",
  dataset_record_missing: "Bir veri seti kaydı depoda bulunamadı.",
  source_lineage_missing:
    "Bir serinin ham kaynak yanıtlarına uzanan soy kaydı yok.",
  raw_response_limit:
    "Ham kaynak yanıtları okuma sınırında kesildi; sayı eksik olabilir.",
  step_limit: "Hesaplama adımı sınırına ulaşıldı; daha eski adımlar izlenmedi.",
  source_limit: "Kaynak sınırına ulaşıldı; bazı seriler gösterilmedi.",
  proof_unreadable: "Kanıt kaydı okunamadı; zincir gösterilmiyor.",
};

export function proofHeadline(proof: Proof) {
  return {
    available: "Kaynaktan sonuca kayıtlı zincir eksiksiz",
    partial: "Kaynaktan sonuca kayıtlı zincir kısmi",
    unavailable: "Bu sonuç için kayıtlı kanıt zinciri gösterilemiyor",
  }[proof.availability];
}

export function gapText(gap: Proof["gaps"][number]) {
  return gaps[gap];
}

export function stepTitle(step: ProofStep) {
  return (
    (step.operation && operations[step.operation]) ??
    producers[step.producer] ??
    step.producer
  );
}

/** Deepest recorded step first, so the list reads from source towards this result. */
export function orderedSteps(proof: Proof) {
  const depth = new Map<number, number>([[0, 0]]);
  proof.steps.forEach((step, index) => {
    for (const item of step.inputs) {
      if (item.kind === "result" && !depth.has(item.index)) {
        depth.set(item.index, (depth.get(index) ?? 0) + 1);
      }
    }
  });
  return proof.steps
    .map((step, index) => ({ step, index, depth: depth.get(index) ?? 0 }))
    .sort((a, b) => b.depth - a.depth || b.index - a.index);
}

export function stepInputs(proof: Proof, step: ProofStep) {
  return step.inputs.map((item) =>
    item.kind === "series"
      ? (proof.sources[item.index]?.title ??
        proof.sources[item.index]?.series_id)
      : `${proof.steps[item.index]?.workspace_name ?? "önceki sonuç"} tablosu`,
  );
}

function day(value: string) {
  return value.slice(0, 10);
}

export function sourceOrigin(source: ProofSource) {
  if (source.raw_responses === 0) {
    return "Ham kaynak yanıtlarına uzanan kayıt yok";
  }
  const hosts = source.hosts.length
    ? source.hosts.join(", ")
    : "kayıtlı sunucu";
  const when =
    source.first_retrieved && source.last_retrieved
      ? day(source.first_retrieved) === day(source.last_retrieved)
        ? `, ${day(source.first_retrieved)} tarihinde alındı`
        : `, ${day(source.first_retrieved)} – ${day(source.last_retrieved)} arasında alındı`
      : "";
  return `${source.raw_responses} ham yanıt (${hosts})${when}`;
}

export function sourceCoverage(source: ProofSource) {
  if (source.observations === null) {
    return "Gözlem sayısı yürütme kaydında tutulmadı";
  }
  const span =
    source.first_period && source.last_period
      ? `${source.first_period} – ${source.last_period}, `
      : "";
  return `${span}${source.observations} gözlem okundu, ${source.missing_values ?? 0} boş`;
}

export function sourceSemantics(source: ProofSource) {
  return [
    source.unit,
    source.scale,
    source.frequency,
    source.measure,
    source.cumulative && `kümülatif: ${source.cumulative}`,
  ]
    .filter(Boolean)
    .join(" · ");
}
