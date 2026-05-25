type MetricCardProps = {
  label: string;
  value: string;
  tone?: "warning";
};

export function MetricCard({ label, value, tone }: MetricCardProps) {
  return (
    <div className={`metric ${tone ?? ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
