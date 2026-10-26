import { Construction } from "lucide-react";
import { Link } from "react-router-dom";

/** Honest placeholder for features that are planned but not built yet. */
export function ComingSoonPage({ title, phase, description }: { title: string; phase: string; description: string }) {
  return (
    <div className="mx-auto max-w-lg py-16 text-center">
      <div className="mx-auto grid h-14 w-14 place-items-center rounded-lg border border-ink-700 bg-ink-800">
        <Construction className="h-6 w-6 text-ink-400" />
      </div>
      <div className="label mt-6">{phase}</div>
      <h1 className="mt-1 text-2xl font-bold">{title}</h1>
      <p className="mt-3 text-sm leading-relaxed text-ink-400">{description}</p>
      <Link
        to="/"
        className="mt-6 inline-flex rounded-md border border-ink-700 bg-ink-800 px-3 py-1.5 text-sm font-medium text-ink-100 hover:bg-ink-700"
      >
        Back to Trade
      </Link>
    </div>
  );
}
