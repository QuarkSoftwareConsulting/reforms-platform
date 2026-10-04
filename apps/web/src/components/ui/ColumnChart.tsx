"use client";

import { useId, useState } from "react";

export interface ColumnDatum {
  /** Etiqueta corta del eje X (p. ej. "3 mar"). */
  label: string;
  value: number;
  /** El valor ya formateado ("12", "45,00 EUR"): lo que lee la persona. */
  display: string;
}

interface ColumnChartProps {
  title: string;
  data: ColumnDatum[];
  /** Texto del desplegable con la tabla de datos (accesibilidad y lectura exacta). */
  tableLabel: string;
  /** Cabeceras de la tabla: [eje X, valor]. */
  columns: [string, string];
  /** Formatea los ticks del eje Y (mismas unidades que `value`). */
  formatTick?: (value: number) => string;
}

const WIDTH = 640;
const HEIGHT = 200;
const PADDING = { top: 16, right: 8, bottom: 24, left: 48 };
const MAX_BAR = 24;
const GAP = 2;
const RADIUS = 4;

/** Techo "redondo" del eje: 1, 2, 5 x 10^n. Los ticks quedan en numeros limpios. */
function niceMax(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const step = [1, 2, 5, 10].find((candidate) => candidate * magnitude >= value) ?? 10;
  return step * magnitude;
}

/** Columna con el extremo de datos redondeado y la base recta, sobre la linea base. */
function columnPath(x: number, y: number, width: number, height: number): string {
  const r = Math.min(RADIUS, width / 2, height);
  const bottom = y + height;
  return [
    `M${x},${bottom}`,
    `V${y + r}`,
    `Q${x},${y} ${x + r},${y}`,
    `H${x + width - r}`,
    `Q${x + width},${y} ${x + width},${y + r}`,
    `V${bottom}`,
    "Z",
  ].join(" ");
}

/**
 * Grafica de columnas de una sola serie, sin dependencias. Una serie por grafica: dos
 * medidas de escala distinta van en dos graficas, nunca en un doble eje.
 *
 * Cada columna es enfocable y muestra su valor al pasar o enfocar; solo se rotula el
 * maximo. La tabla del desplegable lleva todos los valores sin depender del raton.
 */
export function ColumnChart({
  title,
  data,
  tableLabel,
  columns,
  formatTick = (value) => String(value),
}: ColumnChartProps) {
  const titleId = useId();
  const [active, setActive] = useState<number | null>(null);
  const plotWidth = WIDTH - PADDING.left - PADDING.right;
  const plotHeight = HEIGHT - PADDING.top - PADDING.bottom;
  const max = niceMax(Math.max(0, ...data.map((datum) => datum.value)));
  const band = data.length > 0 ? plotWidth / data.length : plotWidth;
  const barWidth = Math.max(1, Math.min(MAX_BAR, band - GAP));
  const peak = data.reduce(
    (best, datum, index) => (datum.value > (data[best]?.value ?? 0) ? index : best),
    0,
  );
  const ticks = [0, max / 2, max];
  // Etiquetas del eje X dispersas: primera, central y ultima.
  const labelled = new Set([0, Math.floor((data.length - 1) / 2), data.length - 1]);
  const activeDatum = active !== null ? data[active] : undefined;

  return (
    <figure className="space-y-2">
      <figcaption id={titleId} className="text-[15px] font-semibold text-ink">
        {title}
      </figcaption>
      <div className="relative">
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="h-auto w-full"
          role="group"
          aria-labelledby={titleId}
          onMouseLeave={() => setActive(null)}
        >
          {ticks.map((tick) => {
            const y = PADDING.top + plotHeight - (tick / max) * plotHeight;
            return (
              <g key={tick}>
                <line
                  x1={PADDING.left}
                  x2={WIDTH - PADDING.right}
                  y1={y}
                  y2={y}
                  className="stroke-divider"
                  strokeWidth={1}
                />
                <text
                  x={PADDING.left - 8}
                  y={y}
                  dy="0.32em"
                  textAnchor="end"
                  className="fill-muted text-[11px]"
                >
                  {formatTick(tick)}
                </text>
              </g>
            );
          })}

          {data.map((datum, index) => {
            const height = (Math.max(0, datum.value) / max) * plotHeight;
            const bandX = PADDING.left + index * band;
            const x = bandX + (band - barWidth) / 2;
            const y = PADDING.top + plotHeight - height;
            const isActive = active === index;
            return (
              <g
                key={`${datum.label}-${index}`}
                tabIndex={0}
                role="img"
                aria-label={`${datum.label}: ${datum.display}`}
                className="cursor-default outline-none"
                onMouseEnter={() => setActive(index)}
                onFocus={() => setActive(index)}
                onBlur={() => setActive(null)}
              >
                {/* Zona de impacto: toda la franja, mas grande que la columna pintada. */}
                <rect
                  x={bandX}
                  y={PADDING.top}
                  width={band}
                  height={plotHeight}
                  className={isActive ? "fill-brand-soft" : "fill-transparent"}
                />
                {height > 0 && (
                  <path
                    d={columnPath(x, y, barWidth, height)}
                    className={isActive ? "fill-brand-hover" : "fill-brand"}
                  />
                )}
                {index === peak && datum.value > 0 && (
                  <text
                    x={x + barWidth / 2}
                    y={y - 4}
                    textAnchor="middle"
                    className="fill-secondary text-[11px] font-semibold"
                  >
                    {datum.display}
                  </text>
                )}
                {labelled.has(index) && (
                  <text
                    x={bandX + band / 2}
                    y={HEIGHT - 6}
                    textAnchor="middle"
                    className="fill-muted text-[11px]"
                  >
                    {datum.label}
                  </text>
                )}
              </g>
            );
          })}

          <line
            x1={PADDING.left}
            x2={WIDTH - PADDING.right}
            y1={PADDING.top + plotHeight}
            y2={PADDING.top + plotHeight}
            className="stroke-line-strong"
            strokeWidth={1}
          />
        </svg>

        {activeDatum && active !== null && (
          <div
            className="pointer-events-none absolute top-0 -translate-x-1/2 rounded-control border border-line bg-surface px-2.5 py-1.5 text-help shadow-floating"
            style={{ left: `${((PADDING.left + (active + 0.5) * band) / WIDTH) * 100}%` }}
          >
            <span className="block font-semibold text-ink">{activeDatum.display}</span>
            <span className="block text-muted">{activeDatum.label}</span>
          </div>
        )}
      </div>

      <details className="text-help text-secondary">
        <summary className="cursor-pointer text-muted">{tableLabel}</summary>
        <table className="mt-2 w-full text-left">
          <thead>
            <tr className="text-muted">
              <th className="py-1 font-medium">{columns[0]}</th>
              <th className="py-1 text-right font-medium">{columns[1]}</th>
            </tr>
          </thead>
          <tbody>
            {data.map((datum, index) => (
              <tr key={`${datum.label}-${index}`} className="border-t border-divider">
                <td className="py-1">{datum.label}</td>
                <td className="py-1 text-right tabular-nums text-ink">{datum.display}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
