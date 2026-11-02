export default function LoadingSkeleton({ className = "", rows = 3 }) {
  return (
    <div className={`skeleton-stack ${className}`} aria-label="Loading">
      {Array.from({ length: rows }, (_, index) => (
        <span className="skeleton-line" key={index} />
      ))}
    </div>
  );
}
