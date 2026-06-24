/**
 * Pole z podświetleniem - odwzorowuje żółte/różowe boxy z mockupu
 * DockWise ("450m", "xx m/s") oznaczające dane wywnioskowane przez AI
 * albo wymagające uwagi agenta portowego.
 */
export default function HighlightField({ children, tone = 'yellow' }) {
  const toneClasses = {
    yellow: 'bg-dockwise-accentYellow/70 text-[#5C4A00]',
    pink: 'bg-dockwise-highlightPink text-[#7A2E26]',
  };
  return (
    <span className={`inline-block px-2 py-0.5 rounded font-medium ${toneClasses[tone]}`}>
      {children}
    </span>
  );
}
