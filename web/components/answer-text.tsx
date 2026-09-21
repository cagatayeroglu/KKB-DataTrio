// The answer as it was written: its own lines and paragraphs, with the parts a reader
// looks for - the interpretation, the assumption, the system's note - named in bold.
// Presentation only: not a character of the text is added, removed or reordered.
const LABELS = ["Yorum:", "Varsayım:", "Not:"];

export function AnswerText({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <p className="answer-text">
      {lines.map((line, index) => {
        const label = LABELS.find((item) => line.startsWith(item));
        return (
          <span key={index}>
            {label ? (
              <>
                <strong className="answer-label">{label}</strong>
                {line.slice(label.length)}
              </>
            ) : (
              line
            )}
            {index < lines.length - 1 ? "\n" : ""}
          </span>
        );
      })}
    </p>
  );
}
