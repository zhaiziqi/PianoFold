import { DIFFICULTIES, type Difficulty } from "../lib/project";

const labels = {
  simple: ["Simple", "Room to begin"],
  standard: ["Standard", "A balanced arrangement"],
  rich: ["Rich", "More musical detail"],
} as const;

export function DifficultySelector({ value, onChange }: { value: Difficulty; onChange: (value: Difficulty) => void }) {
  return (
    <fieldset className="difficulty-selector">
      <legend className="eyebrow">Choose your arrangement</legend>
      <div className="difficulty-options">
        {DIFFICULTIES.map((difficulty) => (
          <label key={difficulty} className={`difficulty-option${value === difficulty ? " is-selected" : ""}`}>
            <input type="radio" name="difficulty" value={difficulty} checked={value === difficulty} onChange={() => onChange(difficulty)} />
            <span><strong>{labels[difficulty][0]}</strong><small>{labels[difficulty][1]}</small></span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
