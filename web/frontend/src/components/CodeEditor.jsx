export default function CodeEditor({ value, onChange }) {
  return (
    <div className="relative">
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        spellCheck={false}
        className="w-full h-64 p-4 font-mono text-sm bg-gray-900 text-green-400 resize-none focus:outline-none"
        placeholder="Paste your SQL or Python code here..."
      />
      <div className="absolute top-2 right-2 text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded">
        SQL / Python
      </div>
    </div>
  );
}
