// webui/src/components/orchestration/TaskDAGView.tsx
import { useMemo } from "react";
import type { OrchestrationPlan, OrchestrationTaskNode } from "@/lib/types";

interface TaskDAGViewProps {
  plan: OrchestrationPlan;
  editable?: boolean;
}

const ROLE_COLORS: Record<string, { bg: string; border: string }> = {
  analyst: { bg: "#EFF6FF", border: "#3B82F6" },
  developer: { bg: "#F0FDF4", border: "#22C55E" },
  tester: { bg: "#FEFCE8", border: "#EAB308" },
  reviewer: { bg: "#FAF5FF", border: "#A855F7" },
};

const STATUS_COLORS: Record<string, string> = {
  pending: "#9CA3AF",
  ready: "#60A5FA",
  running: "#22C55E",
  completed: "#3B82F6",
  failed: "#EF4444",
};

const ROLE_LABELS: Record<string, string> = {
  analyst: "分析",
  developer: "开发",
  tester: "测试",
  reviewer: "审查",
};

const NODE_W = 140;
const NODE_H = 56;
const LAYER_GAP_X = 180;
const NODE_GAP_Y = 24;

interface LayoutNode extends OrchestrationTaskNode {
  layer: number;
  y: number;
}

function computeLayout(tasks: OrchestrationTaskNode[]): LayoutNode[] {
  const depths = new Map<string, number>();
  const children = new Map<string, string[]>();
  for (const t of tasks) children.set(t.id, []);
  for (const t of tasks) {
    for (const dep of t.dependencies) {
      children.get(dep)?.push(t.id);
    }
  }

  // BFS from root nodes
  const queue: string[] = [];
  const inDegree = new Map<string, number>();
  for (const t of tasks) {
    inDegree.set(t.id, t.dependencies.length);
    if (t.dependencies.length === 0) {
      depths.set(t.id, 0);
      queue.push(t.id);
    }
  }

  while (queue.length > 0) {
    const node = queue.shift()!;
    const depth = depths.get(node) ?? 0;
    for (const child of children.get(node) ?? []) {
      depths.set(child, Math.max(depths.get(child) ?? 0, depth + 1));
      const deg = (inDegree.get(child) ?? 1) - 1;
      inDegree.set(child, deg);
    }
  }

  for (const t of tasks) {
    if (!depths.has(t.id)) depths.set(t.id, 0);
  }

  // Group by layer, assign y positions
  const byLayer = new Map<number, OrchestrationTaskNode[]>();
  for (const t of tasks) {
    const layer = depths.get(t.id) ?? 0;
    if (!byLayer.has(layer)) byLayer.set(layer, []);
    byLayer.get(layer)!.push(t);
  }

  const result: LayoutNode[] = [];
  const sortedLayers = [...byLayer.entries()].sort((a, b) => a[0] - b[0]);
  for (const [layer, layerTasks] of sortedLayers) {
    const totalH = layerTasks.length * NODE_H + (layerTasks.length - 1) * NODE_GAP_Y;
    const startY = -totalH / 2;
    layerTasks.forEach((t, i) => {
      result.push({ ...t, layer, y: startY + i * (NODE_H + NODE_GAP_Y) });
    });
  }
  return result;
}

export function TaskDAGView({ plan }: TaskDAGViewProps) {
  const layout = useMemo(() => computeLayout(plan.tasks), [plan.tasks]);

  const maxLayer = Math.max(...layout.map((n) => n.layer), 0);
  const svgW = (maxLayer + 1) * LAYER_GAP_X + NODE_W + 40;
  const allYs = layout.map((n) => n.y);
  const minY = Math.min(...allYs, -NODE_H);
  const maxY = Math.max(...allYs, NODE_H);
  const svgH = maxY - minY + NODE_H + 40;
  const offsetY = -minY + 20;

  const nodePositions = new Map(
    layout.map((n) => [n.id, { x: n.layer * LAYER_GAP_X + 20, y: n.y + offsetY }]),
  );

  const edges: { from: string; to: string }[] = [];
  for (const n of layout) {
    for (const dep of n.dependencies) {
      edges.push({ from: dep, to: n.id });
    }
  }

  return (
    <svg
      viewBox={`0 0 ${svgW} ${svgH}`}
      className="w-full h-auto"
      style={{ maxHeight: layout.length <= 2 ? "180px" : "320px" }}
    >
      <defs>
        <marker
          id="arrowhead"
          viewBox="0 0 10 7"
          refX={9}
          refY={3.5}
          markerWidth={6}
          markerHeight={5}
          orient="auto"
        >
          <polygon points="0 0, 10 3.5, 0 7" fill="#9CA3AF" />
        </marker>
      </defs>
      {/* Edges */}
      {edges.map(({ from, to }) => {
        const fp = nodePositions.get(from);
        const tp = nodePositions.get(to);
        if (!fp || !tp) return null;
        const midX = (fp.x + NODE_W + tp.x) / 2;
        return (
          <path
            key={`${from}-${to}`}
            d={`M ${fp.x + NODE_W} ${fp.y + NODE_H / 2} C ${midX} ${fp.y + NODE_H / 2}, ${midX} ${tp.y + NODE_H / 2}, ${tp.x} ${tp.y + NODE_H / 2}`}
            fill="none"
            stroke="#D1D5DB"
            strokeWidth={1.5}
            markerEnd="url(#arrowhead)"
          />
        );
      })}
      {/* Nodes */}
      {layout.map((n) => {
        const pos = nodePositions.get(n.id)!;
        const colors = ROLE_COLORS[n.role] ?? ROLE_COLORS.analyst;
        const statusColor = STATUS_COLORS[n.status] ?? STATUS_COLORS.pending;
        return (
          <g key={n.id} transform={`translate(${pos.x}, ${pos.y})`}>
            <rect
              x={0}
              y={0}
              width={NODE_W}
              height={NODE_H}
              rx={8}
              ry={8}
              fill={colors.bg}
              stroke={n.status === "running" ? statusColor : colors.border}
              strokeWidth={n.status === "running" ? 2 : 1}
            />
            <circle cx={12} cy={NODE_H / 2} r={5} fill={statusColor} />
            <text x={24} y={22} fontSize={10} fill="#6B7280" fontFamily="system-ui">
              {ROLE_LABELS[n.role] ?? n.role}
            </text>
            <text
              x={24}
              y={40}
              fontSize={13}
              fontWeight={600}
              fill="#1F2937"
              fontFamily="system-ui"
            >
              {n.title.length > 10 ? n.title.slice(0, 10) + "…" : n.title}
            </text>
            {n.status === "failed" && (
              <text
                x={NODE_W - 12}
                y={NODE_H / 2 + 4}
                fontSize={14}
                textAnchor="middle"
                fill="#EF4444"
              >
                !
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
