import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Rectangle,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type RectangleProps,
} from "recharts";
import type { PlayerValue, Position } from "../../types/api";
import { signed } from "../ui";

// Validated pair (dataviz validator, card surface #1E2535): lightness, chroma, contrast pass; CVD ΔE 7.5,
// which is allowed because every bar is also direct-labeled and the legend names both sides.
export const GIVE_COLOR = "#FC2B6D";
export const RECEIVE_COLOR = "#00A896";

const AXIS = { fill: "#8A93A6", fontSize: 11 };
const GRID = "#2A3245";

function TooltipBox({ title, lines }: { title: string; lines: string[] }) {
  return (
    <div className="rounded-md border border-ink-700 bg-ink-850 px-3 py-2 text-xs shadow-lg shadow-black/30">
      <div className="mb-1 font-medium text-ink-100">{title}</div>
      {lines.map((l) => (
        <div key={l} className="num text-ink-300">
          {l}
        </div>
      ))}
    </div>
  );
}

interface PlayerRow {
  name: string;
  side: "Gives" | "Receives";
  value: number;
  ros: number;
}

/** Value over replacement of every player in the trade, grouped by side. */
export function PlayerValueChart({ given, received }: { given: PlayerValue[]; received: PlayerValue[] }) {
  const rows: PlayerRow[] = [
    ...given.map((p) => ({ name: p.name, side: "Gives" as const, value: p.value_over_replacement, ros: p.projected_ros_points })),
    ...received.map((p) => ({ name: p.name, side: "Receives" as const, value: p.value_over_replacement, ros: p.projected_ros_points })),
  ];
  const height = 40 + rows.length * 38;

  return (
    <div>
      <div className="mb-3 flex gap-4 text-xs text-ink-400">
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm" style={{ background: GIVE_COLOR }} /> Team A gives
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm" style={{ background: RECEIVE_COLOR }} /> Team A receives
        </span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 44, bottom: 0, left: 0 }} barCategoryGap={8}>
          <CartesianGrid horizontal={false} stroke={GRID} />
          <XAxis type="number" tick={AXIS} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="name" width={130} tick={AXIS} axisLine={false} tickLine={false} />
          <Tooltip
            cursor={{ fill: "rgba(255,255,255,0.03)" }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const r = payload[0].payload as PlayerRow;
              return (
                <TooltipBox
                  title={`${r.name} · ${r.side.toLowerCase()}`}
                  lines={[`Value over repl. ${r.value.toFixed(1)}`, `Projected ROS ${r.ros.toFixed(0)} pts`]}
                />
              );
            }}
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={22} isAnimationActive>
            {rows.map((r, i) => (
              <Cell key={i} fill={r.side === "Gives" ? GIVE_COLOR : RECEIVE_COLOR} />
            ))}
            <LabelList dataKey="value" position="right" formatter={(v: number) => v.toFixed(1)} fill="#AEB5C4" fontSize={11} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export interface PositionDelta {
  position: Position;
  delta: number;
}

function DivergingBar(raw: unknown) {
  const props = raw as RectangleProps & { delta: number };
  const up = props.delta >= 0;
  const height = props.height ?? 0;
  const y = (props.y ?? 0) + Math.min(height, 0);
  return (
    <Rectangle
      x={props.x}
      width={props.width}
      y={y}
      height={Math.abs(height)}
      fill={up ? RECEIVE_COLOR : GIVE_COLOR}
      radius={up ? [4, 4, 0, 0] : [0, 0, 4, 4]}
    />
  );
}

/** Diverging bars around zero: gains (blue) and losses (rose) per position, values labeled. */
export function PositionDeltaChart({ data, unit }: { data: PositionDelta[]; unit: string }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 18, right: 8, bottom: 0, left: -12 }} barCategoryGap="28%">
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey="position" tick={{ ...AXIS, fontWeight: 600 }} axisLine={false} tickLine={false} />
        <YAxis tick={AXIS} axisLine={false} tickLine={false} />
        <ReferenceLine y={0} stroke="#5D6679" />
        <Tooltip
          cursor={{ fill: "rgba(255,255,255,0.03)" }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const r = payload[0].payload as PositionDelta;
            return <TooltipBox title={r.position} lines={[`${signed(r.delta)} ${unit}`]} />;
          }}
        />
        <Bar
          dataKey="delta"
          maxBarSize={40}
          // Round only the data end of each bar, never the end on the zero baseline.
          shape={DivergingBar}
        >
          <LabelList
            dataKey="delta"
            position="top"
            formatter={(v: number) => (v === 0 ? "" : signed(v))}
            fill="#AEB5C4"
            fontSize={11}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
