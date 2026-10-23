import evidence from './evidence.json';
export { evidence };
export interface Measurement {
  queryId: string;
  variant: string;
  evidence: string;
  estimatedPlan: {
    hash: number;
    operators: {
      id: number;
      operation: string;
      options: string | null;
      object: string | null;
      estimated_rows: number | null;
      optimizer_cost: number | null;
    }[];
  };
}
export type IndexExperiment = (typeof evidence.indexes)[number];
export const repository = import.meta.env.BASE_URL + 'source/index.html';
export const sourceUrl = (path: string) => {
  const [file, fragment] = path.split('#', 2);
  if (!file || file.startsWith('/') || file.includes('..') || file.includes('\\') || Array.from(file).some((character) => character.charCodeAt(0) < 32))
    throw new Error('Invalid public source path');
  const asset = file.endsWith('.md') ? file + '.html' : file.endsWith('.json') ? file : file + '.txt';
  return import.meta.env.BASE_URL + 'source/' + asset + (fragment ? '#' + fragment : '');
};
// Fixed notation in both languages makes every published measurement directly comparable.
export const number = (value: number, digits = 3) =>
  new Intl.NumberFormat('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
export const percent = (value: number) => `${value > 0 ? '+' : ''}${number(value, 2)}%`;
export const usesIndex = (experiment: IndexExperiment) =>
  experiment.after.estimatedPlan.operators.some((op) => op.object === experiment.index);
