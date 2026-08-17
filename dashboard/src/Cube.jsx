// The cube: one square tile per signal. Three faces, picked by what the
// caller passes — label only (a binary check, read purely from its color),
// label + subtitle (Title/Meta), label + big value (everything numeric).
//
// `status` is "good" | "warn" | "bad", or undefined for a signal with no
// natural good/bad direction — those stay transparent line drawings.

const STATUS_FILL = {
  good: "var(--status-good)",
  warn: "var(--status-warn)",
  bad: "var(--status-bad)",
};

export function Corners() {
  return (
    <>
      <i className="corner tl" />
      <i className="corner tr" />
      <i className="corner bl" />
      <i className="corner br" />
    </>
  );
}

export function CubeGrid({ children }) {
  return <div className="cube-grid">{children}</div>;
}

export function Cube({ label, value, sub, status }) {
  const fill = STATUS_FILL[status];
  const labelOnly = value === undefined && sub === undefined;

  return (
    <div
      className={`card blueprint cube ${fill ? "cube-solid" : ""}`}
      style={fill ? { background: fill, borderColor: fill } : undefined}
    >
      <Corners />
      {labelOnly ? (
        <div className="cube-label cube-label-only">{label}</div>
      ) : (
        <>
          <div className="cube-label">{label}</div>
          {sub !== undefined ? (
            <div className="cube-sub">{sub}</div>
          ) : (
            <div className="cube-value">{value}</div>
          )}
        </>
      )}
    </div>
  );
}

// Threshold helpers, in the two directions the signals actually come in.
export function higherIsBetter(v, good, warn) {
  return v >= good ? "good" : v >= warn ? "warn" : "bad";
}

export function lowerIsBetter(v, good, warn) {
  return v < good ? "good" : v <= warn ? "warn" : "bad";
}

// A signal is null when its check failed, when the site genuinely has nothing
// to report, or when the run predates the check existing. Either way it reads
// as unknown and stays uncolored — we don't score a measurement we don't have,
// and a red cube must always mean "we looked and it was bad", never "we never
// looked".
export function scored(label, value, format, statusFor) {
  if (value === null || value === undefined) return { label, value: "unknown" };
  return { label, value: format(value), status: statusFor?.(value) };
}

// The binary form of the same rule: the color is the whole answer, so the cube
// shows its label only — unless we have no measurement, which has to say so.
export function binary(label, value) {
  if (value === null || value === undefined) return { label, value: "unknown" };
  return { label, status: value ? "good" : "bad" };
}
