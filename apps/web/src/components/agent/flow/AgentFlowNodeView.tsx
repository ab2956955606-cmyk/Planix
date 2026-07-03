import { ChevronDown, ChevronRight } from 'lucide-react';
import type { AgentFlowNode } from '../../../types';
import { agentFlowActions } from '../../../store/agentFlowStore';
import { AgentDiffViewer } from './AgentDiffViewer';
import { AgentStepCard } from './AgentStepCard';

interface AgentFlowNodeViewProps {
  node: AgentFlowNode;
  t: (key: string) => string;
}

export function AgentFlowNodeView({ node, t }: AgentFlowNodeViewProps) {
  const label = getNodeLabel(node, t);
  const displayTitle = node.type === 'tool' ? node.title : label;

  return (
    <AgentStepCard node={node} label={label} title={displayTitle} statusLabel={t(`agentFlow.${node.status}`)}>
      {node.type === 'tool' && node.toolCall ? (
        <ToolCallView node={node} t={t} />
      ) : (
        <AgentDiffViewer content={node.content} diff={node.diff} isStreaming={node.status === 'running'} />
      )}
    </AgentStepCard>
  );
}

function ToolCallView({ node, t }: AgentFlowNodeViewProps) {
  const toolCall = node.toolCall;
  if (!toolCall) return null;

  return (
    <div className="tool-call-box">
      <button
        className="tool-call-toggle"
        type="button"
        onClick={() => agentFlowActions.setExpanded(node.id, !toolCall.expanded)}
      >
        {toolCall.expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
        <span>{toolCall.name}</span>
        <em>{t(`agentFlow.${toolCall.writeMode || 'preview'}`)}</em>
      </button>
      {toolCall.expanded ? (
        <div className="tool-call-detail">
          <div>
            <span>{t('agentFlow.toolInput')}</span>
            <pre>{toolCall.input}</pre>
          </div>
          <div>
            <span>{t('agentFlow.toolOutput')}</span>
            <pre>{toolCall.output || node.content}</pre>
          </div>
          <div className="tool-latency">
            <span>{t('agentFlow.latency')}</span>
            <strong>{toolCall.latencyMs ? `${toolCall.latencyMs}ms` : '-'}</strong>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function getNodeLabel(node: AgentFlowNode, t: (key: string) => string) {
  const keyByType: Record<AgentFlowNode['type'], string> = {
    input: 'input',
    reasoning: 'plan',
    tool: 'tool',
    observation: 'observation',
    output: 'output'
  };

  return t(`agentFlow.${keyByType[node.type]}`);
}
