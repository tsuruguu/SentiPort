/**
 * Tło "morskie" odtwarzające atmosferę mockupu DockWise - gradient
 * granatowo-stalowy + subtelne fale SVG, bez zależności od zewnętrznych
 * zdjęć (prawa autorskie, czas ładowania).
 */
export default function OceanBackground() {
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden bg-gradient-to-br from-dockwise-navy via-dockwise-steel to-[#5C84A6]">
      <svg
        className="absolute bottom-0 left-0 w-full opacity-30"
        viewBox="0 0 1440 300"
        preserveAspectRatio="none"
      >
        <path
          d="M0,150 C240,220 480,80 720,140 C960,200 1200,100 1440,160 L1440,300 L0,300 Z"
          fill="#ffffff"
          fillOpacity="0.08"
        />
        <path
          d="M0,200 C300,260 600,140 900,190 C1100,220 1300,170 1440,200 L1440,300 L0,300 Z"
          fill="#ffffff"
          fillOpacity="0.12"
        />
      </svg>
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_15%_20%,rgba(255,255,255,0.08),transparent_45%)]" />
    </div>
  );
}
