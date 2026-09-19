"use client";
import { useEffect, useMemo, useState } from "react";
import {
  Archive,
  ArchiveRestore,
  Download,
  FlaskConical,
  History,
  LoaderCircle,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Upload,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  admitDocumentFromUrl,
  annotateSeries,
  datasetRequestFromExport,
  describeError,
  listKnowledge,
  openDataset,
  readIndex,
  rebuildIndex,
  seriesUses,
  trySearch,
  parseDatedRows,
  parseMonthlyRows,
  saveDataset,
  seriesNotes,
  seriesValues,
  setDatasetArchived,
} from "@/lib/client";
import { knowledgeExportSchema } from "@/lib/contracts";
import type {
  Dataset,
  KnowledgeExport,
  SearchTrial,
  DatasetDetail,
  DatasetRequest,
  KnowledgeList,
  KnowledgeSeries,
  SeriesUses,
  VectorIndex,
} from "@/lib/contracts";
import { unitLabel } from "@/lib/table";

type Filter =
  "all" | "prepared" | "fetchable" | "catalog" | "user" | "archived";
/** Which retrieval stages ran for a trial, in the words the page uses elsewhere. */
const retrievalWords: Record<string, string> = {
  lexical_only: "yalnızca kelime eşleşmesi",
  hybrid: "kelime + anlam araması",
  lexical_degraded: "anlam araması devre dışı",
};
/** Which of the two stages offered a candidate, in the words the trial uses. */
const stageWords: Record<string, string> = {
  lexical: "KELİME",
  dense: "ANLAM",
  both: "İKİSİ",
};
/** Whether the first candidate is the default the question leaves (DEC-165). */
const topCandidateWords: Record<string, string> = {
  unambiguous: "ilk aday net varsayılan",
  ambiguous: "adaylar belirsiz, netleştirme gerekir",
  none: "aday yok",
};
const denseFailureWords: Record<string, string> = {
  snapshot_mismatch:
    "Vektörler bu kataloğu kapsamıyor: bilgi tabanı değişmiş, yeniden vektörlemek gerekiyor.",
  embedding_failed: "Soru vektöre çevrilemedi.",
  index_failed: "Vektör dizini okunamadı.",
};

const filters: [Filter, string][] = [
  ["all", "Tümü"],
  ["prepared", "Hazır"],
  ["fetchable", "Kaynaktan çekilir"],
  ["catalog", "Yalnız katalog"],
  ["user", "Benim eklediklerim"],
  ["archived", "Arşiv"],
];
const measures: Record<string, string> = {
  stock: "stok",
  flow: "akış",
  rate: "oran",
  index: "endeks",
  unknown: "belirsiz",
};
const frequencies: Record<string, string> = {
  monthly: "aylık",
  weekly: "haftalık",
  quarterly: "çeyreklik",
  annual: "yıllık",
  daily: "günlük",
  unknown: "belirsiz",
};

const monthNames = [
  "Ocak",
  "Şubat",
  "Mart",
  "Nisan",
  "Mayıs",
  "Haziran",
  "Temmuz",
  "Ağustos",
  "Eylül",
  "Ekim",
  "Kasım",
  "Aralık",
];

function monthOf(value: string) {
  const [year, month] = value.split("-");
  return `${monthNames[Number(month) - 1] ?? month} ${year}`;
}

/** Coverage and staleness, from the record or the pool; nothing is inferred. */
function health(item: KnowledgeSeries, pool?: Dataset | null) {
  const stored = pool?.series.find((one) => one.series_id === item.series_id);
  const start = item.coverage_start ?? stored?.first_period ?? null;
  const end = item.coverage_end ?? stored?.last_period ?? null;
  const observations =
    item.observations ?? stored?.nonnull_observations ?? null;
  if (!end) return null;
  const last = new Date(end);
  const now = new Date();
  const months =
    (now.getFullYear() - last.getFullYear()) * 12 +
    (now.getMonth() - last.getMonth());
  return {
    last: monthOf(end),
    first: start ? monthOf(start) : null,
    months,
    observations,
    // BDDK and EVDS publish two to three months late; that is not staleness.
    stale: months >= 6,
  };
}

function where(item: KnowledgeSeries) {
  if (item.status === "archived") return "Arşivde";
  if (item.origin === "user") return "Kullanıcı beyanı";
  if (item.prepared) return "Hazır havuzda";
  if (item.acquired_at)
    return `Kaynaktan çekildi · ${new Date(item.acquired_at).toLocaleString("tr-TR")}`;
  if (item.fetchable) return "İlk kullanımda kaynaktan çekilir";
  return "Yalnız katalogda";
}
function matches(item: KnowledgeSeries, filter: Filter) {
  if (filter === "archived") return item.status === "archived";
  if (item.status === "archived") return filter === "all";
  if (filter === "prepared") return item.prepared;
  if (filter === "fetchable") return item.fetchable;
  if (filter === "catalog")
    return item.origin === "reviewed" && !item.prepared && !item.fetchable;
  if (filter === "user") return item.origin === "user";
  return true;
}

export type ChatDocument = { sessionId: string; ref: string; label: string };

