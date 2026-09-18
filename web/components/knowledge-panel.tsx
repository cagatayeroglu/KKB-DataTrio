"use client";
import { useEffect, useMemo, useState } from "react";
import {
  Archive,
  ArchiveRestore,
  Download,
  History,
  LoaderCircle,
  Pencil,
  Plus,
  Search,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  annotateSeries,
  describeError,
  listKnowledge,
  openDataset,
  parseDatedRows,
  parseMonthlyRows,
  saveDataset,
  seriesNotes,
  seriesValues,
  setDatasetArchived,
} from "@/lib/client";
import type {
  Dataset,
  DatasetDetail,
  DatasetRequest,
  KnowledgeList,
  KnowledgeSeries,
} from "@/lib/contracts";
import { unitLabel } from "@/lib/table";

type Filter =
  "all" | "prepared" | "fetchable" | "catalog" | "user" | "archived";
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
}: {
  owner: string;
  documents: ChatDocument[];
  /** The prepared pool's own coverage, which the catalogue record does not carry. */
  pool?: Dataset | null;
}) {
  const [listing, setListing] = useState<KnowledgeList | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [editing, setEditing] = useState<DatasetDetail | "new" | null>(null);
  const [issue, setIssue] = useState("");
  const [busy, setBusy] = useState(false);

  /** The catalogue as this browser sees it, saved as it is read: no server call. */
  function exportListing() {
    if (!listing) return;
    const blob = new Blob([JSON.stringify(listing, null, 2)], {
      type: "application/json",
    });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `bilgi-tabani-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  }
  async function refresh() {
    try {
      setListing(await listKnowledge(owner));
      setIssue("");
    } catch (error) {
      setIssue(describeError(error));
    }
  }
  useEffect(() => {
    void refresh();
  }, [owner]);

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
    } catch (error) {
      setIssue(describeError(error));
    } finally {
      setBusy(false);
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
            aria-label="Bilgi tabanında ara"
            placeholder="Ad, kimlik veya eş anlamlı"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <Button
          size="sm"
          variant="outline"
          disabled={!listing}
          onClick={() => exportListing()}
        >
          <Download size={14} /> Dışa aktar
        </Button>
        <Button size="sm" onClick={() => setEditing("new")} disabled={busy}>
          <Plus size={14} /> Veri seti ekle
        </Button>
      </div>
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
      {issue && <p className="notice">{issue}</p>}
      {editing && (
        <DatasetForm
          owner={owner}
          documents={documents}
          initial={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            await refresh();
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

function SeriesDetail({
  item,
  owner,
  busy,
  act,
  onEdit,
}: {
  item: KnowledgeSeries;
  owner: string;
  busy: boolean;
  act: (work: () => Promise<unknown>) => Promise<void>;
  onEdit: () => void;
}) {
  const [aliases, setAliases] = useState(item.aliases.join(", "));
  const [note, setNote] = useState(item.note ?? "");
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
            {item.coverage_start ?? "?"} – {item.coverage_end ?? "?"}
            {item.observations !== null ? ` · ${item.observations} gözlem` : ""}
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
            Not
            <textarea
              value={note}
              maxLength={1000}
              onChange={(e) => setNote(e.target.value)}
            />
          </label>
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
}: {
  owner: string;
  documents: ChatDocument[];
  initial: DatasetDetail | null;
  onClose: () => void;
  onSaved: () => Promise<void>;
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
    weekly_anchor: "friday" as NonNullable<DatasetRequest["weekly_anchor"]>,
    aliases: series?.aliases.join(", ") ?? "",
  });
  const [source, setSource] = useState<"rows" | "document">("rows");
  const [rows, setRows] = useState(
    initial?.observations
      .map((o) => `${o.period_end.slice(0, 7)};${o.value ?? ""}`)
      .join("\n") ?? "",
  );
  const [document, setDocument] = useState(documents[0]?.ref ?? "");
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
          disabled={documents.length === 0 || form.frequency !== "monthly"}
          title={
            documents.length === 0
              ? "Önce sohbete bir belge yükle"
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
              {documents.map((d) => (
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
