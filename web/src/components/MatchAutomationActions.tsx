import { Clock, ListPlus } from "lucide-react";

export function MatchAutomationActions({
  isBusy,
  onCreateFiltered,
  onCreateManual
}: {
  isBusy: boolean;
  onCreateFiltered: () => void;
  onCreateManual: () => void;
}) {
  return (
    <div className="sync-action">
      <button disabled={isBusy} onClick={onCreateManual} type="button">
        <Clock size={16} />
        创建自动任务
      </button>
      <button disabled={isBusy} onClick={onCreateFiltered} type="button">
        <ListPlus size={16} />
        一键创建筛选任务
      </button>
    </div>
  );
}
