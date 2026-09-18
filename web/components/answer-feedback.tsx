"use client";
import { useState } from "react";
import { Check, LoaderCircle, ThumbsDown, ThumbsUp } from "lucide-react";
import { describeError, rateAnswer } from "@/lib/client";
import type { Feedback, FeedbackReason } from "@/lib/contracts";

const reasonLabels: Record<FeedbackReason, string> = {
  accuracy: "Doğruluk",
  incomplete: "Eksik cevap",
  wrong_source: "Yanlış veri/kaynak",
  slow: "Yavaş",
  lost_context: "Tablo/bağlam kaybı",
  unclear: "Anlaşılmıyor",
  other: "Diğer",
};

export function AnswerFeedback({
  conversationId,
  token,
  turnId,
  saved,
  onSaved,
  onOpenTrace,
}: {
  conversationId: string;
  token: string;
  turnId: string;
  saved?: Feedback;
  onSaved: (feedback: Feedback) => void;
  onOpenTrace?: (runId?: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [comment, setComment] = useState(saved?.comment ?? "");
  const [reasons, setReasons] = useState<FeedbackReason[]>(
    saved?.reasons ?? [],
  );
  const [score, setScore] = useState<number | null>(saved?.score ?? null);
  const [busy, setBusy] = useState(false);
  const [issue, setIssue] = useState("");

  async function send(rating: "up" | "down", withWords = false) {
    setBusy(true);
    setIssue("");
    try {
      const stored = await rateAnswer(conversationId, token, {
        turn_id: turnId,
        rating,
        ...(withWords && comment.trim()
          ? { comment: comment.trim().slice(0, 2000) }
          : {}),
        ...(withWords && reasons.length ? { reasons } : {}),
        ...(withWords && score !== null ? { score } : {}),
      });
      onSaved(stored);
      if (!withWords && rating === "down") setOpen(true);
      else setOpen(false);
    } catch (error) {
      setIssue(describeError(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="answer-feedback">
      <span>Bu cevap işine yaradı mı?</span>
      <button
        type="button"
        aria-label="Olumlu"
        aria-pressed={saved?.rating === "up"}
        className={saved?.rating === "up" ? "chosen" : ""}
        disabled={busy}
        onClick={() => void send("up")}
      >
        <ThumbsUp size={13} />
      </button>
      <button
        type="button"
        aria-label="Olumsuz"
        aria-pressed={saved?.rating === "down"}
        className={saved?.rating === "down" ? "chosen" : ""}
        disabled={busy}
        onClick={() => void send("down")}
      >
        <ThumbsDown size={13} />
      </button>
      <button
        type="button"
        className="link"
        onClick={() => setOpen((value) => !value)}
      >
        {saved?.comment ? "Yorumu düzenle" : "Yorum ekle"}
      </button>
      {onOpenTrace && (
        <button
          type="button"
          className="link"
          onClick={() => onOpenTrace(saved?.run_id ?? undefined)}
        >
          İşlemi incele
        </button>
      )}
      {busy && <LoaderCircle size={13} className="spin" />}
      {saved && !busy && !open && (
        <span className="saved">
          <Check size={12} /> kaydedildi
        </span>
      )}
      {issue && <span className="notice">{issue}</span>}
      {open && (
        <div className="feedback-form">
          <div
            className="feedback-score"
            role="radiogroup"
            aria-label="Cevabın işe yararlığı, 1-5"
          >
            <span>Puan</span>
            {[1, 2, 3, 4, 5].map((value) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-label={`${value} puan`}
                aria-checked={score === value}
                className={score === value ? "chosen" : ""}
                title={
                  value === 1
                    ? "Hiç işe yaramadı"
                    : value === 5
                      ? "Tam olarak işe yaradı"
                      : undefined
                }
                onClick={() =>
                  setScore((current) => (current === value ? null : value))
                }
              >
                {value}
              </button>
            ))}
          </div>
          <div className="feedback-reasons">
            {(Object.keys(reasonLabels) as FeedbackReason[]).map((reason) => (
              <button
                key={reason}
                type="button"
                className={reasons.includes(reason) ? "chosen" : ""}
                onClick={() =>
                  setReasons((current) =>
                    current.includes(reason)
                      ? current.filter((item) => item !== reason)
                      : [...current, reason],
                  )
                }
              >
                {reasonLabels[reason]}
              </button>
            ))}
          </div>
          <textarea
            value={comment}
            maxLength={2000}
            placeholder="Ne eksik ya da yanlıştı?"
            aria-label="Cevap hakkında yorum"
            onChange={(event) => setComment(event.target.value)}
          />
          <div className="feedback-actions">
            <button
              type="button"
              disabled={busy}
              onClick={() => void send("down", true)}
            >
              Olumsuz olarak kaydet
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void send("up", true)}
            >
              Olumlu olarak kaydet
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
