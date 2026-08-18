#!/usr/bin/env python3
"""Deterministic slop linter for Story Forge drafts.

This script makes no judgment calls. It cannot tell you a beat is boring — that is
the cold reader's job. What it can do is refuse to be talked out of a verdict, which
is why it runs on every draft regardless of how good the draft looks.

Shared by both writers. Research mode checks citation coverage and unfalsifiable
attribution; fiction mode drops those — there is no pack to attribute to — and checks
told emotion and genre cliche instead. Banned constructions, hedging, budget, rhythm,
adverb density, repeated openers, and restatement apply to both.

Usage:
    python3 lint_draft.py draft.md --pack pack.json --budget 95
    python3 lint_draft.py draft.md --budget 95 --mode fiction
    python3 lint_draft.py draft.md --budget 95 --no-claims --json

Exit codes: 0 clean, 1 findings, 2 bad input.
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

SEVERITY_ERROR = "error"
SEVERITY_WARN = "warn"

MODE_RESEARCH = "research"
MODE_FICTION = "fiction"

# Constructions that mark text as machine-written. Matched case-insensitively on
# word boundaries. Kept as phrases rather than single words where the single word
# has legitimate uses.
BANNED_PHRASES = [
    # LLM register tells
    "delve", "delves", "delving",
    "tapestry", "testament to", "treasure trove",
    "navigate the complexities", "navigating the complexities",
    "in the realm of", "in the world of", "in today's world",
    "it's important to note", "it is important to note",
    "it's worth noting", "it is worth noting",
    "when it comes to", "at the end of the day",
    "the fact of the matter is",
    "needless to say", "suffice it to say",
    "little did they know", "little did he know", "little did she know",
    "but here's the thing", "here's the thing",
    "that's where things get interesting",
    "buckle up", "let that sink in",
    "plot twist", "enter the",
    "a game-changer", "game changer", "paradigm shift",
    "unleash", "unlock the secrets", "unlocking the",
    "revolutionize", "revolutionized", "revolutionizing",
    "cutting-edge", "state-of-the-art", "groundbreaking",
    "seamless", "seamlessly", "robust solution",
    "dive into", "deep dive", "let's dive",
    "embark on", "embarking on", "a journey through",
    "the answer may surprise you", "you won't believe",
    "more than meets the eye",
    "stands as a", "serves as a reminder",
    "in conclusion", "to sum up", "all in all",
    # Connective padding
    "moreover", "furthermore", "additionally,", "notably,",
    "that being said", "with that said",
    # Empty intensity
    "truly remarkable", "absolutely stunning", "utterly",
    "nothing short of",
]

# Attribution that cannot be checked. A story built on these has no spine.
UNFALSIFIABLE = [
    "experts say", "experts believe", "experts agree",
    "studies show", "studies suggest", "research shows",
    "scientists say", "scientists believe",
    "many believe", "many people believe", "some say", "some argue",
    "it is believed", "it's believed", "it is said", "it's said",
    "widely regarded", "widely considered", "generally accepted",
    "history tells us", "legend has it",
    "sources say", "reports suggest",
]

# Hedges that drain a sentence without adding accuracy. Real uncertainty belongs in
# the claim's confidence field and should be stated explicitly, not smuggled in here.
HEDGES = [
    "arguably", "perhaps", "possibly", "somewhat", "rather",
    "quite", "fairly", "relatively", "virtually", "essentially",
    "basically", "actually", "really", "very", "just",
    "kind of", "sort of", "a bit", "one might say",
]

# Naming the feeling instead of causing it. This is fiction's version of
# unfalsifiable attribution: the sentence asserts an effect the prose has not earned,
# and a reader who is told they are frightened stops being frightened.
TOLD_EMOTION = [
    r"\b(?:was|were|felt|seemed|looked|grew|became)\s+(?:very\s+|so\s+|really\s+)?"
    r"(?:terrified|afraid|scared|frightened|fearful|uneasy|nervous|anxious|horrified|"
    r"panicked|unnerved|shaken|creeped\s+out)\b",
    r"\b(?:it|this|that|the\s+\w+)\s+(?:was|felt|seemed)\s+(?:very\s+|so\s+)?"
    r"(?:terrifying|horrifying|chilling|eerie|creepy|spooky|unsettling|ominous|"
    r"sinister|menacing|haunting|dreadful)\b",
    r"\bfilled\s+(?:him|her|them|me|us)\s+with\s+(?:dread|fear|terror|horror)\b",
    r"\ba\s+(?:sense|feeling|wave)\s+of\s+(?:dread|unease|foreboding|terror|horror)\b",
]

# Horror's stock gestures. Each one is a writer reaching for the genre's furniture
# instead of the specific detail that would actually land.
GENRE_CLICHES = [
    "a chill ran down", "chill ran down her spine", "chill ran down his spine",
    "blood ran cold", "hair stood on end", "goosebumps",
    "heart pounded", "heart hammered", "heart raced", "pulse quickened",
    "breath caught", "breath hitched", "blood curdling", "bloodcurdling",
    "deafening silence", "eerie silence", "dead silence",
    "silence was deafening", "silence was eerie", "air was thick",
    "temperature dropped", "lights flickered", "door creaked open",
    "felt a presence", "sensed a presence",
    "shadows danced", "darkness swallowed", "an unspeakable",
    "little did", "or so they thought", "never to be seen again",
    "the last thing he saw", "the last thing she saw",
    "something was watching", "she wasn't alone", "he wasn't alone",
]

# Sentence openers that, repeated, flatten rhythm.
WEAK_OPENERS = ["and", "but", "so", "then", "it", "this", "there", "that", "however"]

CITATION_RE = re.compile(r"\[(C\d{3,})\]")
# A sentence carrying a number, a year, a percentage, or a capitalised multi-word
# name is making a factual assertion and needs a source.
FACTUAL_SIGNAL_RE = re.compile(
    r"\b\d{4}\b"                       # year
    r"|\b\d+(?:\.\d+)?\s*(?:%|percent)"  # percentage
    r"|\b\d+(?:,\d{3})+\b"             # large number
    r"|\$\s?\d"                        # money
    r"|\b(?:[A-Z][a-z]+\s+){1,}[A-Z][a-z]+\b"  # proper noun phrase
)
ADVERB_RE = re.compile(r"\b\w+ly\b", re.IGNORECASE)


def finding(code, severity, message, line=None, excerpt=None):
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "line": line,
        "excerpt": excerpt,
    }


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        sys.exit(2)


def load_pack(path):
    raw = read_text(path)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"{path} is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(2)
    claims = data.get("claims")
    if not isinstance(claims, list):
        print(f"{path} has no 'claims' list", file=sys.stderr)
        sys.exit(2)
    return {c.get("id"): c for c in claims if isinstance(c, dict) and c.get("id")}


def strip_markdown(text):
    """Narration only — headers, fences, and citation markers are not spoken."""
    out = []
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.lstrip().startswith("#"):
            continue
        if line.lstrip().startswith(">"):
            continue
        out.append(line)
    return "\n".join(out)


def narration_words(text):
    body = CITATION_RE.sub("", strip_markdown(text))
    return [w for w in re.findall(r"[A-Za-z0-9'’\-]+", body) if w]


def split_sentences(text):
    body = CITATION_RE.sub("", strip_markdown(text))
    body = re.sub(r"\s+", " ", body).strip()
    if not body:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'‘“])", body)
    return [p.strip() for p in parts if p.strip()]


def line_of(text, needle_start):
    return text.count("\n", 0, needle_start) + 1


def check_phrases(text, phrases, code, severity, label):
    out = []
    for phrase in phrases:
        pattern = re.compile(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", re.IGNORECASE)
        for match in pattern.finditer(text):
            start = max(0, match.start() - 40)
            end = min(len(text), match.end() + 40)
            out.append(finding(
                code, severity,
                f"{label}: {phrase!r}",
                line=line_of(text, match.start()),
                excerpt=text[start:end].replace("\n", " ").strip(),
            ))
    return out


def check_budget(text, budget, tolerance):
    out = []
    words = narration_words(text)
    count = len(words)
    if budget <= 0:
        return out, count
    ceiling = int(budget * (1 + tolerance))
    floor = int(budget * (1 - tolerance))
    if count > ceiling:
        out.append(finding("over-budget", SEVERITY_ERROR,
                           f"{count} narration words against a cap of {budget} "
                           f"(+{tolerance:.0%} tolerance = {ceiling}). Cut, do not compress."))
    elif count < floor:
        out.append(finding("under-budget", SEVERITY_WARN,
                           f"{count} narration words against a budget of {budget} "
                           f"(-{tolerance:.0%} tolerance = {floor}). Short is fine if the beat "
                           "did its job — check that it did."))
    return out, count


def check_citations(text, claims, require):
    """Every factual assertion carries a claim ID, and every ID resolves."""
    out = []
    cited = set(CITATION_RE.findall(text))

    for cid in sorted(cited):
        if cid not in claims:
            out.append(finding("unknown-claim", SEVERITY_ERROR,
                               f"{cid} is cited but not in the research pack"))
            continue
        claim = claims[cid]
        if claim.get("verified") is False:
            out.append(finding("unverified-claim", SEVERITY_ERROR,
                               f"{cid} has not passed independent verification"))
        if claim.get("confidence") == "low":
            out.append(finding("low-confidence-claim", SEVERITY_WARN,
                               f"{cid} is low confidence — it must be framed as disputed "
                               "in the prose, not stated flat"))

    if not require:
        return out, cited

    for raw_sentence in split_sentences_with_citations(text):
        sentence, has_citation = raw_sentence
        if has_citation:
            continue
        if FACTUAL_SIGNAL_RE.search(sentence):
            out.append(finding("uncited-claim", SEVERITY_ERROR,
                               "factual assertion with no claim ID",
                               excerpt=sentence[:160]))
    return out, cited


def split_sentences_with_citations(text):
    """Sentences paired with whether they carry a citation, before markers are stripped."""
    body = strip_markdown(text)
    body = re.sub(r"\s+", " ", body).strip()
    if not body:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=\[?[A-Z\"'‘“])", body)
    result = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        has = bool(CITATION_RE.search(part))
        result.append((CITATION_RE.sub("", part).strip(), has))
    return result


def check_rhythm(text):
    """Uniform sentence length is the single loudest tell of generated prose."""
    out = []
    sentences = split_sentences(text)
    if not sentences:
        return out

    lengths = [len(re.findall(r"[A-Za-z0-9'’\-]+", s)) for s in sentences]

    # A sentence too long to say is wrong on its own, not relative to its neighbours,
    # so this runs regardless of how many sentences there are to compare against.
    for s, n in zip(sentences, lengths):
        if n > 35:
            out.append(finding("runaway-sentence", SEVERITY_WARN,
                               f"sentence of {n} words — will not survive being read aloud",
                               excerpt=s[:160]))

    # The distribution checks below need enough samples to mean anything.
    if len(sentences) < 4:
        return out

    mean = sum(lengths) / len(lengths)
    variance = sum((n - mean) ** 2 for n in lengths) / len(lengths)
    stdev = variance ** 0.5

    if mean > 0 and stdev / mean < 0.35:
        out.append(finding("flat-rhythm", SEVERITY_WARN,
                           f"sentence lengths cluster tightly (mean {mean:.0f} words, "
                           f"stdev {stdev:.1f}). Spoken narration needs short sentences "
                           "against long ones."))

    if not any(n <= 6 for n in lengths):
        out.append(finding("no-short-sentence", SEVERITY_WARN,
                           "no sentence under 7 words. A beat with no short sentence has "
                           "nowhere for the listener to land."))
    return out


def check_openers(text):
    out = []
    sentences = split_sentences(text)
    if len(sentences) < 4:
        return out
    openers = []
    for s in sentences:
        words = re.findall(r"[A-Za-z']+", s)
        if words:
            openers.append(words[0].lower())
    counts = Counter(openers)
    for word, n in counts.items():
        if n >= 3 and word in WEAK_OPENERS:
            out.append(finding("repeated-opener", SEVERITY_WARN,
                               f"{n} sentences open with {word!r}"))
        elif n >= 4:
            out.append(finding("repeated-opener", SEVERITY_WARN,
                               f"{n} sentences open with {word!r}"))
    return out


def check_adverbs(text):
    out = []
    words = narration_words(text)
    if len(words) < 40:
        return out
    adverbs = ADVERB_RE.findall(" ".join(words))
    # -ly words that are not adverbs of manner and shouldn't count against the draft.
    allow = {"only", "early", "family", "likely", "reply", "supply", "apply",
             "rely", "july", "italy", "assembly", "monopoly", "anomaly", "ally"}
    adverbs = [a for a in adverbs if a.lower() not in allow]
    density = len(adverbs) / len(words)
    if density > 0.035:
        out.append(finding("adverb-heavy", SEVERITY_WARN,
                           f"{len(adverbs)} -ly adverbs in {len(words)} words "
                           f"({density:.1%}). Strong verbs do not need them."))
    return out


def check_restatement(text):
    """Padding to length shows up as the same beat said twice in new words."""
    out = []
    sentences = split_sentences(text)
    stop = {"the", "a", "an", "of", "to", "in", "and", "that", "it", "is", "was",
            "for", "on", "with", "as", "at", "by", "from", "but", "or", "this",
            "they", "he", "she", "we", "you", "not", "be", "have", "had", "has"}
    sig = []
    for s in sentences:
        words = {w.lower() for w in re.findall(r"[A-Za-z']{4,}", s)} - stop
        sig.append((s, words))

    for i in range(len(sig)):
        for j in range(i + 1, len(sig)):
            a, b = sig[i][1], sig[j][1]
            if len(a) < 4 or len(b) < 4:
                continue
            overlap = len(a & b) / len(a | b)
            if overlap > 0.55:
                out.append(finding("restatement", SEVERITY_WARN,
                                   f"two sentences share {overlap:.0%} of their content words "
                                   "— one of them is padding",
                                   excerpt=f"{sig[i][0][:80]} || {sig[j][0][:80]}"))
    return out


# Narration often poses a question without punctuating it as one. These count.
INTERROGATIVE_RE = re.compile(
    r"\b(?:the question (?:is|becomes)|which raises|what nobody|no one knew|"
    r"why (?:six|it|she|he|they|that|this|the)|how (?:she|he|it|they|that|the)|"
    r"whether|the answer|nobody could explain|what happened next)\b",
    re.IGNORECASE,
)


def check_told_emotion(text):
    """Caught in fiction the way unfalsifiable attribution is caught in research."""
    out = []
    for pattern in TOLD_EMOTION:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            start = max(0, match.start() - 40)
            end = min(len(text), match.end() + 40)
            phrase = " ".join(match.group(0).split())
            out.append(finding(
                "told-emotion", SEVERITY_ERROR,
                f"names the feeling instead of causing it: {phrase!r}",
                line=line_of(text, match.start()),
                excerpt=text[start:end].replace("\n", " ").strip(),
            ))
    return out


def check_question_present(text):
    """Every beat either opens a question or pays one off. Silence is a dead beat."""
    out = []
    body = strip_markdown(text)
    if "?" in body or INTERROGATIVE_RE.search(body):
        return out
    out.append(finding("no-question", SEVERITY_WARN,
                       "the beat neither asks nor frames a question — confirm against the "
                       "ledger that this is a payoff beat and not a dead beat"))
    return out


def run_checks(text, claims, budget, tolerance, require_claims, mode=MODE_RESEARCH):
    findings = []
    findings += check_phrases(text, BANNED_PHRASES, "banned-phrase", SEVERITY_ERROR,
                              "banned construction")
    findings += check_phrases(text, HEDGES, "hedge", SEVERITY_WARN, "hedge")

    if mode == MODE_FICTION:
        # No pack to attribute to, so unfalsifiable attribution is not the failure
        # mode here. Told emotion and genre furniture are.
        findings += check_told_emotion(text)
        findings += check_phrases(text, GENRE_CLICHES, "genre-cliche", SEVERITY_ERROR,
                                  "genre cliche")
    else:
        findings += check_phrases(text, UNFALSIFIABLE, "unfalsifiable", SEVERITY_ERROR,
                                  "unfalsifiable attribution")

    budget_findings, word_count = check_budget(text, budget, tolerance)
    findings += budget_findings

    cited = set()
    if claims is not None:
        citation_findings, cited = check_citations(text, claims, require_claims)
        findings += citation_findings

    findings += check_rhythm(text)
    findings += check_openers(text)
    findings += check_adverbs(text)
    findings += check_restatement(text)
    findings += check_question_present(text)
    return findings, word_count, cited


def main():
    parser = argparse.ArgumentParser(description="Deterministic slop linter for Story Forge.")
    parser.add_argument("draft", help="path to the draft markdown")
    parser.add_argument("--pack", help="path to research pack JSON")
    parser.add_argument("--budget", type=int, default=0,
                        help="word budget for this beat")
    parser.add_argument("--tolerance", type=float, default=0.15,
                        help="fractional budget tolerance (default 0.15)")
    parser.add_argument("--no-claims", action="store_true",
                        help="skip the uncited-assertion check (still validates cited IDs)")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="emit findings as JSON")
    parser.add_argument("--strict", action="store_true",
                        help="treat warnings as failures")
    parser.add_argument("--mode", default=MODE_RESEARCH,
                        choices=[MODE_RESEARCH, MODE_FICTION],
                        help="fiction swaps citation checks for told-emotion and cliche")
    args = parser.parse_args()

    text = read_text(args.draft)
    claims = load_pack(args.pack) if args.pack else None

    require_claims = not args.no_claims and args.mode != MODE_FICTION
    findings, word_count, cited = run_checks(
        text, claims, args.budget, args.tolerance, require_claims, args.mode
    )

    errors = [f for f in findings if f["severity"] == SEVERITY_ERROR]
    warnings = [f for f in findings if f["severity"] == SEVERITY_WARN]

    if args.as_json:
        print(json.dumps({
            "draft": args.draft,
            "mode": args.mode,
            "ok": not errors and not (args.strict and warnings),
            "word_count": word_count,
            "budget": args.budget,
            "claims_cited": sorted(cited),
            "errors": errors,
            "warnings": warnings,
        }, indent=2))
    else:
        for f in errors + warnings:
            tag = "ERROR " if f["severity"] == SEVERITY_ERROR else "WARN  "
            loc = f":{f['line']}" if f.get("line") else ""
            print(f"{tag} [{f['code']}]{loc} {f['message']}")
            if f.get("excerpt"):
                print(f"         … {f['excerpt']}")
        print()
        print(f"{word_count} narration words"
              + (f" (budget {args.budget})" if args.budget else ""))
        if not findings:
            print("draft ok — no mechanical findings")
        else:
            print(f"{len(errors)} error(s), {len(warnings)} warning(s)")

    if errors or (args.strict and warnings):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
