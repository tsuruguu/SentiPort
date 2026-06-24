export default function GlassPanel({ title, headerRight, children, className = '' }) {
  return (
    <div className={`bg-white/95 rounded-2xl shadow-xl overflow-hidden flex flex-col min-h-0 ${className}`}>
      {title && (
        <div className="flex items-center justify-between px-6 py-4 bg-dockwise-mist border-b border-black/5">
          <h2 className="font-display text-2xl font-semibold text-dockwise-navy">{title}</h2>
          {headerRight}
        </div>
      )}
      <div className="flex-1 overflow-y-auto p-6">{children}</div>
    </div>
  );
}
