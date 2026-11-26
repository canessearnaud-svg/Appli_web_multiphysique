type Series = { x: number[]; y: number[]; color?: string };

export default function SvgPlot({
  series,
  width = 680,
  height = 260,
}: {
  series: Series[];
  width?: number;
  height?: number;
}) {
  const xs = series.flatMap((s) => s.x);
  const ys = series.flatMap((s) => s.y);
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  const y0 = Math.min(...ys);
  const y1 = Math.max(...ys);
  const pad = 40;
  const sx = (x: number) => pad + ((x - x0) / (x1 - x0 || 1)) * (width - 2 * pad);
  const sy = (y: number) => height - pad - ((y - y0) / (y1 - y0 || 1)) * (height - 2 * pad);
  return (
    <svg width={width} height={height} style={{ border: "1px solid #ccc", background: "#fff" }}>
      <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} stroke="#333" />
      <line x1={pad} y1={pad} x2={pad} y2={height - pad} stroke="#333" />
      {series.map((s, i) => (
        <polyline
          key={i}
          fill="none"
          stroke={s.color ?? "#1f77b4"}
          strokeWidth={1.5}
          points={s.x.map((x, k) => `${sx(x)},${sy(s.y[k])}`).join(" ")}
        />
      ))}
      <text x={width / 2} y={height - 8} textAnchor="middle" fontSize={11}>
        {x0.toFixed(3)} … {x1.toFixed(3)}
      </text>
      <text x={6} y={pad + 4} fontSize={11}>
        {y1.toFixed(3)}
      </text>
      <text x={6} y={height - pad} fontSize={11}>
        {y0.toFixed(3)}
      </text>
    </svg>
  );
}
