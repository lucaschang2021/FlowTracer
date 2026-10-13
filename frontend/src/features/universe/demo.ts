import type { DemoRadar } from './model';

// Isolated UX fixtures, NOT API records. Deliberately non-UUID IDs cannot masquerade as backend facts.
export const DEMO_RADARS: readonly DemoRadar[] = [
  { id: 'demo-ai', name: 'AI Infrastructure', type: 'technology', status: 'active', signals: 5, x: -450, y: -130, color: 'blue', description: '模型基础设施、推理效率与工程实践。' },
  { id: 'demo-policy', name: 'Policy Monitor', type: 'policy', status: 'active', signals: 4, x: -280, y: 130, color: 'ice', description: '人工智能政策、公开规则与行业治理。' },
  { id: 'demo-market', name: 'Market Observatory', type: 'market', status: 'active', signals: 6, x: 20, y: -170, color: 'gold', description: '产业变化与公开市场研究的示例关注方向。' },
  { id: 'demo-research', name: 'Research Frontiers', type: 'academic', status: 'active', signals: 3, x: 430, y: -100, color: 'teal', description: '前沿论文、可复现的方法与研究进展。' },
  { id: 'demo-agent', name: 'Agent Networks', type: 'custom', status: 'paused', signals: 2, x: -40, y: 130, color: 'violet', description: '智能体协作与工具使用的示例 Radar。' },
  { id: 'demo-opportunity', name: 'Opportunity Galaxy', type: 'opportunity', status: 'active', signals: 4, x: 350, y: 175, color: 'silver', description: '机会类信息的视觉映射，不产生任何自动行动。' },
];

export const DEMO_GALAXY = {
  id: 'demo-galaxy', name: 'AI Research Galaxy',
  members: ['demo-ai', 'demo-policy'], x: -365, y: 0,
} as const;

export const freshDemo = () => DEMO_RADARS.map(radar => ({ ...radar }));
