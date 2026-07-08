interface ApprovalCardProps {
  summary: string;
  actionId?: string;
  risk?: string;
  sending: boolean;
  onDecision: (actionId: string, decision: 'approve' | 'reject') => void;
  t: (key: string) => string;
}

export function ApprovalCard({ summary, actionId, risk, sending, onDecision, t }: ApprovalCardProps) {
  return (
    <div className="command-inline-card approval">
      <div className="command-card-heading">
        <strong>{t('command.approvalRequired')}</strong>
        <span>{risk === 'delete' ? t('command.deleteOperation') : t('command.writeRisk')}</span>
      </div>
      <p>{summary}</p>
      <div className="command-card-actions">
        <button
          type="button"
          disabled={!actionId || sending}
          onClick={() => actionId && onDecision(actionId, 'approve')}
        >
          {sending ? t('command.running') : t('command.approve')}
        </button>
        <button
          className="ghost"
          type="button"
          disabled={!actionId || sending}
          onClick={() => actionId && onDecision(actionId, 'reject')}
        >
          {t('command.reject')}
        </button>
      </div>
    </div>
  );
}
