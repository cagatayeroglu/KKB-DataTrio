import type {
  Dataset,
  Proof,
  ProofDocument,
  ProofSource,
  ProofStep,
} from "./contracts";
import { seriesLabel, unitLabel } from "./table";

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
  web_url: "Sorudaki adresteki belgeden hücre okuma",
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

export function stepInputs(
  proof: Proof,
  step: ProofStep,
  dataset: Dataset | null = null,
) {
  return step.inputs.map((item) => {
    if (item.kind === "result") {
      return `${proof.steps[item.index]?.workspace_name ?? "önceki sonuç"} tablosu`;
    }
    if (item.kind === "document") {
      const document = proof.documents[item.index];
      return document ? documentName(document) : "kayıtlı belge";
    }
    const source = proof.sources[item.index];
    return source ? sourceName(source, dataset) : "kayıtlı seri";
  });
}

const formats: Record<ProofDocument["document_format"], string> = {
  csv: "CSV",
  xlsx: "Excel",
  pdf: "PDF",
  html: "HTML",
};

/** The document by format and https host only; the address path is never recorded. */
export function documentName(document: ProofDocument) {
  const format = formats[document.document_format];
  if (document.source_type === "upload") return `Yüklenen ${format} belgesi`;
  return document.host
    ? `${format} belgesi (${document.host})`
    : `${format} belgesi`;
}

export function documentOrigin(document: ProofDocument) {
  if (document.source_type === "upload")
    return document.retrieved_at
      ? `Bu soruya eklenen yükleme, ${day(document.retrieved_at)} tarihinde kabul edildi`
      : "Bu soruya eklenen yükleme";
  const when = document.retrieved_at
    ? `${day(document.retrieved_at)} tarihinde okundu`
    : "okunma zamanı kayıtlı değil";
  return `Sorudaki adresten güvenli indirme, ${when}`;
}

/** Position of the selected cell or column; sheet names and cell text stay out. */
export function documentLocation(document: ProofDocument) {
  return [
    document.page === null ? null : `sayfa ${document.page}`,
    document.sheet_selected ? "seçilen çalışma sayfası" : null,
    document.table === null ? null : `tablo ${document.table}`,
    document.row === null ? null : `satır ${document.row}`,
    document.column === null ? null : `sütun ${document.column}`,
    document.values_read === null
      ? null
      : `${document.values_read} değer okundu`,
  ]
    .filter(Boolean)
    .join(" · ");
}

export function stepCheck(step: ProofStep) {
  return step.producer === "web_url"
    ? "Seçilen hücre, belgenin içerik kimliği ve okunan değerle yeniden eşleşti"
    : "Yürütme kaydı girdileri ve çıktısıyla yeniden eşleşti";
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

const frequencies: Record<string, string> = {
  daily: "günlük",
  business_day: "iş günü",
  weekly: "haftalık",
  twice_monthly: "ayda iki",
  monthly: "aylık",
  quarterly: "çeyreklik",
  semiannual: "altı aylık",
  annual: "yıllık",
  irregular: "düzensiz",
  unknown: "sıklık belirsiz",
};
const measures: Record<string, string> = {
  stock: "stok",
  flow: "akım",
  rate: "oran",
  index: "endeks",
  unknown: "ölçü türü belirsiz",
};
const cumulative: Record<string, string> = {
  none: "kümülatif değil",
  since_inception: "başlangıçtan kümülatif",
  yearly_reset: "yıl başında sıfırlanan kümülatif",
  unknown: "kümülatiflik belirsiz",
};
const archive: Record<string, string> = {
  active: "katalogda aktif",
  archived: "katalogda arşivlenmiş",
  unknown: "katalog arşiv durumu bilinmiyor",
};

/** Catalog display title when the inventory knows the identity; recorded title otherwise. */
export function sourceName(source: ProofSource, dataset: Dataset | null) {
  const named = seriesLabel(source.series_id, dataset);
  return named !== source.series_id
    ? named
    : (source.title ?? source.series_id);
}

export function sourceSemantics(source: ProofSource) {
  const pick = (map: Record<string, string>, value: string | null) =>
    value === null ? null : (map[value] ?? value);
  return [
    source.scale === null ? null : unitLabel(source.unit, source.scale),
    pick(frequencies, source.frequency),
    pick(measures, source.measure),
    pick(cumulative, source.cumulative),
    pick(archive, source.catalog_status),
  ]
    .filter(Boolean)
    .join(" · ");
}