export function KnowledgePanel({
  owner,
  documents,
  pool,
  onOpenConversation,
  session = null,
}: {
  owner: string;
  documents: ChatDocument[];
  /** The prepared pool's own coverage, which the catalogue record does not carry. */
  pool?: Dataset | null;
  /** Opens one of this browser's conversations in the studio (reverse lineage). */
  onOpenConversation?: (id: string) => void;
  /** The open conversation; a document fetched from an address is admitted into it. */
  session?: { id: string; token: string } | null;
}) {
  const [listing, setListing] = useState<KnowledgeList | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [editing, setEditing] = useState<DatasetDetail | "new" | null>(null);
  const [issue, setIssue] = useState("");
  const [busy, setBusy] = useState(false);
  //: What a question would find here, run on demand and kept nowhere.
  const [trialQuery, setTrialQuery] = useState("");
  const [trial, setTrial] = useState<SearchTrial | null>(null);
  const [trying, setTrying] = useState(false);
  //: Which generation of meaning vectors this deployment searches, and what it covers.
  const [index, setIndex] = useState<VectorIndex | null>(null);
  //: A friendly next-step note (not an error), cleared by the next action.
  const [hint, setHint] = useState("");

  /**
   * The knowledge base as a file that can be imported again: the listing plus
   * each user dataset's full detail (declared meaning and observations).
   * Reviewed catalogue entries travel only as their notes and aliases.
   */
  async function exportKnowledge() {
    if (!listing) return;
    setBusy(true);
    try {
      const datasets = await Promise.all(
        listing.series
          .filter((item) => item.origin === "user" && item.slug)
          .map((item) => openDataset(owner, item.slug!)),
      );
      const file: KnowledgeExport = {
        schema: "kkb-knowledge-export-v1",
        exported_at: new Date().toISOString(),
        listing,
        datasets,
      };
      const blob = new Blob([JSON.stringify(file, null, 2)], {
        type: "application/json",
      });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `bilgi-tabani-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(link.href);
      setIssue("");
    } catch (error) {
      setIssue(describeError(error));
    } finally {
      setBusy(false);
    }
  }

  /**
   * Replay an exported knowledge base into this one. Every dataset lands as a
   * new version through the same declared-meaning gate a manual save passes,
   * and reviewed-series notes/aliases/archivals are replayed as annotations -
   * nothing is written behind the store's back, and nothing reviewed changes.
   */
  async function importKnowledge(file: File) {
    setBusy(true);
    const problems: string[] = [];
    let imported = 0;
    try {
      const parsed = knowledgeExportSchema.safeParse(
        JSON.parse(await file.text()),
      );
      if (!parsed.success) {
        setIssue("Bu dosya bir bilgi tabanı dışa aktarımı değil.");
        return;
      }
      for (const detail of parsed.data.datasets) {
        const item = detail.series;
        try {
          await saveDataset(owner, datasetRequestFromExport(detail));
          if (item.status === "archived" && item.slug)
            await setDatasetArchived(owner, item.slug, true);
          imported++;
        } catch (error) {
          problems.push(
            `${item.slug ?? item.series_id}: ${describeError(error)}`,
          );
        }
      }
      for (const item of parsed.data.listing.series) {
        // A reviewed entry travels as its annotations, never as its record.
        if (item.origin !== "reviewed") continue;
        if (!item.aliases.length && !item.note && item.status !== "archived")
          continue;
        try {
          await annotateSeries(owner, item.series_id, {
            archived: item.status === "archived",
            aliases: item.aliases,
            ...(item.note ? { note: item.note } : {}),
          });
        } catch (error) {
          problems.push(`${item.series_id}: ${describeError(error)}`);
        }
      }
      setIssue(
        problems.length
          ? `${imported} veri seti alındı; alınamayanlar - ${problems.slice(0, 3).join(" · ")}`
          : `${imported} veri seti ve notlar içe aktarıldı; her biri yeni bir sürüm olarak kaydedildi.`,
      );
      await refresh();
    } catch (error) {
      setIssue(describeError(error));
    } finally {
      setBusy(false);
    }
  }
  async function refresh() {
    try {
      setListing(await listKnowledge(owner));
      setIssue("");
    } catch (error) {
      setIssue(describeError(error));
    }
    // Every knowledge-base change makes a different catalogue, so the card that
    // reports vector coverage is read again with the listing.
    void readIndexStatus();
  }
  async function readIndexStatus() {
    try {
      setIndex(await readIndex(owner));
    } catch {
      // An older deployment has no index route; the card then says so.
      setIndex(null);
    }
  }
  useEffect(() => {
    void refresh();
    void readIndexStatus();
  }, [owner]);
  useEffect(() => {
    // A build embeds every entry again, so it is followed rather than waited on.
    if (!index?.rebuilding) return;
    const timer = setTimeout(() => void readIndexStatus(), 3000);
    return () => clearTimeout(timer);
  }, [index]);

  const shown = useMemo(
    () =>
      (listing?.series ?? []).filter(
        (item) =>
          matches(item, filter) &&
          (!query ||
            [item.title, item.series_id, ...item.aliases]
              .join(" ")
              .toLocaleLowerCase("tr")
              .includes(query.toLocaleLowerCase("tr"))),
      ),
    [listing, filter, query],
  );
  const counts = useMemo(() => {
    const all = listing?.series ?? [];
    return {
      reviewed: all.filter((s) => s.origin === "reviewed").length,
      user: all.filter((s) => s.origin === "user").length,
      archived: all.filter((s) => s.status === "archived").length,
    };
  }, [listing]);

  async function act(work: () => Promise<unknown>) {
    setBusy(true);
    try {
      await work();
      await refresh();
      noteVectorGap();
    } catch (error) {
      setIssue(describeError(error));
    } finally {
      setBusy(false);
    }
  }

  /**
   * A gentle reminder after any knowledge-base change: word search covers the
   * change at once, meaning-based search only after the vectors are rebuilt.
   * Read fresh so the message never claims a gap that is not there.
   */
  async function noteVectorGap() {
    try {
      const state = await readIndex(owner);
      setIndex(state);
      if (state.configured && !state.covers_catalog && state.rebuildable)
        setHint(
          'Kaydedildi. Kelime araması değişikliğini hemen görür; yeni açıklama ve eş anlamlıların ANLAMSAL aramaya girmesi için yukarıdaki "Yeniden vektörle" düğmesine basman yeterli.',
        );
    } catch {
      // Without the index route there is nothing to remind about.
    }
  }

  return (
    <div className="knowledge">
      <p className="panel-description">
        Ajanın bildiği her şey. İncelenmiş kayıtlar değiştirilmez; arşivleme, eş
        anlamlı ve not ayrı bir katmanda sürümlü tutulur. Arşivlenen kayıt
        keşiften ve hesaplamadan çıkar, geçmişi kalır ve geri alınabilir.
      </p>
      <div className="page-stats">
        <span>
          <strong>{counts.reviewed}</strong> incelenmiş seri
        </span>
        <span>
          <strong>{counts.user}</strong> eklediğin veri seti
        </span>
        <span>
          {listing
            ? listing.catalog_digest === listing.reviewed_digest
              ? "Katalog incelenmiş haliyle kullanılıyor"
              : `Bilgi tabanıyla birlikte · ${counts.archived} arşivli`
            : "Yükleniyor"}
        </span>
      </div>
      <div className="knowledge-tools">
        <label className="table-search">
          <Search size={14} />
          <input
            aria-label="Listeyi süz: yazdığın metni içeren kayıtlar"
            placeholder="Listeyi süz: ad, kimlik veya eş anlamlı"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <Button
          size="sm"
          variant="outline"
          disabled={!listing || busy}
          onClick={() => void exportKnowledge()}
        >
          <Download size={14} /> Dışa aktar
        </Button>
        <label className="import-label">
          <Upload size={14} /> İçe aktar
          <input
            type="file"
            accept="application/json,.json"
            hidden
            disabled={busy}
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (file) void importKnowledge(file);
            }}
          />
        </label>
        <Button size="sm" onClick={() => setEditing("new")} disabled={busy}>
          <Plus size={14} /> Veri seti ekle
        </Button>
      </div>
      <p className="trial-lead">
        <strong>Ajanın araması.</strong> Aşağısı listeyi süzmez: soruyu ajanın
        kendi keşfine verir — onaylı eş anlamlılarla kelime eşleşmesi ve, dizin
        kuruluysa, anlamsal arama birlikte. Sonuçta hangi aşamaların çalıştığı
        yazar.
      </p>
      <form
        className="knowledge-trial"
        onSubmit={async (event) => {
          event.preventDefault();
          if (!trialQuery.trim()) return;
          setTrying(true);
          try {
            setTrial(await trySearch(owner, trialQuery.trim()));
            setIssue("");
          } catch (error) {
            setIssue(describeError(error));
          } finally {
            setTrying(false);
          }
        }}
      >
        <label className="table-search">
          <FlaskConical size={14} />
          <input
            aria-label="Bir soru yazıp ajanın ne bulacağını dene"
            placeholder="Doğal dille bir soru yaz: ajan bu katalogda ne bulur?"
            value={trialQuery}
            maxLength={512}
            onChange={(e) => setTrialQuery(e.target.value)}
          />
        </label>
        <Button
          size="sm"
          variant="outline"
          disabled={trying || !trialQuery.trim()}
        >
          {trying && <LoaderCircle size={13} className="spin" />} Dene
        </Button>
        {trial && (
          <button type="button" onClick={() => setTrial(null)}>
            Temizle
          </button>
        )}
      </form>
      {trial && (
        <div className="trial-result">
          <p>
            <strong>{trial.status}</strong> · {trial.total_candidates} aday
            {trial.clarification_required
              ? " · netleştirme gerekir"
              : " · tek seri seçilebilir"}
            {" · "}
            {retrievalWords[trial.retrieval_mode]}
            {trial.top_candidate && (
              <>
                {" · "}
                {topCandidateWords[trial.top_candidate]}
              </>
            )}
          </p>
          {trial.retrieval_mode === "lexical_degraded" && (
            <p className="helper">
              {denseFailureWords[trial.dense_failure ?? "index_failed"]} Ajan da
              bu soruyu yalnızca kelimelerle arar.
            </p>
          )}
          {trial.hits.length === 0 && (
            <p className="helper">
              Bu soruyla eşleşen kayıt yok: ajan da bulamaz. Eş anlamlı eklemek
              ya da veri setini eklemek gerekir.
            </p>
          )}
          <ol>
            {trial.hits.map((hit) => (
              <li key={hit.series_id}>
                <span className="trial-rank">{stageWords[hit.stage]}</span>
                <span>
                  {hit.title}
                  <small>
                    {hit.provider} ·{hit.unit ?? "birim bilinmiyor"} ·{" "}
                    {hit.frequency} · {hit.stock_flow}
                    {hit.prepared ? " · hazır havuzda" : " · havuzda yok"}
                    {hit.archived ? " · arşivde" : ""}
                  </small>
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
      {index ? (
        <VectorIndexCard
          index={index}
          onRebuild={async () => {
            try {
              setIndex(await rebuildIndex(owner));
              setIssue("");
            } catch (error) {
              setIssue(describeError(error));
            }
          }}
        />
      ) : (
        <section className="vector-index">
          <div className="vector-head">
            <h3>Anlamsal arama dizini</h3>
            <span className="pill-warn">bilgi alınamadı</span>
          </div>
          <p className="helper">
            Bu sunucu sürümü dizin bilgisini sunmuyor. Sunucu güncel koddan (ve{" "}
            <code>--catalog-index</code> ile) yeniden başlatılınca burada
            modelin, kapsamın ve &quot;Yeniden vektörle&quot; düğmesi görünür.
          </p>
        </section>
      )}
      <div className="knowledge-filters" role="tablist">
        {filters.map(([key, label]) => (
          <button
            key={key}
            role="tab"
            aria-selected={filter === key}
            className={filter === key ? "chosen" : ""}
            onClick={() => setFilter(key)}
          >
            {label}
          </button>
        ))}
      </div>
      {hint && (
        <p className="hint" role="status">
          {hint}
          <button type="button" onClick={() => setHint("")} aria-label="Kapat">
            <X size={13} />
          </button>
        </p>
      )}
      {issue && <p className="notice">{issue}</p>}
      {editing && (
        <DatasetForm
          owner={owner}
          documents={documents}
          session={session}
          initial={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            await refresh();
            await noteVectorGap();
          }}
        />
      )}
      <div className="series-list">
        {!listing && <LoaderCircle size={16} className="spin" />}
        {shown.map((item) => (
          <article key={item.series_id} className="knowledge-item">
            <button
              className="knowledge-head"
              aria-expanded={open === item.series_id}
              onClick={() =>
                setOpen(open === item.series_id ? null : item.series_id)
              }
            >
              <span className={`series-source ${item.origin}`}>
                {item.origin === "user" ? "KULLANICI" : item.provider}
              </span>
              <h3>{item.title}</h3>
              <small>{where(item)}</small>
              {(() => {
                const state = health(item, pool);
                if (!state) return null;
                return (
                  <span
                    className={`series-health ${state.stale ? "stale" : ""}`}
                  >
                    {state.first ? `${state.first} – ` : ""}
                    {state.last}
                    {state.observations !== null
                      ? ` · ${state.observations} gözlem`
                      : ""}
                    {state.months >= 4 ? ` · ${state.months} ay geride` : ""}
                  </span>
                );
              })()}
            </button>
            {open === item.series_id && (
              <SeriesDetail
                item={item}
                owner={owner}
                busy={busy}
                act={act}
                stored={health(item, pool)}
                vectored={
                  index && index.configured
                    ? !index.missing.includes(item.series_id)
                    : null
                }
                onOpenConversation={onOpenConversation}
                onEdit={async () => {
                  if (!item.slug) return;
                  try {
                    setEditing(await openDataset(owner, item.slug));
                  } catch (error) {
                    setIssue(describeError(error));
                  }
                }}
              />
            )}
          </article>
        ))}
        {listing && shown.length === 0 && (
          <p className="helper">Bu filtrede kayıt yok.</p>
        )}
      </div>
    </div>
  );
}

/**
 * The meaning-based half of discovery, in the state it is actually in.
 *
 * A generation of vectors is built for one exact catalogue. Everything the
 * knowledge base adds, renames or archives makes a different catalogue, and
 * until the vectors are built again the agent searches words alone. The card
 * says which it is, and builds them again with the same model and input policy.
 */
function VectorIndexCard({
  index,
  onRebuild,
}: {
  index: VectorIndex;
  onRebuild: () => Promise<void>;
}) {
  const covered = index.configured && index.covers_catalog;
  return (
    <section className="vector-index">
      <div className="vector-head">
        <h3>Anlamsal arama dizini</h3>
        <span className={covered ? "pill-ok" : "pill-warn"}>
          {!index.configured
            ? "kurulu değil"
            : covered
              ? "katalogla eşleşiyor"
              : "katalogla eşleşmiyor"}
        </span>
        {index.rebuildable && (
          <Button
            size="sm"
            variant="outline"
            disabled={index.rebuilding || !index.configured}
            onClick={() => void onRebuild()}
          >
            {index.rebuilding ? (
              <LoaderCircle size={13} className="spin" />
            ) : (
              <RefreshCw size={13} />
            )}
            {index.rebuilding ? "Vektörleniyor" : "Yeniden vektörle"}
          </Button>
        )}
      </div>
      {!index.configured ? (
        <p className="helper">
          Bu sunucu vektör dizini olmadan başlatılmış: arama yalnızca kelime
          eşleşmesiyle çalışır. Dizin, sunucu `--catalog-index` ile
          başlatıldığında açılır.
        </p>
      ) : (
        <>
          <dl className="vector-facts">
            <div>
              <dt>Model</dt>
              <dd>{index.model}</dd>
            </div>
            <div>
              <dt>Girdi politikası</dt>
              <dd>
                {index.input_policy_id} · {index.dimension} boyut
              </dd>
            </div>
            <div>
              <dt>Kapsam</dt>
              <dd>
                {index.series_vectored}/{index.series_total} kayıt vektörlü
              </dd>
            </div>
            <div>
              <dt>Katalog sürümü</dt>
              <dd>{index.catalog_version}</dd>
            </div>
          </dl>
          <p className="helper">
            Vektörler kendiliğinden oluşmaz: eklediğin açıklama, başlık ve eş
            anlamlılar ancak yeniden vektörlendikten sonra anlamsal aramaya
            girer. Kurulum her kayıt için bir gömme çağrısı demektir, bu yüzden
            düğmeye basınca arka planda çalışır.
          </p>
          {!covered && (
            <p className="helper">
              Vektörler {index.generation_version ?? "başka bir"} kataloğu için
              kuruldu. Bilgi tabanındaki değişiklikler yeniden vektörlenene
              kadar anlamsal aramaya girmez
              {index.missing.length > 0 && (
                <>
                  {" — kapsanmayan: "}
                  {index.missing.slice(0, 4).join(", ")}
                  {index.missing.length > 4
                    ? ` ve ${index.missing.length - 4} kayıt daha`
                    : ""}
                </>
              )}
              .
            </p>
          )}
          {index.last_error && (
            <p className="helper">
              Son kurulum tamamlanamadı ({index.last_error}); kullanımdaki
              vektörler değişmedi.
            </p>
          )}
          {index.built_at && !index.last_error && (
            <p className="helper">
              Son kurulum: {new Date(index.built_at).toLocaleString("tr-TR")}
            </p>
          )}
        </>
      )}
    </section>
  );
}

function SeriesDetail({
  item,
  owner,
  busy,
  act,
  stored: held,
  vectored,
  onEdit,
  onOpenConversation,
}: {
  item: KnowledgeSeries;
  owner: string;
  busy: boolean;
  act: (work: () => Promise<unknown>) => Promise<void>;
  /** The window the store really holds, when the catalogue record declares none. */
  stored: ReturnType<typeof health>;
  /** Whether the vectors in use cover this entry; null when none are configured. */
  vectored: boolean | null;
  onEdit: () => void;
  onOpenConversation?: (id: string) => void;
}) {
  const [aliases, setAliases] = useState(item.aliases.join(", "));
  const [note, setNote] = useState(item.note ?? "");
  //: Reverse lineage: this browser's answers whose proof read the series.
  const [uses, setUses] = useState<SeriesUses | null>(null);
  useEffect(() => {
    let cancelled = false;
    seriesUses(owner, item.series_id)
      .then((found) => {
        if (!cancelled) setUses(found);
      })
      .catch(() => {
        // An older server has no uses route; the section simply stays away.
      });
    return () => {
      cancelled = true;
    };
  }, [owner, item.series_id]);
  const [detail, setDetail] = useState<DatasetDetail | null>(null);
  const [history, setHistory] = useState<string[] | null>(null);
  const [stored, setStored] = useState<
    { period_end: string; value: number | null }[] | null
  >(null);
  const archived = item.status === "archived";
  const aliasList = aliases
    .split(",")
    .map((a) => a.trim())
    .filter(Boolean);
  return (
    <div className="knowledge-detail">
      <dl className="settings-list">
        <div>
          <dt>Kimlik</dt>
          <dd>
            <code>{item.series_id}</code>
          </dd>
        </div>
        <div>
          <dt>Anlam</dt>
          <dd>
            {unitLabel(item.unit, item.scale)} ·{" "}
            {frequencies[item.frequency] ?? item.frequency} ·{" "}
            {measures[item.stock_flow] ?? item.stock_flow}
            {item.cumulative !== "none" && item.cumulative !== "unknown"
              ? ` · kümülatif (${item.cumulative})`
              : ""}
            {item.base_year ? ` · baz ${item.base_year}` : ""}
          </dd>
        </div>
        <div>
          <dt>Kapsam</dt>
          <dd>
            {held
              ? `${held.first ? `${held.first} – ` : ""}${held.last}${
                  held.observations !== null
                    ? ` · ${held.observations} gözlem`
                    : ""
                }`
              : item.fetchable
                ? "Havuzda yok; ilk kullanımda resmî kaynağından alınır"
                : "Havuzda gözlem yok"}
          </dd>
        </div>
        <div>
          <dt>Anlamın kaynağı</dt>
          <dd>
            {item.origin === "user"
              ? "Senin beyanın; incelenmedi"
              : "İncelenmiş katalog kaydı"}
          </dd>
        </div>
        {item.description && (
          <div>
            <dt>Açıklama</dt>
            <dd>{item.description}</dd>
          </div>
        )}
        {item.labels && item.labels.length > 0 && (
          <div>
            <dt>Etiketler</dt>
            <dd>{item.labels.join(" · ")}</dd>
          </div>
        )}
        {item.reviewed_aliases && item.reviewed_aliases.length > 0 && (
          <div>
            <dt>İncelenmiş eş anlamlılar</dt>
            <dd>{item.reviewed_aliases.join(", ")}</dd>
          </div>
        )}
        {item.reviewer_note && (
          <div>
            <dt>İnceleyenin notu</dt>
            <dd>{item.reviewer_note}</dd>
          </div>
        )}
        <div>
          <dt>Arama</dt>
          <dd>
            {item.search_text
              ? vectored === null
                ? "Kelime aramasında; anlam vektörleri yapılandırılmamış"
                : vectored
                  ? "Kelime aramasında ve anlam vektörlerinde"
                  : "Kelime aramasında; anlam vektörü eksik (vektörleri yeniden üret)"
              : "Aranan katalogda değil (arşivli)"}
            {item.search_text && (
              <details className="search-text">
                <summary>Aramanın okuduğu metin</summary>
                <p>{item.search_text}</p>
              </details>
            )}
          </dd>
        </div>
        {uses && uses.uses.length > 0 && (
          <div>
            <dt>Bu seriyi kullanan yanıtlar</dt>
            <dd>
              <ul className="series-uses">
                {uses.uses.slice(0, 8).map((use) => (
                  <li key={`${use.conversation_id}-${use.turn_id}`}>
                    <button
                      type="button"
                      className="use-link"
                      title={use.question}
                      onClick={() => onOpenConversation?.(use.conversation_id)}
                      disabled={!onOpenConversation}
                    >
                      {use.title || use.question || use.conversation_id}
                      <small>
                        {use.question && use.question !== use.title
                          ? `${use.question.slice(0, 80)} · `
                          : ""}
                        {new Date(use.used_at).toLocaleDateString("tr-TR")}
                      </small>
                    </button>
                  </li>
                ))}
                {uses.uses.length > 8 && (
                  <li className="helper">
                    ve {uses.uses.length - 8} yanıt daha
                  </li>
                )}
              </ul>
            </dd>
          </div>
        )}
      </dl>
      {item.origin === "reviewed" ? (
        <div className="knowledge-form">
          <label>
            Eş anlamlılar (virgülle)
            <input
              value={aliases}
              maxLength={600}
              onChange={(e) => setAliases(e.target.value)}
              placeholder="ör. mortgage stoku"
            />
          </label>
          <label>
            Senin açıklaman (aramaya girer)
            <textarea
              value={note}
              maxLength={1000}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Bu seriyi kendi sözlerinle anlat; soruda bu sözler geçince bulunur"
            />
          </label>
          <p className="helper">
            Eş anlamlılar birebir eşleşir (soruda aynen geçerse seri doğrudan
            bulunur); açıklama kelime ve anlam aramasına girer. İkisi de
            incelenmiş metne eklenir, onu değiştirmez. Kaydettikten sonra anlam
            araması için vektörleri yeniden üret.
          </p>
          <div className="feedback-actions">
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() =>
                void act(() =>
                  annotateSeries(owner, item.series_id, {
                    archived,
                    aliases: aliasList,
                    ...(note.trim() ? { note: note.trim() } : {}),
                  }),
                )
              }
            >
              <Pencil size={13} /> Kaydet
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() =>
                void act(() =>
                  annotateSeries(owner, item.series_id, {
                    archived: !archived,
                    aliases: aliasList,
                    ...(note.trim() ? { note: note.trim() } : {}),
                  }),
                )
              }
            >
              {archived ? (
                <>
                  <ArchiveRestore size={13} /> Geri al
                </>
              ) : (
                <>
                  <Archive size={13} /> Arşivle
                </>
              )}
            </Button>
          </div>
        </div>
      ) : (
        <div className="feedback-actions">
          <Button
            size="sm"
            variant="outline"
            disabled={busy || !item.slug}
            onClick={() =>
              void (async () => {
                if (item.slug) setDetail(await openDataset(owner, item.slug));
              })()
            }
          >
            <History size={13} /> Değerler ve sürümler
          </Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={onEdit}>
            <Pencil size={13} /> Düzenle
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={busy || !item.slug}
            onClick={() =>
              void act(() => setDatasetArchived(owner, item.slug!, !archived))
            }
          >
            {archived ? (
              <>
                <ArchiveRestore size={13} /> Geri al
              </>
            ) : (
              <>
                <Archive size={13} /> Arşivle
              </>
            )}
          </Button>
        </div>
      )}
      {detail && (
        <div className="knowledge-values">
          <table>
            <thead>
              <tr>
                <th>Dönem sonu</th>
                <th>Değer</th>
              </tr>
            </thead>
            <tbody>
              {detail.observations.slice(-24).map((o) => (
                <tr key={o.period_end}>
                  <td>{o.period_end}</td>
                  <td>
                    {o.value === null ? "—" : o.value.toLocaleString("tr-TR")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {detail.observations.length > 24 && (
            <p className="helper">
              Son 24 dönem gösteriliyor ({detail.observations.length} toplam).
            </p>
          )}
          <ol className="knowledge-history">
            {detail.history.map((v) => (
              <li key={v.version}>
                v{v.version} · {v.status === "archived" ? "arşiv" : "etkin"} ·{" "}
                {v.observations} gözlem ·{" "}
                {new Date(v.created_at).toLocaleString("tr-TR")} ·{" "}
                <code>{v.content_sha256.slice(0, 12)}</code>
              </li>
            ))}
          </ol>
        </div>
      )}
      {item.origin === "reviewed" && item.prepared && (
        <Button
          size="sm"
          variant="ghost"
          onClick={() =>
            void (async () => {
              const found = await seriesValues(owner, item.series_id);
              setStored(found.observations);
            })()
          }
        >
          <History size={13} /> Değerleri göster
        </Button>
      )}
      {stored && (
        <div className="knowledge-values">
          <table>
            <thead>
              <tr>
                <th>Dönem sonu</th>
                <th>Değer</th>
              </tr>
            </thead>
            <tbody>
              {stored.slice(-24).map((o) => (
                <tr key={o.period_end}>
                  <td>{o.period_end}</td>
                  <td>
                    {o.value === null ? "—" : o.value.toLocaleString("tr-TR")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="helper">
            Hazır havuzda saklanan değerler
            {stored.length > 24
              ? ` · son 24 dönem (${stored.length} toplam)`
              : ""}
            .
          </p>
        </div>
      )}
      {item.origin === "reviewed" && (
        <Button
          size="sm"
          variant="ghost"
          onClick={() =>
            void (async () => {
              const found = await seriesNotes(owner, item.series_id);
              setHistory(
                found.history.map(
                  (v) =>
                    `v${v.version} · ${v.archived ? "arşivlendi" : "etkin"} · ` +
                    `${v.aliases.join(", ") || "eş anlamlı yok"} · ` +
                    `${new Date(v.created_at).toLocaleString("tr-TR")}` +
                    (v.note ? ` · ${v.note}` : ""),
                ),
              );
            })()
          }
        >
          <History size={13} /> Düzenleme geçmişi
        </Button>
      )}
      {history && (
        <ol className="knowledge-history">
          {history.length === 0 && <li>Henüz düzenleme yok.</li>}
          {history.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ol>
      )}
    </div>
  );
}

function DatasetForm({
  owner,
  documents,
  initial,
  onClose,
  onSaved,
  session = null,
}: {
  owner: string;
  documents: ChatDocument[];
  initial: DatasetDetail | null;
  onClose: () => void;
  onSaved: () => Promise<void>;
  session?: { id: string; token: string } | null;
}) {
  const series = initial?.series;
  const [form, setForm] = useState({
    slug: series?.slug ?? "",
    title: series?.title ?? "",
    description: initial?.description ?? "",
    unit: series?.unit ?? "TRY",
    scale: (series?.scale ?? "million") as DatasetRequest["scale"],
    frequency: (series?.frequency ?? "monthly") as DatasetRequest["frequency"],
    stock_flow: (series?.stock_flow ?? "stock") as DatasetRequest["stock_flow"],
    cumulative: (series?.cumulative ?? "none") as DatasetRequest["cumulative"],
    aggregation: (initial?.aggregation ??
      "last") as DatasetRequest["aggregation"],
    base_year: series?.base_year ? String(series.base_year) : "",
    weekly_anchor: (initial?.weekly_anchor ?? "friday") as NonNullable<
      DatasetRequest["weekly_anchor"]
    >,
    aliases: series?.aliases.join(", ") ?? "",
  });
  const [source, setSource] = useState<"rows" | "document">("rows");
  const [rows, setRows] = useState(
    initial?.observations
      .map((o) => `${o.period_end.slice(0, 7)};${o.value ?? ""}`)
      .join("\n") ?? "",
  );
  //: Documents fetched from an address during this form, admitted like uploads.
  const [extraDocs, setExtraDocs] = useState<ChatDocument[]>([]);
  const allDocs = [...documents, ...extraDocs];
  const [urlDraft, setUrlDraft] = useState("");
  const [fetchingUrl, setFetchingUrl] = useState(false);
  const [document, setDocument] = useState(documents[0]?.ref ?? "");

  async function fetchFromUrl() {
    if (!session || !/^https:\/\//.test(urlDraft.trim())) return;
    setFetchingUrl(true);
    setIssue("");
    try {
      const admitted = await admitDocumentFromUrl(
        {
          api_version: 1,
          session_id: session.id,
          token: session.token,
          survives_restart: true,
        },
        urlDraft,
      );
      const entry: ChatDocument = {
        sessionId: session.id,
        ref: admitted.document_ref,
        label: `Adresten belge ${extraDocs.length + 1} · ${admitted.document_format.toUpperCase()}`,
      };
      setExtraDocs((current) => [...current, entry]);
      setDocument(entry.ref);
      setSource("document");
      setUrlDraft("");
    } catch (error) {
      setIssue(describeError(error));
    } finally {
      setFetchingUrl(false);
    }
  }
  const [columns, setColumns] = useState({ period: "", value: "" });
  const [issue, setIssue] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (key: keyof typeof form) => (value: string) =>
    setForm((current) => ({ ...current, [key]: value }));

  async function submit() {
    const request: DatasetRequest = {
      slug: form.slug.trim(),
      title: form.title.trim(),
      ...(form.description.trim()
        ? { description: form.description.trim() }
        : {}),
      unit: form.unit.trim(),
      scale: form.scale,
      frequency: form.frequency,
      stock_flow: form.stock_flow,
      cumulative: form.cumulative,
      aggregation: form.aggregation,
      ...(form.base_year ? { base_year: Number(form.base_year) } : {}),
      ...(form.frequency === "weekly"
        ? { weekly_anchor: form.weekly_anchor }
        : {}),
      aliases: form.aliases
        .split(",")
        .map((a) => a.trim())
        .filter(Boolean),
    };
    if (source === "rows") {
      const weekly = form.frequency === "weekly";
      const parsed = weekly ? parseDatedRows(rows) : parseMonthlyRows(rows);
      if (parsed.rejected.length) {
        setIssue(
          `Okunamayan satırlar: ${parsed.rejected.slice(0, 8).join(", ")}. Biçim: ${weekly ? "YYYY-AA-GG" : "YYYY-AA"};değer`,
        );
        return;
      }
      request.observations = parsed.observations;
    } else {
      const chosen = documents.find((d) => d.ref === document);
      if (!chosen || !columns.period.trim() || !columns.value.trim()) {
        setIssue("Belgeyi ve iki sütun başlığını seç.");
        return;
      }
      request.document = {
        session_id: chosen.sessionId,
        document_ref: chosen.ref,
        period_column: columns.period.trim(),
        value_column: columns.value.trim(),
      };
    }
    setBusy(true);
    setIssue("");
    try {
      await saveDataset(owner, request);
      await onSaved();
    } catch (error) {
      setIssue(describeError(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="knowledge-editor" aria-label="Veri seti">
      <header>
        <strong>{initial ? "Veri setini düzenle" : "Yeni veri seti"}</strong>
        <Button
          size="icon"
          variant="ghost"
          aria-label="Kapat"
          onClick={onClose}
        >
          <X size={15} />
        </Button>
      </header>
      <p className="helper">
        Her kayıt yeni bir sürümdür; eski sürüm ve onu kullanan cevaplar
        değişmez. Birim ve anlamı sen beyan edersin; kayıt “incelenmedi” diye
        işaretlenir.
      </p>
      <div className="knowledge-form grid">
        <label>
          Kısa ad (küçük harf, _)
          <input
            value={form.slug}
            disabled={Boolean(initial)}
            pattern="[a-z][a-z0-9_]{2,39}"
            onChange={(e) => set("slug")(e.target.value)}
          />
        </label>
        <label>
          Başlık
          <input
            value={form.title}
            onChange={(e) => set("title")(e.target.value)}
          />
        </label>
        <label>
          Birim
          <input
            value={form.unit}
            onChange={(e) => set("unit")(e.target.value)}
          />
        </label>
        <label>
          Ölçek
          <select
            value={form.scale}
            onChange={(e) => set("scale")(e.target.value)}
          >
            <option value="one">bir</option>
            <option value="thousand">bin</option>
            <option value="million">milyon</option>
            <option value="billion">milyar</option>
          </select>
        </label>
        <label>
          Sıklık
          <select
            value={form.frequency}
            onChange={(e) => set("frequency")(e.target.value)}
          >
            <option value="weekly">haftalık</option>
            <option value="monthly">aylık</option>
            <option value="quarterly">çeyreklik</option>
            <option value="annual">yıllık</option>
          </select>
        </label>
        {form.frequency === "weekly" && (
          <label>
            Hafta hangi gün biter?
            <select
              value={form.weekly_anchor}
              onChange={(e) => set("weekly_anchor")(e.target.value)}
            >
              <option value="friday">cuma</option>
              <option value="wednesday">çarşamba</option>
              <option value="thursday">perşembe</option>
              <option value="monday">pazartesi</option>
              <option value="tuesday">salı</option>
              <option value="saturday">cumartesi</option>
              <option value="sunday">pazar</option>
            </select>
          </label>
        )}
        <label>
          Ölçü türü
          <select
            value={form.stock_flow}
            onChange={(e) => set("stock_flow")(e.target.value)}
          >
            <option value="stock">stok (bakiye)</option>
            <option value="flow">akış (dönem içi)</option>
            <option value="rate">oran</option>
            <option value="index">endeks</option>
          </select>
        </label>
        <label>
          Kümülatif mi?
          <select
            value={form.cumulative}
            onChange={(e) => set("cumulative")(e.target.value)}
          >
            <option value="none">hayır</option>
            <option value="yearly_reset">yıl başında sıfırlanır</option>
            <option value="since_inception">başlangıçtan beri</option>
          </select>
        </label>
        <label>
          Birleştirme
          <select
            value={form.aggregation}
            onChange={(e) => set("aggregation")(e.target.value)}
          >
            <option value="last">son değer</option>
            <option value="sum">toplam</option>
            <option value="average">ortalama</option>
            <option value="first">ilk değer</option>
            <option value="min">en küçük</option>
            <option value="max">en büyük</option>
          </select>
        </label>
        <label>
          Baz yılı (endeks için)
          <input
            value={form.base_year}
            inputMode="numeric"
            onChange={(e) => set("base_year")(e.target.value)}
          />
        </label>
        <label>
          Eş anlamlılar (virgülle)
          <input
            value={form.aliases}
            onChange={(e) => set("aliases")(e.target.value)}
          />
        </label>
      </div>
      <label className="knowledge-form">
        Açıklama
        <textarea
          value={form.description}
          maxLength={1000}
          onChange={(e) => set("description")(e.target.value)}
        />
      </label>
      <div className="knowledge-filters" role="radiogroup" aria-label="Kaynak">
        {session && (
          <div className="url-fetch">
            <input
              type="url"
              inputMode="url"
              placeholder="https://… — CSV/Excel tablo adresi"
              aria-label="Tablo adresi"
              value={urlDraft}
              maxLength={2000}
              disabled={fetchingUrl}
              onChange={(e) => setUrlDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void fetchFromUrl();
                }
              }}
            />
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={fetchingUrl || !/^https:\/\//.test(urlDraft.trim())}
              onClick={() => void fetchFromUrl()}
              title="Adres güvenli indirme kurallarından geçer (yalnız GET, https, sınırlı boyut) ve bir yükleme gibi kabul edilir."
            >
              {fetchingUrl ? (
                <LoaderCircle size={13} className="spin" />
              ) : (
                <Download size={13} />
              )}{" "}
              Adresten getir
            </Button>
          </div>
        )}
        <button
          role="radio"
          aria-checked={source === "rows"}
          className={source === "rows" ? "chosen" : ""}
          onClick={() => setSource("rows")}
        >
          Değerleri yapıştır
        </button>
        <button
          role="radio"
          aria-checked={source === "document"}
          className={source === "document" ? "chosen" : ""}
          disabled={allDocs.length === 0 || form.frequency !== "monthly"}
          title={
            allDocs.length === 0
              ? "Önce sohbete bir belge yükle ya da bir adresten getir"
              : "Belgeden okuma yalnız aylık dönemlerle çalışır"
          }
          onClick={() => setSource("document")}
        >
          Sohbetteki belgeden
        </button>
      </div>
      {source === "rows" ? (
        <label className="knowledge-form">
          {form.frequency === "weekly"
            ? "Her satır: YYYY-AA-GG;değer (dönem sonu tarihi; boş değer boş kalır)"
            : "Her satır: YYYY-AA;değer (boş değer boş kalır)"}
          <textarea
            rows={8}
            value={rows}
            onChange={(e) => setRows(e.target.value)}
            placeholder={"2025-01;100\n2025-02;110"}
          />
        </label>
      ) : (
        <div className="knowledge-form grid">
          <label>
            Belge
            <select
              value={document}
              onChange={(e) => setDocument(e.target.value)}
            >
              {allDocs.map((d) => (
                <option key={d.ref} value={d.ref}>
                  {d.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Dönem sütunu başlığı
            <input
              value={columns.period}
              onChange={(e) =>
                setColumns((c) => ({ ...c, period: e.target.value }))
              }
            />
          </label>
          <label>
            Değer sütunu başlığı
            <input
              value={columns.value}
              onChange={(e) =>
                setColumns((c) => ({ ...c, value: e.target.value }))
              }
            />
          </label>
        </div>
      )}
      {issue && <p className="notice">{issue}</p>}
      <div className="feedback-actions">
        <Button size="sm" disabled={busy} onClick={() => void submit()}>
          {busy && <LoaderCircle size={13} className="spin" />} Kaydet
        </Button>
      </div>
    </section>
  );
}
