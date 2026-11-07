import { strings } from "../copy/strings";

export function CategoryFilter({
  categories,
  selected,
  onChange,
}: {
  categories: string[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  function toggle(category: string) {
    if (selected.includes(category)) onChange(selected.filter((item) => item !== category));
    else onChange([...selected, category]);
  }

  return (
    <div className="chips" role="group" aria-label={strings.categories}>
      {categories.map((category) => {
        const pressed = selected.includes(category);
        return (
          <button
            key={category}
            type="button"
            className={pressed ? "chip on" : "chip"}
            aria-pressed={pressed}
            onClick={() => toggle(category)}
          >
            {category}
          </button>
        );
      })}
    </div>
  );
}
