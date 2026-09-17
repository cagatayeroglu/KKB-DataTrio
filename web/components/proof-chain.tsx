"use client";
import {
  Calculator,
  Database,
  FileText,
  Server,
  ShieldAlert,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import type { Dataset, Proof } from "@/lib/contracts";
import { noticeText } from "@/lib/language";
import {
  documentLocation,
  documentName,
  documentOrigin,
  gapText,
  orderedSteps,
  proofHeadline,
  sourceCoverage,
  sourceOrigin,
  sourceName,
  sourceSemantics,
  stepCheck,
  stepInputs,
  stepTitle,
} from "@/lib/proof";
import { periodLabel } from "@/lib/table";

/** Server-recorded, result-level evidence. Rendered as text nodes only. */
export function ProofChain({
  proof,
  dataset,
}: {
  proof: Proof;
  dataset: Dataset | null;
}) {
  const recorded = proof.availability !== "unavailable";
  return (
    <section
      className={`proof-chain ${proof.availability}`}
      aria-label="Kanıt zinciri"
    >
      <div className="proof-headline">
        {proof.availability === "available" ? (
          <ShieldCheck size={16} />
        ) : (
          <ShieldAlert size={16} />
        )}
        <strong>{proofHeadline(proof)}</strong>
      </div>
      {recorded && (
        <ol className="proof-layers">
          {proof.sources.map((source, index) => (
            <li key={`source-${index}`} className="proof-layer">
              <span className="proof-icon">
                <Server size={14} />
              </span>
              <div>
                <h4>{sourceName(source, dataset)}</h4>
                <p>{sourceOrigin(source)}</p>
                <p>{sourceCoverage(source)}</p>
                <p className="muted">{sourceSemantics(source)}</p>
                {source.dataset_sha256 && (
                  <p
                    className="mono"
                    title="İçerik kimliği; doğruluk kanıtı değildir"
                  >
                    <Database size={11} /> {source.dataset_sha256.slice(0, 16)}…
                  </p>
                )}
              </div>
            </li>
          ))}
          {proof.documents.map((document, index) => (
            <li key={`document-${index}`} className="proof-layer">
              <span className="proof-icon">
                <FileText size={14} />
              </span>
              <div>
                <h4>{documentName(document)}</h4>
                <p>{documentOrigin(document)}</p>
                <p>
                  {document.column === null
                    ? "Okunan tablo"
                    : document.row === null
                      ? "Okunan sütun"
                      : "Okunan hücre"}
                  : {documentLocation(document)}
                </p>
                <p
                  className="mono"
                  title="İçerik kimliği; doğruluk kanıtı değildir"
                >
                  <Database size={11} /> {document.content_sha256.slice(0, 16)}…
                </p>
              </div>
            </li>
          ))}
          {orderedSteps(proof).map(({ step, index }) => (
            <li key={`step-${index}`} className="proof-layer">
              <span className="proof-icon">
                <Calculator size={14} />
              </span>
              <div>
                <h4>
                  {stepTitle(step)}
                  {index === 0 ? " — bu sonuç" : ""}
                  {step.workspace_name ? ` (${step.workspace_name})` : ""}
                </h4>
                <p>
                  Girdi: {stepInputs(proof, step, dataset).join(", ") || "—"}
                </p>
                {step.coverage && <p>Kapsam: {periodLabel(step.coverage)}</p>}
                {step.samples && (
                  <p>
                    {step.samples.used} gözlem kullanıldı ·{" "}
                    {step.samples.missing} eksik · {step.samples.excluded}{" "}
                    dışlanan
                  </p>
                )}
                <p className="muted">{stepCheck(step)}</p>
              </div>
            </li>
          ))}
          <li className="proof-layer">
            <span className="proof-icon">
              <ShieldCheck size={14} />
            </span>
            <div>
              <h4>Cevap denetimi: kabul edildi</h4>
              <p className="muted">
                Kayıt kapsamı doğruluk garantisi değildir; kanıt sonuç
                düzeyindedir, bu hücrenin tek tek hangi gözlemden geldiği ayrıca
                eşlenmez.
              </p>
            </div>
          </li>
        </ol>
      )}
      {[
        ...proof.gaps.map(gapText),
        ...proof.warnings.map(noticeText),
        ...proof.limitations.map(noticeText),
        ...proof.unresolved_semantics.map(noticeText),
      ].map((text, index) => (
        <p key={`note-${index}`} className="proof-note">
          <TriangleAlert size={12} /> {text}
        </p>
      ))}
    </section>
  );
}
