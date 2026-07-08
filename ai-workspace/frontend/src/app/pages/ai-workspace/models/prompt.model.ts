export interface PromptTemplate {
  id: string;
  title: string;
  description?: string;
  body: string;
  mode: 'ask' | 'agent' | 'both';
  tags?: string[];
}
