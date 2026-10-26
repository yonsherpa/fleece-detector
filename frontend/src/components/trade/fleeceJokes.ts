// One-liners shown under a bad verdict, picked at random. Just for fun: they never affect the grade.
// Add your own; keep them short enough to fit on one or two lines.

/** For F grades: you're getting fleeced. */
export const F_JOKES = [
  "This is worse than the Luka for AD trade.",
  "This makes the Herschel Walker trade look fair.",
  "The Red Sox got a better deal selling Babe Ruth.",
  "Mike Ditka gave up a whole draft for Ricky Williams and still did better than this.",
  "The Nets' trade for Pierce and Garnett aged better than this.",
  "Broncos fans have seen this before. It was called the Russell Wilson trade.",
  "Your league chat is already screenshotting this.",
  "The commissioner should veto this for your own protection.",
  "Somewhere a sheep is missing its fleece. It's you.",
  "This is how toilet bowl seasons start.",
  "You're trading a steak dinner for a gas station hot dog.",
  "Your trade partner just texted their group chat \"lmaooo\".",
  "Even the auto-draft wouldn't do this to you.",
  "If you accept this, you're buying everyone's wings at the draft next year.",
  "Your opponent didn't ask for this. They just couldn't believe you'd say yes.",
];

/** For D grades: not a total robbery, but you're losing some wool. */
export const D_JOKES = [
  "Not a full fleece, but you're definitely losing some wool.",
  "Your trade partner is smiling a little too much.",
  "Read the fine print before you hit accept.",
  "This trade needs a counteroffer.",
  "Close, but the other manager wins this one.",
  "This is a \"we'll see\" trade, and we already see.",
  "Selling low is a bold strategy. Let's see if it pays off.",
  "You're one bad week away from regretting this.",
];

/** A random joke for a D or F grade, or null for anything better. */
export function pickFleeceJoke(grade: string): string | null {
  const jokes = grade[0] === "F" ? F_JOKES : grade[0] === "D" ? D_JOKES : null;
  return jokes ? jokes[Math.floor(Math.random() * jokes.length)] : null;
}
