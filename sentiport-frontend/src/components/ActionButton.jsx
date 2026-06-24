const VARIANTS = {
  accept: 'bg-dockwise-accentGreen hover:bg-[#4f9c5e]',
  redirect: 'bg-[#5C84A6] hover:bg-[#4d7290]',
  request: 'bg-dockwise-steel hover:bg-[#314d68]',
};

export default function ActionButton({ variant = 'redirect', children, onClick, disabled, loading }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || loading}
      className={`w-full text-left px-5 py-3 rounded-lg text-white font-body font-medium text-[15px] shadow-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${VARIANTS[variant]}`}
    >
      {loading ? 'Przetwarzanie…' : children}
    </button>
  );
}
