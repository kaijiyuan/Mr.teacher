import { useState } from "react";

export function CustomSelect({ value, options, onChange }) {
  const [open, setOpen] = useState(false);

  return (
    <div className={`custom-select ${open ? "open" : ""}`}>
      <button type="button" className="custom-select-trigger" onClick={() => setOpen(!open)}>
        <span>{value}</span>
        <span className="custom-select-arrow" />
      </button>
      {open ? (
        <div className="custom-select-menu">
          {options.map((item) => (
            <button
              key={item}
              type="button"
              className={item === value ? "active" : ""}
              onClick={() => {
                onChange(item);
                setOpen(false);
              }}
            >
              {item}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
