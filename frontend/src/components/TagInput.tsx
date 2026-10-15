import { KeyboardEvent, useState } from "react";

type Props = {
  name?: string;
  initial?: string[];
  suggestions?: string[];
  onChange?: (tags: string[]) => void;
};

const norm = (s: string) => s.trim().replace(/^#+/, "").trim().toLowerCase().replace(/\s+/g, "-");

/** Campo de etiquetas: Enter o coma las confirma. Envía la lista en un input oculto (separada por comas). */
export default function TagInput({ name = "tags", initial = [], suggestions = [], onChange }: Props) {
  const [tags, setTags] = useState<string[]>(initial);
  const [text, setText] = useState("");
  const listId = `tags-${name}`;

  function commit(raw: string) {
    const t = norm(raw);
    if (!t || tags.includes(t) || tags.length >= 10) return setText("");
    const next = [...tags, t];
    setTags(next);
    setText("");
    onChange?.(next);
  }
  function remove(t: string) {
    const next = tags.filter((x) => x !== t);
    setTags(next);
    onChange?.(next);
  }
  function onKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      commit(text);
    } else if (e.key === "Backspace" && !text && tags.length) {
      remove(tags[tags.length - 1]);
    }
  }

  return (
    <div className="taginput">
      {tags.map((t) => (
        <span className="tagchip" key={t}>#{t}<button type="button" className="link" onClick={() => remove(t)} aria-label={`Quitar ${t}`}>✕</button></span>
      ))}
      <input
        value={text} list={listId} maxLength={30}
        placeholder={tags.length ? "" : "Etiquetas (ej. viaje-cartagena)"}
        onChange={(e) => setText(e.target.value)} onKeyDown={onKey} onBlur={() => text && commit(text)}
      />
      <datalist id={listId}>{suggestions.filter((s) => !tags.includes(s)).map((s) => <option key={s} value={s} />)}</datalist>
      <input type="hidden" name={name} value={tags.join(",")} />
    </div>
  );
}
